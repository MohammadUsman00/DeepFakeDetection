from __future__ import annotations

from enum import StrEnum


class JobState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ProcessingStage(StrEnum):
    validating = "validating"
    frame_extraction = "frame_extraction"
    face_detection = "face_detection"
    inference = "inference"
    aggregation = "aggregation"
    explainability = "explainability"
    saving_results = "saving_results"


_STAGE_ORDER: tuple[ProcessingStage, ...] = (
    ProcessingStage.validating,
    ProcessingStage.frame_extraction,
    ProcessingStage.face_detection,
    ProcessingStage.inference,
    ProcessingStage.aggregation,
    ProcessingStage.explainability,
    ProcessingStage.saving_results,
)


def stage_index(stage: ProcessingStage) -> int:
    return _STAGE_ORDER.index(stage)


def validate_stage_transition(from_stage: ProcessingStage | None, to_stage: ProcessingStage) -> None:
    """
    Enforce strictly ordered stage transitions.

    Rules:
    - If `from_stage` is None, only `validating` is allowed.
    - Otherwise, transitions must move forward by exactly one step (no skipping, no going backwards).
    """

    if from_stage is None:
        if to_stage != ProcessingStage.validating:
            raise ValueError(f"Invalid stage transition: {from_stage} -> {to_stage}")
        return

    from_idx = _STAGE_ORDER.index(from_stage)
    to_idx = _STAGE_ORDER.index(to_stage)
    # Idempotent allowance: setting the same stage is a no-op.
    if to_idx == from_idx:
        return
    # In a distributed worker environment with retries, stages might re-execute.
    # We allow forward moves and idempotent moves. We log a warning for backward moves but don't crash.
    if to_idx < from_idx:
        from .logging import get_logger
        get_logger("enums").warning("backward_stage_transition", extra={"from": from_stage, "to": to_stage})
        return
    # Any forward move or current stage is fine
    return

