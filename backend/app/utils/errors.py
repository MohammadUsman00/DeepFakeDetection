from __future__ import annotations

from enum import StrEnum
from typing import Any

from .enums import ProcessingStage


class ErrorCode(StrEnum):
    # Validation
    INVALID_EXTENSION = "INVALID_EXTENSION"
    INVALID_MIME_TYPE = "INVALID_MIME_TYPE"
    INVALID_MAGIC_BYTES = "INVALID_MAGIC_BYTES"
    DOUBLE_EXTENSION = "DOUBLE_EXTENSION"
    FILENAME_TOO_LONG = "FILENAME_TOO_LONG"
    EMPTY_FILE = "EMPTY_FILE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    VIDEO_TOO_LONG = "VIDEO_TOO_LONG"

    # Media processing
    VIDEO_DECODE_ERROR = "VIDEO_DECODE_ERROR"
    IMAGE_DECODE_ERROR = "IMAGE_DECODE_ERROR"

    # Face detection / pipeline outcomes
    NO_FACE_DETECTED = "NO_FACE_DETECTED"
    INSUFFICIENT_FACE_FRAMES = "INSUFFICIENT_FACE_FRAMES"

    # ML
    MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"
    INFERENCE_ERROR = "INFERENCE_ERROR"
    EXPLAINABILITY_ERROR = "EXPLAINABILITY_ERROR"

    # Storage / DB
    STORAGE_ERROR = "STORAGE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"

    # Auth / SaaS
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    EMAIL_IN_USE = "EMAIL_IN_USE"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"

    # Catch-all
    INTERNAL_ERROR = "INTERNAL_ERROR"


ERROR_CODE_HTTP_STATUS: dict[ErrorCode, int] = {
    # Validation
    ErrorCode.INVALID_EXTENSION: 415,
    ErrorCode.INVALID_MIME_TYPE: 415,
    ErrorCode.INVALID_MAGIC_BYTES: 415,
    ErrorCode.DOUBLE_EXTENSION: 400,
    ErrorCode.FILENAME_TOO_LONG: 400,
    ErrorCode.EMPTY_FILE: 400,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.VIDEO_TOO_LONG: 422,
    # Media processing
    ErrorCode.VIDEO_DECODE_ERROR: 422,
    ErrorCode.IMAGE_DECODE_ERROR: 422,
    # Face detection / pipeline outcomes
    ErrorCode.NO_FACE_DETECTED: 422,
    ErrorCode.INSUFFICIENT_FACE_FRAMES: 422,
    # ML
    ErrorCode.MODEL_NOT_AVAILABLE: 503,
    ErrorCode.INFERENCE_ERROR: 500,
    ErrorCode.EXPLAINABILITY_ERROR: 500,
    # Storage / DB
    ErrorCode.STORAGE_ERROR: 500,
    ErrorCode.DATABASE_ERROR: 500,
    # Auth
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.INVALID_CREDENTIALS: 401,
    ErrorCode.EMAIL_IN_USE: 409,
    ErrorCode.QUOTA_EXCEEDED: 429,
    # Catch-all
    ErrorCode.INTERNAL_ERROR: 500,
}


class AppError(Exception):
    """
    Standard application exception that can be mapped to API responses.

    We keep it framework-agnostic here; FastAPI integration will be done later.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        job_id: str | None = None,
        stage: ProcessingStage | None = None,
        details: dict[str, Any] | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.job_id = job_id
        self.stage = stage
        self.details = details or {}
        self.http_status = http_status if http_status is not None else ERROR_CODE_HTTP_STATUS.get(code, 500)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"error_code": self.code.value, "message": self.message}
        if self.job_id is not None:
            payload["job_id"] = self.job_id
        if self.stage is not None:
            payload["stage"] = self.stage.value
        if self.details:
            payload["details"] = self.details
        return payload

