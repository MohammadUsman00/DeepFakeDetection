from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..utils.enums import JobState, ProcessingStage, validate_stage_transition
from ..utils.errors import AppError, ErrorCode
from .models import Job, Result


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _tx(db: Session):
    """
    Begin a transaction only if one isn't already active.

    SQLAlchemy 2.x sessions "autobegin" transactions; calling `begin()` inside an
    already-active transaction raises InvalidRequestError. This helper keeps DB
    operations atomic without nesting errors.
    """

    return nullcontext() if db.in_transaction() else db.begin()


@dataclass(frozen=True, slots=True)
class JobRecord:
    id: str
    media_type: str
    state: str
    stage: str
    progress_percent: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    upload_key: str | None
    original_filename: str | None
    original_content_type: str | None
    original_size_bytes: int | None
    stored_size_bytes: int | None
    processing_started_at: datetime | None
    processing_completed_at: datetime | None
    retry_count: int
    timed_out: int
    user_id: str | None


class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_job(
        self,
        *,
        job_id: str,
        media_type: str,
        original_filename: str | None = None,
        original_content_type: str | None = None,
        original_size_bytes: int | None = None,
        expires_at: datetime | None = None,
        user_id: str | None = None,
    ) -> JobRecord:
        now = _utcnow()
        if expires_at is None and settings.cleanup.enabled:
            expires_at = now + timedelta(seconds=settings.cleanup.ttl_seconds)

        def _sanitize(val: str | None, max_len: int) -> str | None:
            if val is None:
                return None
            s = str(val).strip()
            if s == "":
                return None
            return s[:max_len]

        job = Job(
            id=job_id,
            user_id=user_id,
            media_type=media_type,
            state=JobState.QUEUED.value,
            stage=ProcessingStage.validating.value,
            progress_percent=0,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            upload_key=None,
            original_filename=_sanitize(original_filename, 128),
            original_content_type=_sanitize(original_content_type, 64),
            original_size_bytes=original_size_bytes,
            stored_size_bytes=None,
            processing_started_at=None,
            processing_completed_at=None,
            retry_count=0,
            timed_out=0,
            error_code=None,
            error_message=None,
        )

        try:
            with _tx(self.db):
                self.db.add(job)
                self.db.flush()
            # SQLAlchemy 2.x "autobegin" keeps `in_transaction()` true; we still
            # need an explicit commit so other sessions (e.g., BackgroundTasks)
            # can observe the writes immediately.
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise AppError(code=ErrorCode.DATABASE_ERROR, message="Failed to create job", job_id=job_id) from e

        return self._to_record(job)

    def get_job(self, job_id: str) -> JobRecord | None:
        job = self.db.get(Job, job_id)
        return None if job is None else self._to_record(job)

    def set_upload_key(self, job_id: str, upload_key: str) -> None:
        try:
            with _tx(self.db):
                job = self.db.get(Job, job_id)
                if job is None:
                    raise AppError(code=ErrorCode.DATABASE_ERROR, message="Job not found", job_id=job_id)
                job.upload_key = upload_key
                job.updated_at = _utcnow()
                self.db.flush()
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise AppError(code=ErrorCode.DATABASE_ERROR, message="Failed to update upload key", job_id=job_id) from e

    def set_stored_size_bytes(self, job_id: str, stored_size_bytes: int) -> None:
        try:
            with _tx(self.db):
                job = self.db.get(Job, job_id)
                if job is None:
                    raise AppError(code=ErrorCode.DATABASE_ERROR, message="Job not found", job_id=job_id)
                job.stored_size_bytes = int(stored_size_bytes)
                job.updated_at = _utcnow()
                self.db.flush()
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise AppError(code=ErrorCode.DATABASE_ERROR, message="Failed to update stored size", job_id=job_id) from e

    def update_status(
        self,
        *,
        job_id: str,
        state: JobState | None = None,
        stage: ProcessingStage | None = None,
        progress_percent: int | None = None,
        error_code: ErrorCode | None = None,
        error_message: str | None = None,
    ) -> None:
        try:
            with _tx(self.db):
                job = self.db.get(Job, job_id)
                if job is None:
                    raise AppError(code=ErrorCode.DATABASE_ERROR, message="Job not found", job_id=job_id)

                if stage is not None:
                    from_stage = ProcessingStage(job.stage) if job.stage else None
                    validate_stage_transition(from_stage, stage)
                    job.stage = stage.value

                if state is not None:
                    job.state = state.value
                    if state in {JobState.RUNNING, JobState.PROCESSING} and job.processing_started_at is None:
                        job.processing_started_at = _utcnow()
                    if state in {JobState.COMPLETED, JobState.FAILED} and job.processing_completed_at is None:
                        job.processing_completed_at = _utcnow()

                if progress_percent is not None:
                    pct = int(progress_percent)
                    # Only COMPLETED is allowed to set 100%.
                    if pct >= 100 and (state is None or state != JobState.COMPLETED):
                        pct = 99
                    job.progress_percent = max(0, min(100, pct))

                if error_code is not None:
                    job.error_code = error_code.value
                    job.error_message = error_message

                job.updated_at = _utcnow()
                self.db.flush()
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise AppError(code=ErrorCode.DATABASE_ERROR, message="Failed to update job status", job_id=job_id) from e

    def increment_retry_count(self, job_id: str) -> None:
        try:
            with _tx(self.db):
                job = self.db.get(Job, job_id)
                if job is None:
                    raise AppError(code=ErrorCode.DATABASE_ERROR, message="Job not found", job_id=job_id)
                job.retry_count = int(job.retry_count or 0) + 1
                job.updated_at = _utcnow()
                self.db.flush()
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise AppError(code=ErrorCode.DATABASE_ERROR, message="Failed to increment retry count", job_id=job_id) from e

    def set_timed_out(self, job_id: str, timed_out: bool) -> None:
        try:
            with _tx(self.db):
                job = self.db.get(Job, job_id)
                if job is None:
                    raise AppError(code=ErrorCode.DATABASE_ERROR, message="Job not found", job_id=job_id)
                job.timed_out = 1 if timed_out else 0
                job.updated_at = _utcnow()
                self.db.flush()
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise AppError(code=ErrorCode.DATABASE_ERROR, message="Failed to set timeout flag", job_id=job_id) from e

    def save_result(
        self,
        *,
        job_id: str,
        final_score: float | None,
        confidence_label: str | None,
        summary: dict[str, Any] | None,
    ) -> None:
        payload = None if summary is None else json.dumps(summary, ensure_ascii=False)
        if payload is not None:
            size = len(payload.encode("utf-8"))
            if size > settings.result.max_summary_json_bytes:
                raise AppError(
                    code=ErrorCode.DATABASE_ERROR,
                    message="Result summary payload too large",
                    job_id=job_id,
                    details={"max_bytes": settings.result.max_summary_json_bytes, "actual_bytes": size},
                )

        try:
            with _tx(self.db):
                job = self.db.get(Job, job_id)
                if job is None:
                    raise AppError(code=ErrorCode.DATABASE_ERROR, message="Job not found", job_id=job_id)

                res = self.db.get(Result, job_id)
                now = _utcnow()
                if res is None:
                    res = Result(
                        job_id=job_id,
                        final_score=final_score,
                        confidence_label=confidence_label,
                        summary_json=payload,
                        created_at=now,
                    )
                    self.db.add(res)
                else:
                    res.final_score = final_score
                    res.confidence_label = confidence_label
                    res.summary_json = payload
                job.updated_at = now
                self.db.flush()
            self.db.commit()
        except AppError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise AppError(code=ErrorCode.DATABASE_ERROR, message="Failed to save result", job_id=job_id) from e

    def get_result_summary(self, job_id: str) -> dict[str, Any] | None:
        """
        Returns the result summary dict if present; otherwise None (e.g., job still running).
        """
        res = self.db.get(Result, job_id)
        if res is None or res.summary_json is None:
            return None
        try:
            return json.loads(res.summary_json)
        except Exception as e:
            raise AppError(code=ErrorCode.DATABASE_ERROR, message="Failed to parse stored result JSON", job_id=job_id) from e

    def list_jobs(self, limit: int = 50) -> list[JobRecord]:
        rows = self.db.execute(select(Job).order_by(Job.created_at.desc()).limit(limit)).scalars().all()
        return [self._to_record(j) for j in rows]

    def list_jobs_for_user(self, user_id: str, limit: int = 50) -> list[JobRecord]:
        rows = (
            self.db.execute(select(Job).where(Job.user_id == user_id).order_by(Job.created_at.desc()).limit(limit))
            .scalars()
            .all()
        )
        return [self._to_record(j) for j in rows]

    @staticmethod
    def _to_record(job: Job) -> JobRecord:
        return JobRecord(
            id=job.id,
            user_id=getattr(job, "user_id", None),
            media_type=job.media_type,
            state=job.state,
            stage=job.stage,
            progress_percent=job.progress_percent,
            error_code=job.error_code,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
            expires_at=job.expires_at,
            upload_key=job.upload_key,
            original_filename=job.original_filename,
            original_content_type=job.original_content_type,
            original_size_bytes=job.original_size_bytes,
            stored_size_bytes=job.stored_size_bytes,
            processing_started_at=job.processing_started_at,
            processing_completed_at=job.processing_completed_at,
            retry_count=job.retry_count,
            timed_out=job.timed_out,
        )

