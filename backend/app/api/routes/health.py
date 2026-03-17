from __future__ import annotations

from fastapi import APIRouter

from ...config import settings


router = APIRouter()


@router.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "deepfake-detection-backend",
        "version": "0.0.0",
        "model_id": settings.inference.model_id,
    }

