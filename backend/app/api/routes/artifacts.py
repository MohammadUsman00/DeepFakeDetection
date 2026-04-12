from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse

from ...config import settings
from ...db.repository import JobRepository
from ...db.session import db_session
from ...services.auth_tokens import decode_access_token
from ...services.storage_service import StorageService
from ...utils.errors import AppError, ErrorCode
from ...utils.logging import get_logger


router = APIRouter()
_storage = StorageService()


def _viewer_id_from_request(request: Request, access_token: str | None) -> str | None:
    """Browser <img> cannot send Authorization; allow ?access_token= for same JWT."""
    if not settings.saas.require_auth:
        return None
    raw = request.headers.get("authorization")
    token: str | None = None
    if raw and raw.lower().startswith("bearer "):
        token = raw.split(" ", 1)[1].strip()
    elif access_token:
        token = access_token.strip()
    if not token:
        raise AppError(code=ErrorCode.UNAUTHORIZED, message="Authentication required for artifacts")
    try:
        data = decode_access_token(token)
        uid = data.get("sub")
        if not uid or not isinstance(uid, str):
            raise ValueError("no sub")
        return uid
    except AppError:
        raise
    except Exception as e:
        raise AppError(code=ErrorCode.INVALID_CREDENTIALS, message="Invalid or expired token") from e


@router.get("/artifacts/{job_id}/{name}")
async def get_artifact(
    job_id: str,
    name: str,
    request: Request,
    access_token: str | None = Query(None, description="JWT when using <img> (no Authorization header)"),
) -> FileResponse:
    request_id = getattr(request.state, "request_id", "-")
    log = get_logger("artifacts", request_id=request_id, job_id=job_id, stage="artifacts")

    db = db_session()
    try:
        repo = JobRepository(db)
        job = repo.get_job(job_id)
        if job is None:
            raise AppError(code=ErrorCode.DATABASE_ERROR, message="Job not found", job_id=job_id, http_status=404)

        viewer_id = _viewer_id_from_request(request, access_token)
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

