from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from ..config import settings
from ..utils.errors import AppError, ErrorCode
from ..utils.logging import get_logger
from ..utils.validation import validate_magic_bytes


_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
_CHUNK_SIZE = 1024 * 1024


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def _validate_safe_name(name: str) -> None:
    if not _SAFE_NAME_RE.match(name):
        raise AppError(
            code=ErrorCode.STORAGE_ERROR,
            message="Invalid filename",
            details={"name": name},
            http_status=400,
        )


def _dir_size_bytes(root: Path) -> int:
    total = 0
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            try:
                total += (Path(dirpath) / fn).stat().st_size
            except Exception:
                continue
    return total


def _looks_like_png(prefix: bytes) -> bool:
    return prefix.startswith(b"\x89PNG\r\n\x1a\n")


def _looks_like_jpeg(prefix: bytes) -> bool:
    return prefix.startswith(b"\xff\xd8\xff")


def _looks_like_mp4_mov(prefix: bytes) -> bool:
    # ISO base media file format: size(4) + 'ftyp'(4) + brand...
    return len(prefix) >= 12 and prefix[4:8] == b"ftyp"


@dataclass(frozen=True, slots=True)
class StoredObject:
    """
    Opaque storage reference returned to the rest of the system.
    We avoid leaking absolute filesystem paths outside this service.
    """

    key: str
    size_bytes: int


