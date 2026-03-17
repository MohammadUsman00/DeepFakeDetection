from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from ...db.repository import JobRepository
from ...db.session import db_session
from ...services.storage_service import StorageService
from ...utils.errors import AppError, ErrorCode
from ...utils.logging import get_logger


router = APIRouter()
_storage = StorageService()


@router.get("/artifacts/{job_id}/{name}")
async def get_artifact(job_id: str, name: str, request: Request) -> FileResponse:
    request_id = getattr(request.state, "request_id", "-")
    log = get_logger("artifacts", request_id=request_id, job_id=job_id, stage="artifacts")

    db = db_session()
    try:
        repo = JobRepository(db)
        job = repo.get_job(job_id)
        if job is None:
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

