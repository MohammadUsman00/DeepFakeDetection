from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request, UploadFile

from ...db.repository import JobRepository
from ...db.session import db_session
from ...services.storage_service import StorageService
from ...services.job_service import JobClock, JobService, is_transient_error
from ...utils.enums import JobState, ProcessingStage
from ...utils.errors import AppError, ErrorCode
from ...utils.logging import get_logger
from ...utils.validation import validate_upload_metadata
from ...utils.video import validate_video_duration
from ...config import settings
from ...video.pipeline import analyze_video_up_to_inference
from ...utils.debug_mode import dbg_log


router = APIRouter()
_storage = StorageService()


def _stub_process_job(job_id: str) -> None:
    """
    Placeholder background task.
    Real pipeline will replace this in later steps.
    """

    max_retries = int(settings.job.max_retries)
    attempts = max(1, 1 + max_retries)
    for attempt in range(1, attempts + 1):
        # region agent log
        dbg_log(
            run_id="repro",
            hypothesis_id="H_BG_START",
            location="backend/app/api/routes/analyze.py:_stub_process_job:entry",
            message="Background task entered",
            data={"job_id": job_id, "attempt": attempt},
        )
        # endregion
        db = db_session()
        repo = JobRepository(db)
        svc = JobService(repo)
        clock = JobClock(started_at_monotonic=time.monotonic())
        try:
            job = repo.get_job(job_id)
            if job is None or job.upload_key is None:
                raise AppError(code=ErrorCode.DATABASE_ERROR, message="Missing job upload", job_id=job_id)

            clock.check_timeout(job_id=job_id)
            # Mark job active
            # region agent log
            dbg_log(
                run_id="repro",
                hypothesis_id="H_BG_STATUS",
                location="backend/app/api/routes/analyze.py:_stub_process_job:before_status",
                message="About to set RUNNING/PROCESSING + frame_extraction",
                data={"job_id": job_id},
            )
            # endregion
            repo.update_status(job_id=job_id, state=JobState.RUNNING)
            repo.update_status(job_id=job_id, state=JobState.PROCESSING)
            svc.set_stage(job_id=job_id, stage=ProcessingStage.frame_extraction)

            upload_path = _storage.resolve_upload_path(upload_key=job.upload_key)
            summary = analyze_video_up_to_inference(job_id=job_id, video_path=upload_path, job_svc=svc)

            # Save partial result (up to inference).
            svc.set_stage(job_id=job_id, stage=ProcessingStage.saving_results)
            repo.save_result(job_id=job_id, final_score=None, confidence_label=None, summary=summary)

            repo.update_status(job_id=job_id, state=JobState.COMPLETED, progress_percent=100)
            return
        except Exception as e:
            # region agent log
            dbg_log(
                run_id="repro",
                hypothesis_id="H_BG_EXC",
                location="backend/app/api/routes/analyze.py:_stub_process_job:except",
                message="Background task exception",
                data={"job_id": job_id, "type": type(e).__name__, "err": str(e), "attempt": attempt},
            )
            # endregion
            # Timeout flag if relevant
            if isinstance(e, AppError) and e.http_status == 408:
                try:
                    repo.set_timed_out(job_id, True)
                except Exception:
                    pass

            # Only retry transient errors.
            if attempt <= max_retries and is_transient_error(e):
                try:
                    repo.increment_retry_count(job_id)
                except Exception:
                    pass
                get_logger("job", job_id=job_id, stage="-").warning(
                    "job_retry",
                    extra={"retry_count": attempt, "timed_out": False},
                )
                continue

            svc.fail(job_id=job_id, stage=ProcessingStage.saving_results, error=e)
            try:
                _storage.delete_job_files(job_id=job_id, allow_when_active=True)
            except Exception:
                pass
            return
        finally:
            db.close()


@router.post("/analyze-video")
async def analyze_video(file: UploadFile, background_tasks: BackgroundTasks, request: Request) -> dict[str, Any]:
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
        # region agent log
        dbg_log(
            run_id="repro",
            hypothesis_id="H_ROUTE",
            location="backend/app/api/routes/analyze.py:analyze_video:before_create",
            message="Route reached before create_job",
            data={"job_id": job_id, "filename": meta.filename, "content_type": meta.content_type, "ext": meta.ext},
        )
        # endregion
        repo.create_job(
            job_id=job_id,
            media_type="video",
            original_filename=meta.filename,
            original_content_type=meta.content_type,
            original_size_bytes=meta.size_bytes,
        )

        stored = _storage.save_upload(job_id=job_id, ext=meta.ext, fileobj=file.file)
        repo.set_upload_key(job_id, stored.key)
        repo.set_stored_size_bytes(job_id, stored.size_bytes)

        # Duration validation after upload (strict 3 minutes max).
        upload_path = _storage.resolve_upload_path(upload_key=stored.key)
        validate_video_duration(upload_path, job_id=job_id)

        # region agent log
        dbg_log(
            run_id="repro",
            hypothesis_id="H_SCHEDULE",
            location="backend/app/api/routes/analyze.py:analyze_video:before_add_task",
            message="About to schedule background task",
            data={"job_id": job_id},
        )
        # endregion
        background_tasks.add_task(_stub_process_job, job_id)
        # region agent log
        dbg_log(
            run_id="repro",
            hypothesis_id="H_SCHEDULE",
            location="backend/app/api/routes/analyze.py:analyze_video:after_add_task",
            message="Scheduled background task",
            data={"job_id": job_id},
        )
        # endregion
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
async def analyze_image(file: UploadFile, background_tasks: BackgroundTasks, request: Request) -> dict[str, Any]:
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
        repo.create_job(
            job_id=job_id,
            media_type="image",
            original_filename=meta.filename,
            original_content_type=meta.content_type,
            original_size_bytes=meta.size_bytes,
        )

        stored = _storage.save_upload(job_id=job_id, ext=meta.ext, fileobj=file.file)
        repo.set_upload_key(job_id, stored.key)
        repo.set_stored_size_bytes(job_id, stored.size_bytes)

        background_tasks.add_task(_stub_process_job, job_id)
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

