from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import settings
from .errors import AppError, ErrorCode
from .logging import get_logger


@dataclass(frozen=True, slots=True)
class UploadMeta:
    filename: str
    ext: str
    content_type: str
    size_bytes: int | None
    is_video: bool
    is_image: bool


def extract_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext


_DANGEROUS_SUFFIXES = {
    "exe",
    "bat",
    "cmd",
    "com",
    "ps1",
    "vbs",
    "js",
    "jar",
    "msi",
    "scr",
    "sh",
}


def validate_filename(filename: str, *, job_id: str | None = None) -> None:
    if len(filename) > settings.file.max_filename_chars:
        raise AppError(
            code=ErrorCode.FILENAME_TOO_LONG,
            message="Filename too long",
            job_id=job_id,
            details={"max_chars": settings.file.max_filename_chars},
        )

    p = Path(filename)
    suffixes = [s.lstrip(".").lower() for s in p.suffixes if s]
    if not suffixes:
        raise AppError(code=ErrorCode.INVALID_EXTENSION, message="Missing file extension", job_id=job_id)

    # Prevent double-extension tricks like "file.exe.mp4"
    if len(suffixes) >= 2 and any(s in _DANGEROUS_SUFFIXES for s in suffixes[:-1]):
        raise AppError(
            code=ErrorCode.DOUBLE_EXTENSION,
            message="Suspicious double-extension filename",
            job_id=job_id,
            details={"suffixes": suffixes},
        )


def validate_extension(filename: str, *, content_type: str, size_bytes: int | None, job_id: str | None = None) -> UploadMeta:
    validate_filename(filename, job_id=job_id)

    ext = extract_extension(filename)

    allowed_video = set(settings.file.allowed_video_ext)
    allowed_image = set(settings.file.allowed_image_ext)
    if ext not in allowed_video and ext not in allowed_image:
        raise AppError(
            code=ErrorCode.INVALID_EXTENSION,
            message="Unsupported file extension",
            job_id=job_id,
            details={"ext": ext, "allowed_video_ext": sorted(allowed_video), "allowed_image_ext": sorted(allowed_image)},
        )

    return UploadMeta(
        filename=filename,
        ext=ext,
        content_type=(content_type or "").lower().strip(),
        size_bytes=size_bytes,
        is_video=ext in allowed_video,
        is_image=ext in allowed_image,
    )


def validate_size_bytes(size_bytes: int | None, *, job_id: str | None = None) -> None:
    """
    Optional size validation.

    Note: for multipart uploads, size is often unknown before streaming to disk.
    In that case we rely on the storage streaming limit + non-empty enforcement.
    """

    if size_bytes is None:
        return
    if size_bytes < 0:
        raise AppError(code=ErrorCode.STORAGE_ERROR, message="Invalid file size", job_id=job_id, http_status=400)
    if size_bytes == 0:
        raise AppError(code=ErrorCode.EMPTY_FILE, message="Empty file upload", job_id=job_id)
    if size_bytes > settings.file.max_upload_bytes:
        raise AppError(
            code=ErrorCode.FILE_TOO_LARGE,
            message="Upload exceeds maximum allowed size",
            job_id=job_id,
            details={"max_bytes": settings.file.max_upload_bytes},
            http_status=413,
        )


def validate_magic_bytes(prefix: bytes, *, ext: str, job_id: str | None = None) -> None:
    """
    Lightweight content validation (defense-in-depth).

    This does not guarantee the file is fully valid, but it catches obvious mismatches.
    """

    ext_norm = ext.lower().lstrip(".")
    if len(prefix) < 12:
        raise AppError(code=ErrorCode.INVALID_MAGIC_BYTES, message="File too small", job_id=job_id)

    if ext_norm == "png":
        if not prefix.startswith(b"\x89PNG\r\n\x1a\n"):
            raise AppError(code=ErrorCode.INVALID_MAGIC_BYTES, message="File content is not PNG", job_id=job_id)
        return
    if ext_norm in {"jpg", "jpeg"}:
        if not prefix.startswith(b"\xff\xd8\xff"):
            raise AppError(code=ErrorCode.INVALID_MAGIC_BYTES, message="File content is not JPEG", job_id=job_id)
        return
    if ext_norm in settings.file.allowed_video_ext:
        if prefix[4:8] != b"ftyp":
            raise AppError(code=ErrorCode.INVALID_MAGIC_BYTES, message="File content is not MP4/MOV", job_id=job_id)
        return


def validate_mime_type(meta: UploadMeta, *, job_id: str | None = None) -> None:
    ct = (meta.content_type or "").lower().strip()
    if meta.is_video:
        allowed = set(settings.file.allowed_video_mime)
    else:
        allowed = set(settings.file.allowed_image_mime)
    if ct == "" or ct not in allowed:
        raise AppError(
            code=ErrorCode.INVALID_MIME_TYPE,
            message="Unsupported MIME type",
            job_id=job_id,
            details={"content_type": ct, "allowed": sorted(allowed)},
        )


def validate_upload_metadata(
    *,
    filename: str,
    content_type: str,
    size_bytes: int | None,
    job_id: str | None = None,
) -> UploadMeta:
    """
    Validates metadata (filename/ext/mime/size). Magic-bytes validation is handled
    by the storage service during streaming.
    """

    log = get_logger("validation", job_id=job_id or "-", stage="validating")
    try:
        validate_size_bytes(size_bytes, job_id=job_id)
        meta = validate_extension(filename, content_type=content_type, size_bytes=size_bytes, job_id=job_id)
        validate_mime_type(meta, job_id=job_id)
        return meta
    except AppError as e:
        log.warning("validation_failed", extra={"error_code": e.code.value, "reason": e.message})
        raise

