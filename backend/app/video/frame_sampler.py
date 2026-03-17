from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2

from ..config import settings
from ..utils.errors import AppError, ErrorCode
from ..utils.logging import get_logger


@dataclass(frozen=True, slots=True)
class SampledFrame:
    """
    A single sampled video frame.

    - frame_bgr: OpenCV BGR image (numpy ndarray)
    """

    frame_index: int
    timestamp_ms: int
    frame_bgr: object


def _fps_is_reliable(fps: float) -> bool:
    if fps <= 0:
        return False
    return settings.video.fps_metadata_min <= fps <= settings.video.fps_metadata_max


def _downscale_if_needed(frame_bgr):
    max_w = int(settings.video.downscale_max_width)
    if max_w <= 0:
        return frame_bgr
    try:
        h, w = frame_bgr.shape[:2]
    except Exception:
        return frame_bgr
    if w <= max_w:
        return frame_bgr
    scale = max_w / float(w)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    if new_w <= 0 or new_h <= 0:
        return frame_bgr
    return cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)


def iter_sampled_frames(video_path: Path) -> Iterator[SampledFrame]:
    """
    Streaming frame sampler.

    Constraints:
    - ~1 frame per second (configurable via VIDEO_SAMPLE_FPS)
    - cap max yielded frames at VIDEO_MAX_FRAMES (strict)
    - fallback to timestamp-based sampling if FPS metadata is unreliable
    """

    log = get_logger("frame_sampler", stage="frame_extraction")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise AppError(
            code=ErrorCode.VIDEO_DECODE_ERROR,
            message="Could not open video",
            details={"path": str(video_path)},
        )

    frames_read = 0
    frames_corrupt = 0
    frames_sampled = 0
    sampling_mode = "timestamp"

    try:
        max_frames = int(settings.video.max_frames)
        sample_fps = float(settings.video.sample_fps)
        sample_period_ms = int(round(1000.0 / max(0.001, sample_fps)))

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        use_fps = _fps_is_reliable(fps)
        sampling_mode = "fps" if use_fps else "timestamp"

        yielded = 0
        read_index = 0
        next_sample_ms: int | None = None
        last_ts_ms = -1

        while yielded < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            frames_read += 1
            if frame is None or getattr(frame, "size", 0) == 0:
                frames_corrupt += 1
                read_index += 1
                continue

            frame = _downscale_if_needed(frame)

            # Prefer CAP_PROP_POS_MSEC for accurate timestamps.
            ts_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
            if ts_ms <= 0 and use_fps and fps > 0:
                # Fallback if POS_MSEC isn't available.
                ts_ms = int(round((read_index / fps) * 1000.0))
            if ts_ms < last_ts_ms:
                # Non-monotonic timestamps can happen; fall back to best effort.
                ts_ms = max(last_ts_ms, ts_ms)
            last_ts_ms = ts_ms

            # Time-based accumulation avoids drift even with varying frame times.
            if next_sample_ms is None:
                next_sample_ms = ts_ms

            if ts_ms >= next_sample_ms:
                yield SampledFrame(frame_index=read_index, timestamp_ms=ts_ms, frame_bgr=frame)
                yielded += 1
                frames_sampled += 1
                # Prevent drift: advance by fixed period from the scheduled time.
                next_sample_ms = next_sample_ms + sample_period_ms
                while next_sample_ms <= ts_ms:
                    next_sample_ms += sample_period_ms
            read_index += 1

        # Ensure at least one frame for very short videos (if we read any non-corrupt frames).
        if frames_sampled == 0 and frames_read > frames_corrupt:
            try:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame0 = cap.read()
                if ok and frame0 is not None and getattr(frame0, "size", 0) != 0:
                    frame0 = _downscale_if_needed(frame0)
                    ts0 = int(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
                    yield SampledFrame(frame_index=0, timestamp_ms=ts0, frame_bgr=frame0)
                    frames_sampled += 1
            except Exception:
                pass
    finally:
        try:
            cap.release()
        finally:
            log.info(
                "sampling_summary",
                extra={
                    "path": str(video_path),
                    "frames_read": frames_read,
                    "frames_corrupt": frames_corrupt,
                    "frames_sampled": frames_sampled,
                    "sampling_mode": sampling_mode,
                },
            )

