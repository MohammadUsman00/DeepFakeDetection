from __future__ import annotations

import time
import uuid
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request, UploadFile

from ...config import settings
from ...db.repository import JobRepository
from ...db.session import db_session
from ...db.user_repository import UserRepository
from ...services.storage_service import StorageService
from ...services.job_service import JobClock, JobService, is_transient_error
from ...utils.enums import JobState, ProcessingStage
from ...utils.errors import AppError, ErrorCode
from ...utils.logging import get_logger
from ...utils.validation import validate_upload_metadata
from ...utils.video import validate_video_duration
from ...video.pipeline import analyze_video_up_to_inference
from ..deps import resolve_bearer_user_id


router = APIRouter()
_storage = StorageService()


import socketio
from ...celery_app import celery_app

# Synchronous Socket.io manager for Celery workers
sio_mgr = socketio.RedisManager(os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"))

@celery_app.task(name="process_analysis_task", bind=True, max_retries=3)
def process_analysis_task(self, job_id: str) -> None:
    """
    Celery task that replaces the old FastAPI BackgroundTasks.
    """
    db = db_session()
    repo = JobRepository(db)
    svc = JobService(repo)
    clock = JobClock(started_at_monotonic=time.monotonic())
    
    def broadcast_progress(data: dict):
        sio_mgr.emit("analysis_update", {"job_id": job_id, **data})

    try:
        job = repo.get_job(job_id)
        if job is None or job.upload_key is None:
            raise AppError(code=ErrorCode.DATABASE_ERROR, message="Missing job upload", job_id=job_id)

        clock.check_timeout(job_id=job_id)
        repo.update_status(job_id=job_id, state=JobState.RUNNING)
        repo.update_status(job_id=job_id, state=JobState.PROCESSING)
        svc.set_stage(job_id=job_id, stage=ProcessingStage.frame_extraction)
        
        broadcast_progress({"state": "RUNNING", "stage": "frame_extraction", "progress": 10})

        upload_path = _storage.resolve_upload_path(upload_key=job.upload_key)
        
        from ...image_pipeline import analyze_image_pipeline

        # Inject progress callback into pipeline if possible, or just mock stages
        # For now, we perform the analysis and broadcast at key points
        if job.media_type == "image":
            summary = analyze_image_pipeline(job_id=job_id, image_path=upload_path, job_svc=svc)
        else:
            summary = analyze_video_up_to_inference(job_id=job_id, video_path=upload_path, job_svc=svc)

        # Save results
        svc.set_stage(job_id=job_id, stage=ProcessingStage.saving_results)
        broadcast_progress({"state": "PROCESSING", "stage": "saving_results", "progress": 90})
        
        repo.save_result(
            job_id=job_id,
            final_score=summary.get("final_score"),
            confidence_label=summary.get("confidence_label"),
            summary=summary,
        )

        repo.update_status(job_id=job_id, state=JobState.COMPLETED, progress_percent=100)
        broadcast_progress({"state": "COMPLETED", "stage": "completed", "progress": 100, "result": summary})
        return
        
    except Exception as e:
        if self.request.retries < self.max_retries and is_transient_error(e):
            raise self.retry(exc=e)
            
        svc.fail(job_id=job_id, stage=ProcessingStage.saving_results, error=e)
        broadcast_progress({"state": "FAILED", "error": str(e)})
        try:
            _storage.delete_job_files(job_id=job_id, allow_when_active=True)
        except Exception:
            pass
    finally:
        db.close()


def _check_free_tier_quota(db, user_id: str) -> None:
    users = UserRepository(db)
    u = users.get_by_id(user_id)
    if u is None or u.tier != "free":
        return
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    n = users.count_jobs_since(user_id, start)
    if n >= int(settings.saas.free_tier_daily_uploads):
        raise AppError(
            code=ErrorCode.QUOTA_EXCEEDED,
            message=f"Free tier daily upload limit ({settings.saas.free_tier_daily_uploads}) reached. Try again tomorrow or upgrade.",
            details={"limit": settings.saas.free_tier_daily_uploads},
        )


@router.post("/analyze-video")
async def analyze_video(
    file: UploadFile,
    request: Request,
    user_id: str | None = Depends(resolve_bearer_user_id),
) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", "-")
    job_id = str(uuid.uuid4())
    log = get_logger("analyze.video", request_id=request_id, job_id=job_id, stage=ProcessingStage.validating.value)

    # Validate metadata (ext/mime/size/filename). Magic bytes validated during streaming save.
    meta = validate_upload_metadata(
        filename=file.filename or "",
        content_type=file.content_type or "",
        size_bytes=None,
        job_id=job_id,
    )
    if not meta.is_video:
        raise AppError(code=ErrorCode.INVALID_EXTENSION, message="Expected a video file", job_id=job_id)

    db = db_session()
    try:
        repo = JobRepository(db)
        if user_id:
            _check_free_tier_quota(db, user_id)
        repo.create_job(
            job_id=job_id,
            media_type="video",
            original_filename=meta.filename,
            original_content_type=meta.content_type,
            original_size_bytes=meta.size_bytes,
            user_id=user_id,
        )

        stored = _storage.save_upload(job_id=job_id, ext=meta.ext, fileobj=file.file)
        repo.set_upload_key(job_id, stored.key)
        repo.set_stored_size_bytes(job_id, stored.size_bytes)

        # Duration validation after upload (strict 3 minutes max).
        upload_path = _storage.resolve_upload_path(upload_key=stored.key)
        validate_video_duration(upload_path, job_id=job_id)

        process_analysis_task.delay(job_id)
        log.info("job_queued")
        return {
            "job_id": job_id,
            "state": JobState.QUEUED.value,
            "stage": ProcessingStage.validating.value,
            "progress_percent": 0,
            "result": None,
            "error": None,
        }
    except Exception as e:
        # Mark as FAILED and cleanup upload/artifacts if present.
        try:
            js = JobService(repo)
            js.fail(job_id=job_id, stage=ProcessingStage.validating, error=e)
        except Exception:
            pass
        try:
            _storage.delete_job_files(job_id=job_id, allow_when_active=True)
        except Exception:
            pass
        raise
    finally:
        db.close()


@router.post("/analyze-image")
async def analyze_image(
    file: UploadFile,
    request: Request,
    user_id: str | None = Depends(resolve_bearer_user_id),
) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", "-")
    job_id = str(uuid.uuid4())
    log = get_logger("analyze.image", request_id=request_id, job_id=job_id, stage=ProcessingStage.validating.value)

    meta = validate_upload_metadata(
        filename=file.filename or "",
        content_type=file.content_type or "",
        size_bytes=None,
        job_id=job_id,
    )
    if not meta.is_image:
        raise AppError(code=ErrorCode.INVALID_EXTENSION, message="Expected an image file", job_id=job_id)

    db = db_session()
    try:
        repo = JobRepository(db)
        if user_id:
            _check_free_tier_quota(db, user_id)
        repo.create_job(
            job_id=job_id,
            media_type="image",
            original_filename=meta.filename,
            original_content_type=meta.content_type,
            original_size_bytes=meta.size_bytes,
            user_id=user_id,
        )

        stored = _storage.save_upload(job_id=job_id, ext=meta.ext, fileobj=file.file)
        repo.set_upload_key(job_id, stored.key)
        repo.set_stored_size_bytes(job_id, stored.size_bytes)

        process_analysis_task.delay(job_id)
        log.info("job_queued")
        return {
            "job_id": job_id,
            "state": JobState.QUEUED.value,
            "stage": ProcessingStage.validating.value,
            "progress_percent": 0,
            "result": None,
            "error": None,
        }
    except Exception as e:
        try:
            js = JobService(repo)
            js.fail(job_id=job_id, stage=ProcessingStage.validating, error=e)
        except Exception:
            pass
        try:
            _storage.delete_job_files(job_id=job_id, allow_when_active=True)
        except Exception:
            pass
        raise
    finally:
        db.close()

