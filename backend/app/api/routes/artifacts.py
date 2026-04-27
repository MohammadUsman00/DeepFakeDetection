from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from ...config import settings
from ...db.repository import JobRepository
from ...db.session import db_session
from ..deps import resolve_bearer_user_id
from ...services.storage_service import StorageService
from ...utils.errors import AppError, ErrorCode
from ...utils.logging import get_logger


router = APIRouter()
_storage = StorageService()


@router.get("/artifacts/{job_id}/{name}")
async def get_artifact(
    job_id: str,
    name: str,
    request: Request,
    viewer_id: str | None = Depends(resolve_bearer_user_id),
) -> FileResponse:
    request_id = getattr(request.state, "request_id", "-")
    log = get_logger("artifacts", request_id=request_id, job_id=job_id, stage="artifacts")

    db = db_session()
    try:
        repo = JobRepository(db)
        job = repo.get_job(job_id)
        if job is None:
            raise AppError(code=ErrorCode.DATABASE_ERROR, message="Job not found", job_id=job_id, http_status=404)

        if settings.saas.require_auth and viewer_id is None:
            raise AppError(code=ErrorCode.UNAUTHORIZED, message="Authentication required for artifacts")
        if job.user_id and settings.saas.require_auth and viewer_id != job.user_id:
            raise AppError(code=ErrorCode.DATABASE_ERROR, message="Job not found", job_id=job_id, http_status=404)

        path = _storage.resolve_artifact_path(job_id=job_id, name=name)
        if not path.exists():
            raise AppError(code=ErrorCode.STORAGE_ERROR, message="Artifact not found", job_id=job_id, http_status=404)

        log.info("artifact_served", extra={"key": f"artifacts/{job_id}/{name}"})
        media_type, _ = mimetypes.guess_type(str(path))
        resp = FileResponse(path, media_type=media_type or "application/octet-stream")
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp
    finally:
        db.close()

