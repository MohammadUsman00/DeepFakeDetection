from __future__ import annotations

from pathlib import Path

import cv2

from ..config import settings
from .errors import AppError, ErrorCode


def get_video_duration_seconds(path: Path, *, job_id: str | None = None) -> float:
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise AppError(code=ErrorCode.VIDEO_DECODE_ERROR, message="Could not open video", job_id=job_id)
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        if fps > 0 and frames > 0:
            return float(frames / fps)
        # Fallback: seek to end and read timestamp if available.
        cap.set(cv2.CAP_PROP_POS_AVI_RATIO, 1)
        ms = cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0
        return float(ms / 1000.0)
    finally:
        cap.release()


def validate_video_duration(path: Path, *, job_id: str | None = None) -> float:
    duration = get_video_duration_seconds(path, job_id=job_id)
    if duration > settings.video.max_duration_seconds:
        raise AppError(
            code=ErrorCode.VIDEO_TOO_LONG,
            message="Video exceeds maximum duration",
            job_id=job_id,
            details={"max_seconds": settings.video.max_duration_seconds, "duration_seconds": duration},
        )
    return duration