class StorageService:
    def __init__(self) -> None:
        self._data_dir = settings.storage.data_dir
        self._uploads_dir = settings.storage.uploads_dir
        self._artifacts_dir = settings.storage.artifacts_dir
        self._log = get_logger("storage", stage="storage")

        _ensure_dir(self._data_dir)
        _ensure_dir(self._uploads_dir)
        _ensure_dir(self._artifacts_dir)

    # -------------------------
    # Uploads
    # -------------------------
    def save_upload(self, *, job_id: str, ext: str, fileobj: BinaryIO) -> StoredObject:
        ext_norm = ext.lower().lstrip(".")
        if ext_norm not in (*settings.file.allowed_video_ext, *settings.file.allowed_image_ext):
            raise AppError(
                code=ErrorCode.INVALID_EXTENSION,
                message="Unsupported file extension",
                job_id=job_id,
                details={"ext": ext_norm},
            )

        filename = f"{job_id}.{ext_norm}"
        _validate_safe_name(filename)
        dest = (self._uploads_dir / filename).resolve()

        if not _is_within(dest, self._uploads_dir):
            raise AppError(code=ErrorCode.STORAGE_ERROR, message="Invalid upload destination", job_id=job_id)

        if dest.exists() and not settings.storage.allow_overwrite_uploads:
            raise AppError(
                code=ErrorCode.STORAGE_ERROR,
                message="Upload already exists",
                job_id=job_id,
                http_status=409,
            )

        quota = settings.storage.total_quota_bytes
        base_usage = _dir_size_bytes(self._data_dir) if quota > 0 else 0

        # Magic-bytes validation (defense-in-depth).
        prefix = fileobj.read(64)
        if not prefix:
            raise AppError(code=ErrorCode.EMPTY_FILE, message="Empty upload", job_id=job_id, http_status=400)
        validate_magic_bytes(prefix, ext=ext_norm, job_id=job_id)

        size = 0
        try:
            with open(dest, "wb") as f:
                f.write(prefix)
                size += len(prefix)
                if size > settings.file.max_upload_bytes:
                    raise AppError(
                        code=ErrorCode.FILE_TOO_LARGE,
                        message="Upload exceeds maximum allowed size",
                        job_id=job_id,
                        details={"max_bytes": settings.file.max_upload_bytes},
                        http_status=413,
                    )
                if quota > 0 and base_usage + size > quota:
                    raise AppError(
                        code=ErrorCode.STORAGE_ERROR,
                        message="Storage quota exceeded",
                        job_id=job_id,
                        details={"quota_bytes": quota},
                        http_status=507,
                    )
                while True:
                    chunk = fileobj.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > settings.file.max_upload_bytes:
                        raise AppError(
                            code=ErrorCode.FILE_TOO_LARGE,
                            message="Upload exceeds maximum allowed size",
                            job_id=job_id,
                            details={"max_bytes": settings.file.max_upload_bytes},
                            http_status=413,
                        )
                    if quota > 0 and base_usage + size > quota:
                        raise AppError(
                            code=ErrorCode.STORAGE_ERROR,
                            message="Storage quota exceeded",
                            job_id=job_id,
                            details={"quota_bytes": quota},
                            http_status=507,
                        )
                    f.write(chunk)
        except AppError:
            # Best-effort cleanup on failure.
            try:
                if dest.exists():
                    dest.unlink()
            except Exception:
                pass
            raise
        except Exception as e:
            try:
                if dest.exists():
                    dest.unlink()
            except Exception:
                pass
            raise AppError(code=ErrorCode.STORAGE_ERROR, message="Failed to save upload", job_id=job_id) from e

        # Defense-in-depth: verify size on disk matches what we wrote.
        try:
            on_disk = dest.stat().st_size
        except Exception as e:
            raise AppError(code=ErrorCode.STORAGE_ERROR, message="Failed to stat uploaded file", job_id=job_id) from e
        if on_disk != size:
            try:
                dest.unlink(missing_ok=True)
            except Exception:
                pass
            raise AppError(
                code=ErrorCode.STORAGE_ERROR,
                message="Upload size verification failed",
                job_id=job_id,
                details={"expected": size, "actual": on_disk},
            )

        self._log.info("upload_saved", extra={"job_id": job_id, "bytes": size, "key": f"uploads/{filename}"})

        # Storage key is a relative, safe reference.
        return StoredObject(key=f"uploads/{filename}", size_bytes=size)

    def resolve_upload_path(self, *, upload_key: str) -> Path:
        # upload_key is expected like "uploads/<job_id>.<ext>"
        rel = Path(upload_key)
        dest = (self._data_dir / rel).resolve()
        if not _is_within(dest, self._uploads_dir):
            raise AppError(code=ErrorCode.STORAGE_ERROR, message="Invalid upload key", details={"key": upload_key})
        return dest

    # -------------------------
    # Artifacts
    # -------------------------
    def ensure_artifact_dir(self, *, job_id: str) -> Path:
        job_dir = (self._artifacts_dir / job_id).resolve()
        if not _is_within(job_dir, self._artifacts_dir):
            raise AppError(code=ErrorCode.STORAGE_ERROR, message="Invalid artifact directory", job_id=job_id)
        _ensure_dir(job_dir)
        return job_dir

    def save_artifact_bytes(self, *, job_id: str, name: str, data: bytes) -> StoredObject:
        _validate_safe_name(name)
        job_dir = self.ensure_artifact_dir(job_id=job_id)
        dest = (job_dir / name).resolve()
        if not _is_within(dest, job_dir):
            raise AppError(code=ErrorCode.STORAGE_ERROR, message="Invalid artifact path", job_id=job_id)
        try:
            with open(dest, "wb") as f:
                f.write(data)
        except Exception as e:
            raise AppError(code=ErrorCode.STORAGE_ERROR, message="Failed to write artifact", job_id=job_id) from e
        self._log.info("artifact_saved", extra={"job_id": job_id, "bytes": len(data), "key": f"artifacts/{job_id}/{name}"})
        return StoredObject(key=f"artifacts/{job_id}/{name}", size_bytes=len(data))

    def heatmap_overlay_name(self, frame_index: int) -> str:
        if frame_index < 0 or frame_index >= settings.video.max_frames:
            raise AppError(
                code=ErrorCode.STORAGE_ERROR,
                message="Invalid frame index for heatmap naming",
                details={"frame_index": frame_index},
            )
        return f"heatmap_frame_{frame_index}.png"

    def save_heatmap_overlay(self, *, job_id: str, frame_index: int, png_bytes: bytes) -> StoredObject:
        name = self.heatmap_overlay_name(frame_index)
        return self.save_artifact_bytes(job_id=job_id, name=name, data=png_bytes)

    def resolve_artifact_path(self, *, job_id: str, name: str) -> Path:
        _validate_safe_name(name)
        job_dir = (self._artifacts_dir / job_id).resolve()
        dest = (job_dir / name).resolve()
        if not _is_within(dest, job_dir):
            raise AppError(code=ErrorCode.STORAGE_ERROR, message="Invalid artifact lookup", job_id=job_id)
        return dest

    def delete_job_files(self, *, job_id: str, allow_when_active: bool = False) -> None:
        """
        Deletes uploads and artifacts for a job.

        Note: the cleanup service must ensure it never calls this for RUNNING/PROCESSING jobs.
        """
        if not allow_when_active:
            raise AppError(code=ErrorCode.STORAGE_ERROR, message="Deletion requires allow_when_active=True", job_id=job_id)

        upload_candidates = list(self._uploads_dir.glob(f"{job_id}.*"))
        for p in upload_candidates:
            try:
                p.unlink(missing_ok=True)
                self._log.info("file_deleted", extra={"job_id": job_id, "key": f"uploads/{p.name}"})
            except Exception:
                pass

        job_art_dir = (self._artifacts_dir / job_id).resolve()
        if _is_within(job_art_dir, self._artifacts_dir) and job_art_dir.exists():
            for child in job_art_dir.glob("*"):
                try:
                    if child.is_file():
                        child.unlink(missing_ok=True)
                        self._log.info("file_deleted", extra={"job_id": job_id, "key": f"artifacts/{job_id}/{child.name}"})
                except Exception:
                    pass
            try:
                job_art_dir.rmdir()
            except Exception:
                pass

