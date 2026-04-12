from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ...db.repository import JobRepository
from ...db.session import db_session
from ..deps import require_token_user_id

router = APIRouter()


@router.get("/jobs/me")
def list_my_jobs(user_id: str = Depends(require_token_user_id), limit: int = 50) -> dict[str, Any]:
    db = db_session()
    try:
        repo = JobRepository(db)
        rows = repo.list_jobs_for_user(user_id, limit=min(max(limit, 1), 100))
        return {
            "jobs": [
                {
                    "job_id": r.id,
                    "media_type": r.media_type,
                    "state": r.state,
                    "stage": r.stage,
                    "progress_percent": r.progress_percent,
                    "created_at": r.created_at.isoformat(),
                    "original_filename": r.original_filename,
                }
                for r in rows
            ]
        }
    finally:
        db.close()
