from __future__ import annotations

import time
from dataclasses import dataclass

from ..config import settings
from ..db.repository import JobRepository
from ..utils.enums import JobState, ProcessingStage, stage_index
from ..utils.errors import AppError, ErrorCode
from ..utils.logging import get_logger


STAGE_PROGRESS: dict[ProcessingStage, int] = {
    ProcessingStage.validating: 0,
    ProcessingStage.frame_extraction: 10,
    ProcessingStage.face_detection: 30,
    ProcessingStage.inference: 55,
    ProcessingStage.aggregation: 75,
    ProcessingStage.explainability: 90,
    ProcessingStage.saving_results: 95,
}


def progress_for_stage(stage: ProcessingStage) -> int:
    return STAGE_PROGRESS.get(stage, 0)


@dataclass(frozen=True, slots=True)
class JobClock:
    started_at_monotonic: float

    def check_timeout(self, *, job_id: str) -> None:
        if settings.job.timeout_seconds <= 0:
            return
        elapsed = time.monotonic() - self.started_at_monotonic
        if elapsed > settings.job.timeout_seconds:
            raise AppError(
                code=ErrorCode.INTERNAL_ERROR,
                message="Job timed out",
                job_id=job_id,
                details={"timeout_seconds": settings.job.timeout_seconds, "elapsed_seconds": elapsed},
                http_status=408,
            )


class JobService:
    def __init__(self, repo: JobRepository):
        self.repo = repo

    def set_stage(
        self,
        *,
        job_id: str,
        stage: ProcessingStage,
        state: JobState | None = None,
        retry_count: int = 0,
        timed_out: bool = False,
    ) -> None:
        # Idempotency: don't re-run a stage that's already completed.
        current = self.repo.get_job(job_id)
        if current is not None:
            try:
                cur_stage = ProcessingStage(current.stage)
                if stage_index(cur_stage) > stage_index(stage):
                    return
            except Exception:
                pass

        pct = progress_for_stage(stage)
        get_logger("job", job_id=job_id, stage=stage.value).info("stage_transition", extra={"progress_percent": pct})
        self.repo.update_status(job_id=job_id, stage=stage, state=state, progress_percent=pct)

    def update_progress(
        self,
        *,
        job_id: str,
        stage: ProcessingStage,
        within_stage_percent: float,
    ) -> None:
        """
        Allows gradual progress updates within a stage.

        within_stage_percent: 0..1 (clamped)
        """

        within = max(0.0, min(1.0, float(within_stage_percent)))
        base = progress_for_stage(stage)
        # Next stage base defines upper bound (exclusive-ish) to avoid jumping ahead.
        next_base = 99
        stage_order = list(STAGE_PROGRESS.keys())
        if stage in stage_order:
            idx = stage_order.index(stage)
            if idx + 1 < len(stage_order):
                next_base = progress_for_stage(stage_order[idx + 1])
        span = max(1, next_base - base)
        pct = base + int(within * span)
        self.repo.update_status(job_id=job_id, progress_percent=pct)

    def fail(self, *, job_id: str, stage: ProcessingStage | None, error: AppError | Exception) -> None:
        if isinstance(error, AppError):
            code = error.code
            msg = error.message
        else:
            code = ErrorCode.INTERNAL_ERROR
            msg = str(error)
        get_logger("job", job_id=job_id, stage=(stage.value if stage else "-")).warning(
            "job_failed",
            extra={"error_code": code.value},
        )
        self.repo.update_status(
            job_id=job_id,
            state=JobState.FAILED,
            error_code=code,
            error_message=(f"[{stage.value}] {msg}" if stage else msg),
        )


def is_transient_error(err: Exception) -> bool:
    if not isinstance(err, AppError):
        return True
    # Transient: infra/IO-ish errors; not validation or media format errors.
    return err.code in {
        ErrorCode.STORAGE_ERROR,
        ErrorCode.DATABASE_ERROR,
        ErrorCode.INTERNAL_ERROR,
        ErrorCode.MODEL_NOT_AVAILABLE,
    }

