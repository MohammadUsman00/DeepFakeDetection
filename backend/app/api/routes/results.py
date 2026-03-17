from __future__ import annotations

from fastapi import APIRouter, Request

from ...db.repository import JobRepository
from ...db.session import db_session
from ...utils.errors import AppError, ErrorCode
from ...utils.logging import get_logger


router = APIRouter()


@router.get("/result/{job_id}")
async def get_result(job_id: str, request: Request) -> dict:
    request_id = getattr(request.state, "request_id", "-")
    log = get_logger("result", request_id=request_id, job_id=job_id, stage="result")

    db = db_session()
    try:
        repo = JobRepository(db)
        job = repo.get_job(job_id)
        if job is None:
            raise AppError(code=ErrorCode.DATABASE_ERROR, message="Job not found", job_id=job_id, http_status=404)

        result = repo.get_result_summary(job_id)
        payload = {
            "job_id": job.id,
            "media_type": job.media_type,
            "state": job.state,
            "stage": job.stage,
            "progress_percent": job.progress_percent,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "processing_started_at": (job.processing_started_at.isoformat() if job.processing_started_at else None),
            "processing_completed_at": (job.processing_completed_at.isoformat() if job.processing_completed_at else None),
            "metadata": {
                "original_filename": job.original_filename,
                "original_content_type": job.original_content_type,
                "original_size_bytes": job.original_size_bytes,
                "stored_size_bytes": job.stored_size_bytes,
            },
            "error": None,
            "result": None,
        }
        if job.error_code or job.error_message:
            payload["error"] = {"error_code": job.error_code, "message": job.error_message}
        if result is not None:
            payload["result"] = result

        log.info("result_fetched", extra={"has_result": result is not None})
        return payload
    finally:
        db.close()

