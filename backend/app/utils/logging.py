from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


class _ContextDefaultsFilter(logging.Filter):
    """
    Ensures context fields always exist on log records.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "job_id"):
            record.job_id = "-"
        if not hasattr(record, "stage"):
            record.stage = "-"
        if not hasattr(record, "state"):
            record.state = "-"
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Optional structured context (e.g., job_id, stage) can be attached via LoggerAdapter.
        for key in ("request_id", "job_id", "stage", "state"):
            if hasattr(record, key):
                base[key] = getattr(record, key)

        # Common structured fields we want to preserve in logs (if present).
        for key in (
            "method",
            "path",
            "status_code",
            "elapsed_ms",
            "bytes",
            "key",
            "ip",
            "model_id",
            "batch_size",
            "max_frames",
            "effective_max_frames",
            "config",
            "error_code",
            "frames_read",
            "frames_corrupt",
            "frames_sampled",
            "sampling_mode",
            "count",
            "score",
            "bbox",
            "reason",
            "model_version",
            "device",
            "threads",
            "weights_loaded",
            "batch_size",
            "num_batches",
            "skipped_no_face",
            "skipped_error",
            "processing_ms",
            "warnings",
            "label",
            "low_confidence",
            "frames_used_for_score",
            "top_k_count",
            "trimmed_count",
            "final_score",
            "frame_index",
            "alpha",
            "class_index",
            "requested",
            "generated",
            "failures",
        ):
            if hasattr(record, key):
                base[key] = getattr(record, key)

        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)

        try:
            return json.dumps(base, ensure_ascii=False)
        except Exception:
            # If JSON serialization fails for any reason, fall back to a readable line.
            parts = [
                base.get("ts", ""),
                base.get("level", ""),
                base.get("logger", ""),
                base.get("request_id", "-"),
                base.get("job_id", "-"),
                base.get("stage", "-"),
                base.get("msg", ""),
            ]
            return " | ".join(str(p) for p in parts if p is not None)


def configure_logging() -> None:
    """
    Configure application-wide logging.

    Env:
    - LOG_LEVEL: DEBUG|INFO|WARNING|ERROR (default INFO)
    - LOG_FORMAT: json|text (default json)
    """

    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = os.getenv("LOG_FORMAT", "json").strip().lower()
    handler = logging.StreamHandler(sys.stdout)
    if fmt == "text":
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
    else:
        handler.setFormatter(JsonFormatter())
    handler.addFilter(_ContextDefaultsFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)


class ContextLogger(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = kwargs.get("extra") or {}
        extra = {**extra, **self.extra}
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str, **context: Any) -> ContextLogger:
    """
    Return a logger with optional structured context.

    Recommended fields:
    - request_id
    - job_id
    - stage
    - state
    """

    return ContextLogger(logging.getLogger(name), context)

