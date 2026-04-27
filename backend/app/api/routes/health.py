from __future__ import annotations

import os

from fastapi import APIRouter, Response
from sqlalchemy import text

from ...config import settings
from ...db.session import engine


router = APIRouter()


@router.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "deepfake-detection-backend",
        "version": "0.0.0",
        "model_id": settings.inference.model_id,
    }


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def health_ready(response: Response) -> dict[str, object]:
    checks: dict[str, str] = {}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "fail"
        response.status_code = 503

    broker = os.getenv("CELERY_BROKER_URL", "").strip()
    if os.getenv("REQUIRE_REDIS_FOR_READY", "").lower() in ("1", "true", "yes") and broker.startswith("redis"):
        try:
            import redis

            r = redis.from_url(broker, socket_connect_timeout=2, socket_timeout=2)
            r.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "fail"
            response.status_code = 503

    ok = all(v == "ok" for v in checks.values())
    return {"status": "ready" if ok else "not_ready", "checks": checks}

