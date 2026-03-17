from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


_LOG_PATH = Path("debug-819d5b.log")
_SESSION_ID = "819d5b"


def dbg_log(*, run_id: str, hypothesis_id: str, location: str, message: str, data: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {
        "sessionId": _SESSION_ID,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    try:
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass

