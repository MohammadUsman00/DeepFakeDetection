from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


def _env_str(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None or v.strip() == "" else v.strip()


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    return int(v)


def _env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    return float(v)


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    s = v.strip().lower()
    if s in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean for {name}: {v!r}")


def _env_csv(name: str, default: Iterable[str]) -> tuple[str, ...]:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return tuple(default)
    parts = [p.strip().lower() for p in v.split(",") if p.strip()]
    return tuple(parts)


def _clamp_int(v: int, *, name: str, min_v: int | None = None, max_v: int | None = None) -> int:
    if min_v is not None and v < min_v:
        raise ValueError(f"{name} must be >= {min_v}, got {v}")
    if max_v is not None and v > max_v:
        raise ValueError(f"{name} must be <= {max_v}, got {v}")
    return v


def _clamp_float(
    v: float, *, name: str, min_v: float | None = None, max_v: float | None = None
) -> float:
    if min_v is not None and v < min_v:
        raise ValueError(f"{name} must be >= {min_v}, got {v}")
    if max_v is not None and v > max_v:
        raise ValueError(f"{name} must be <= {max_v}, got {v}")
    return v


@dataclass(frozen=True, slots=True)
class FileConfig:
    """Upload and file validation limits."""

    max_upload_bytes: int
    max_filename_chars: int
    allowed_video_ext: tuple[str, ...]
    allowed_image_ext: tuple[str, ...]
    allowed_video_mime: tuple[str, ...]
    allowed_image_mime: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VideoConfig:
    """Video constraints and frame sampling."""

    max_duration_seconds: int
    sample_fps: float
    max_frames: int
    fps_metadata_min: float
    fps_metadata_max: float
    downscale_max_width: int


@dataclass(frozen=True, slots=True)
class InferenceConfig:
    """Inference/runtime behavior (CPU-first)."""

    batch_size: int
    top_k_explainability: int
    pytorch_num_threads: int
    model_id: str
    model_version: str
    model_weights_path: Path
    gradcam_time_budget_ms: int
    gradcam_overlay_alpha: float


@dataclass(frozen=True, slots=True)
class AggregationConfig:
    """Robust aggregation for final authenticity score."""

    top_fraction: float
    trim_fraction: float
    min_frames_for_trim: int
    small_sample_fallback_threshold: int


@dataclass(frozen=True, slots=True)
class EarlyExitConfig:
    """Early-exit optimization when evidence is strong."""

    enabled: bool
    high_fake_threshold: float
    consecutive_high_frames: int
    min_frames_before_exit: int


@dataclass(frozen=True, slots=True)
class FaceConfig:
    """Face detection behavior."""

    largest_face_only: bool
    min_face_frames_for_confident_result: int
    enable_haar_fallback: bool
    min_confidence: float
    min_face_size: int
    bbox_padding_ratio: float


@dataclass(frozen=True, slots=True)
class CleanupConfig:
    """Artifact and upload cleanup settings."""

    enabled: bool
    ttl_seconds: int
    interval_seconds: int


@dataclass(frozen=True, slots=True)
class StorageConfig:
    """Filesystem layout and URL prefixes for artifacts."""

    data_dir: Path
    uploads_dir: Path
    artifacts_dir: Path
    artifact_url_prefix: str
    allow_overwrite_uploads: bool
    total_quota_bytes: int


@dataclass(frozen=True, slots=True)
class ResultConfig:
    """Limits for persisted analysis outputs."""

    max_summary_json_bytes: int


@dataclass(frozen=True, slots=True)
class JobConfig:
    """Runtime controls for background processing."""

    timeout_seconds: int
    max_retries: int


@dataclass(frozen=True, slots=True)
class Settings:
    """Centralized configuration for the backend."""

    file: FileConfig
    video: VideoConfig
    face: FaceConfig
    inference: InferenceConfig
    aggregation: AggregationConfig
    early_exit: EarlyExitConfig
    cleanup: CleanupConfig
    storage: StorageConfig
    result: ResultConfig
    job: JobConfig

    @staticmethod
    def load() -> "Settings":
        """
        Loads settings from environment variables with safe defaults.

        Environment variable naming convention:
        - FILE_*
        - VIDEO_*
        - FACE_*
        - INFER_*
        - AGG_*
        - EARLY_EXIT_*
        - CLEANUP_*
        - STORAGE_*
        - RESULT_*
        - JOB_*
        """

        # --------------------
        # File
        # --------------------
        max_upload_mb = _clamp_int(_env_int("FILE_MAX_UPLOAD_MB", 200), name="FILE_MAX_UPLOAD_MB", min_v=1)
        file_cfg = FileConfig(
            max_upload_bytes=max_upload_mb * 1024 * 1024,
            max_filename_chars=_clamp_int(_env_int("FILE_MAX_FILENAME_CHARS", 100), name="FILE_MAX_FILENAME_CHARS", min_v=1, max_v=255),
            allowed_video_ext=_env_csv("FILE_ALLOWED_VIDEO_EXT", ("mp4", "mov")),
            allowed_image_ext=_env_csv("FILE_ALLOWED_IMAGE_EXT", ("jpg", "jpeg", "png")),
            allowed_video_mime=_env_csv("FILE_ALLOWED_VIDEO_MIME", ("video/mp4", "video/quicktime")),
            allowed_image_mime=_env_csv("FILE_ALLOWED_IMAGE_MIME", ("image/jpeg", "image/png")),
        )
        if not file_cfg.allowed_video_ext:
            raise ValueError("FILE_ALLOWED_VIDEO_EXT must not be empty")
        if not file_cfg.allowed_image_ext:
            raise ValueError("FILE_ALLOWED_IMAGE_EXT must not be empty")
        if not file_cfg.allowed_video_mime:
            raise ValueError("FILE_ALLOWED_VIDEO_MIME must not be empty")
        if not file_cfg.allowed_image_mime:
            raise ValueError("FILE_ALLOWED_IMAGE_MIME must not be empty")

        # --------------------
        # Video
        # --------------------
        video_cfg = VideoConfig(
            max_duration_seconds=_clamp_int(
                _env_int("VIDEO_MAX_DURATION_SECONDS", 180),
                name="VIDEO_MAX_DURATION_SECONDS",
                min_v=1,
                max_v=60 * 60,
            ),
            sample_fps=_clamp_float(_env_float("VIDEO_SAMPLE_FPS", 1.0), name="VIDEO_SAMPLE_FPS", min_v=0.1, max_v=30.0),
            max_frames=_clamp_int(_env_int("VIDEO_MAX_FRAMES", 150), name="VIDEO_MAX_FRAMES", min_v=1, max_v=10_000),
            # Used to decide if reported FPS metadata is trustworthy; otherwise we fall back to timestamp-based sampling.
            fps_metadata_min=_clamp_float(_env_float("VIDEO_FPS_METADATA_MIN", 1.0), name="VIDEO_FPS_METADATA_MIN", min_v=0.1),
            fps_metadata_max=_clamp_float(
                _env_float("VIDEO_FPS_METADATA_MAX", 240.0), name="VIDEO_FPS_METADATA_MAX", min_v=1.0
            ),
            downscale_max_width=_clamp_int(
                _env_int("VIDEO_DOWNSCALE_MAX_WIDTH", 0),
                name="VIDEO_DOWNSCALE_MAX_WIDTH",
                min_v=0,
                max_v=8192,
            ),
        )
        if video_cfg.fps_metadata_min >= video_cfg.fps_metadata_max:
            raise ValueError("VIDEO_FPS_METADATA_MIN must be < VIDEO_FPS_METADATA_MAX")

        # --------------------
        # Face detection
        # --------------------
        face_cfg = FaceConfig(
            largest_face_only=_env_bool("FACE_LARGEST_FACE_ONLY", True),
            # If fewer than this many frames contain a face, produce a LOW_CONFIDENCE result (not FAILED).
            min_face_frames_for_confident_result=_clamp_int(
                _env_int("FACE_MIN_FACE_FRAMES", 10), name="FACE_MIN_FACE_FRAMES", min_v=0, max_v=video_cfg.max_frames
            ),
            # Optional: Haar cascade fallback if MTCNN is too slow on CPU.
            enable_haar_fallback=_env_bool("FACE_ENABLE_HAAR_FALLBACK", False),
            min_confidence=_clamp_float(
                _env_float("FACE_MIN_CONFIDENCE", 0.90),
                name="FACE_MIN_CONFIDENCE",
                min_v=0.0,
                max_v=1.0,
            ),
            min_face_size=_clamp_int(_env_int("FACE_MIN_FACE_SIZE", 40), name="FACE_MIN_FACE_SIZE", min_v=1, max_v=4096),
            bbox_padding_ratio=_clamp_float(
                _env_float("FACE_BBOX_PADDING_RATIO", 0.10),
                name="FACE_BBOX_PADDING_RATIO",
                min_v=0.0,
                max_v=1.0,
            ),
        )

        # --------------------
        # Inference / model
        # --------------------
        default_model_id = "efficientnet_b0_deepfake"
        weights_path = Path(
            _env_str("INFER_MODEL_WEIGHTS_PATH", str(Path("data") / "models" / "efficientnet_b0.pth"))
        ).expanduser()
        infer_cfg = InferenceConfig(
            batch_size=_clamp_int(_env_int("INFER_BATCH_SIZE", 16), name="INFER_BATCH_SIZE", min_v=1, max_v=256),
            top_k_explainability=_clamp_int(_env_int("INFER_TOP_K_EXPLAINABILITY", 5), name="INFER_TOP_K_EXPLAINABILITY", min_v=1, max_v=50),
            pytorch_num_threads=_clamp_int(_env_int("INFER_TORCH_NUM_THREADS", 0), name="INFER_TORCH_NUM_THREADS", min_v=0, max_v=256),
            model_id=_env_str("INFER_MODEL_ID", default_model_id),
            model_version=_env_str("INFER_MODEL_VERSION", "0.1.0"),
            model_weights_path=weights_path.resolve(),
            gradcam_time_budget_ms=_clamp_int(
                _env_int("INFER_GRADCAM_TIME_BUDGET_MS", 0),
                name="INFER_GRADCAM_TIME_BUDGET_MS",
                min_v=0,
                max_v=10 * 60 * 1000,
            ),
            gradcam_overlay_alpha=_clamp_float(
                _env_float("INFER_GRADCAM_OVERLAY_ALPHA", 0.45),
                name="INFER_GRADCAM_OVERLAY_ALPHA",
                min_v=0.0,
                max_v=1.0,
            ),
        )
        if infer_cfg.model_id.strip() == "":
            raise ValueError("INFER_MODEL_ID must not be empty")

        # --------------------
        # Aggregation
        # --------------------
        agg_cfg = AggregationConfig(
            # Precise definition (implemented later):
            # - sort descending
            # - take top 30%
            # - trim 10% from both ends (if enough samples)
            # - mean
            top_fraction=_clamp_float(_env_float("AGG_TOP_FRACTION", 0.30), name="AGG_TOP_FRACTION", min_v=0.01, max_v=1.0),
            trim_fraction=_clamp_float(_env_float("AGG_TRIM_FRACTION", 0.10), name="AGG_TRIM_FRACTION", min_v=0.0, max_v=0.49),
            # Minimum number of samples in the selected slice required to do symmetric trimming.
            min_frames_for_trim=_clamp_int(_env_int("AGG_MIN_FRAMES_FOR_TRIM", 10), name="AGG_MIN_FRAMES_FOR_TRIM", min_v=1),
            # If fewer than this many face-frames exist overall, use a small-sample fallback aggregation.
            small_sample_fallback_threshold=_clamp_int(
                _env_int("AGG_SMALL_SAMPLE_FALLBACK_THRESHOLD", 5),
                name="AGG_SMALL_SAMPLE_FALLBACK_THRESHOLD",
                min_v=1,
            ),
        )
        if agg_cfg.top_fraction <= 0.0 or agg_cfg.top_fraction > 1.0:
            raise ValueError("AGG_TOP_FRACTION must be in (0, 1]")
        if agg_cfg.trim_fraction < 0.0 or agg_cfg.trim_fraction >= 0.5:
            raise ValueError("AGG_TRIM_FRACTION must be in [0, 0.5)")
        if agg_cfg.top_fraction <= 2 * agg_cfg.trim_fraction and agg_cfg.trim_fraction > 0.0:
            raise ValueError("AGG_TOP_FRACTION must be > 2 * AGG_TRIM_FRACTION when trimming is enabled")

        # --------------------
        # Early-exit
        # --------------------
        early_exit_cfg = EarlyExitConfig(
            enabled=_env_bool("EARLY_EXIT_ENABLED", True),
            high_fake_threshold=_clamp_float(
                _env_float("EARLY_EXIT_HIGH_FAKE_THRESHOLD", 0.95),
                name="EARLY_EXIT_HIGH_FAKE_THRESHOLD",
                min_v=0.5,
                max_v=1.0,
            ),
            consecutive_high_frames=_clamp_int(
                _env_int("EARLY_EXIT_CONSECUTIVE_HIGH_FRAMES", 8),
                name="EARLY_EXIT_CONSECUTIVE_HIGH_FRAMES",
                min_v=1,
                max_v=video_cfg.max_frames,
            ),
            # Early-exit is only allowed after this many frames have been processed (strict).
            min_frames_before_exit=_clamp_int(
                _env_int("EARLY_EXIT_MIN_FRAMES_BEFORE_EXIT", 20),
                name="EARLY_EXIT_MIN_FRAMES_BEFORE_EXIT",
                min_v=0,
                max_v=video_cfg.max_frames,
            ),
        )
        if early_exit_cfg.min_frames_before_exit > video_cfg.max_frames:
            raise ValueError("EARLY_EXIT_MIN_FRAMES_BEFORE_EXIT must be <= VIDEO_MAX_FRAMES")

        # --------------------
        # Cleanup
        # --------------------
        cleanup_cfg = CleanupConfig(
            enabled=_env_bool("CLEANUP_ENABLED", True),
            ttl_seconds=_clamp_int(
                _env_int("CLEANUP_TTL_SECONDS", 24 * 60 * 60),
                name="CLEANUP_TTL_SECONDS",
                min_v=60,
                max_v=30 * 24 * 60 * 60,
            ),
            interval_seconds=_clamp_int(
                _env_int("CLEANUP_INTERVAL_SECONDS", 60 * 60),
                name="CLEANUP_INTERVAL_SECONDS",
                min_v=30,
                max_v=24 * 60 * 60,
            ),
        )

        # --------------------
        # Storage
        # --------------------
        data_dir = Path(_env_str("STORAGE_DATA_DIR", str(Path.cwd() / "data"))).expanduser().resolve()
        uploads_dir = Path(_env_str("STORAGE_UPLOADS_DIR", str(data_dir / "uploads"))).expanduser().resolve()
        artifacts_dir = Path(_env_str("STORAGE_ARTIFACTS_DIR", str(data_dir / "artifacts"))).expanduser().resolve()
        storage_cfg = StorageConfig(
            data_dir=data_dir,
            uploads_dir=uploads_dir,
            artifacts_dir=artifacts_dir,
            artifact_url_prefix=_env_str("STORAGE_ARTIFACT_URL_PREFIX", "/artifacts"),
            allow_overwrite_uploads=_env_bool("STORAGE_ALLOW_OVERWRITE_UPLOADS", False),
            total_quota_bytes=_clamp_int(
                _env_int("STORAGE_TOTAL_QUOTA_MB", 0),
                name="STORAGE_TOTAL_QUOTA_MB",
                min_v=0,
                max_v=10_000_000,
            )
            * 1024
            * 1024,
        )
        if not storage_cfg.artifact_url_prefix.startswith("/"):
            raise ValueError("STORAGE_ARTIFACT_URL_PREFIX must start with '/'")

        # --------------------
        # Result storage limits
        # --------------------
        result_cfg = ResultConfig(
            max_summary_json_bytes=_clamp_int(
                _env_int("RESULT_MAX_SUMMARY_JSON_BYTES", 512 * 1024),
                name="RESULT_MAX_SUMMARY_JSON_BYTES",
                min_v=1024,
                max_v=10 * 1024 * 1024,
            )
        )

        job_cfg = JobConfig(
            timeout_seconds=_clamp_int(_env_int("JOB_TIMEOUT_SECONDS", 0), name="JOB_TIMEOUT_SECONDS", min_v=0, max_v=24 * 60 * 60),
            max_retries=_clamp_int(_env_int("JOB_MAX_RETRIES", 0), name="JOB_MAX_RETRIES", min_v=0, max_v=5),
        )

        # Basic sanity checks that prevent misconfiguration.
        if infer_cfg.top_k_explainability < 1:
            raise ValueError("INFER_TOP_K_EXPLAINABILITY must be >= 1")
        if video_cfg.max_frames < 1:
            raise ValueError("VIDEO_MAX_FRAMES must be >= 1")

        return Settings(
            file=file_cfg,
            video=video_cfg,
            face=face_cfg,
            inference=infer_cfg,
            aggregation=agg_cfg,
            early_exit=early_exit_cfg,
            cleanup=cleanup_cfg,
            storage=storage_cfg,
            result=result_cfg,
            job=job_cfg,
        )

    @property
    def effective_max_frames(self) -> int:
        """
        A derived cap that respects both `VIDEO_MAX_FRAMES` and the theoretical
        number of samples implied by duration * sample_fps.

        Note: actual pipelines can further reduce frames due to face-missing skips.
        """
        theoretical = int(math.ceil(self.video.max_duration_seconds * self.video.sample_fps))
        return max(1, min(self.video.max_frames, theoretical))

    def summary(self) -> dict[str, Any]:
        """
        Safe, JSON-serializable summary for debugging (e.g., `/system-info`).
        Avoids leaking secrets (we don't store any here) and normalizes paths.
        """
        return {
            "file": {
                "max_upload_bytes": self.file.max_upload_bytes,
                "max_filename_chars": self.file.max_filename_chars,
                "allowed_video_ext": list(self.file.allowed_video_ext),
                "allowed_image_ext": list(self.file.allowed_image_ext),
                "allowed_video_mime": list(self.file.allowed_video_mime),
                "allowed_image_mime": list(self.file.allowed_image_mime),
            },
            "video": {
                "max_duration_seconds": self.video.max_duration_seconds,
                "sample_fps": self.video.sample_fps,
                "max_frames": self.video.max_frames,
                "effective_max_frames": self.effective_max_frames,
                "fps_metadata_min": self.video.fps_metadata_min,
                "fps_metadata_max": self.video.fps_metadata_max,
                "downscale_max_width": self.video.downscale_max_width,
            },
            "face": {
                "largest_face_only": self.face.largest_face_only,
                "min_face_frames_for_confident_result": self.face.min_face_frames_for_confident_result,
                "enable_haar_fallback": self.face.enable_haar_fallback,
                "min_confidence": self.face.min_confidence,
                "min_face_size": self.face.min_face_size,
                "bbox_padding_ratio": self.face.bbox_padding_ratio,
            },
            "inference": {
                "batch_size": self.inference.batch_size,
                "top_k_explainability": self.inference.top_k_explainability,
                "pytorch_num_threads": self.inference.pytorch_num_threads,
                "model_id": self.inference.model_id,
                "model_version": self.inference.model_version,
                "model_weights_path": str(self.inference.model_weights_path),
                "gradcam_time_budget_ms": self.inference.gradcam_time_budget_ms,
                "gradcam_overlay_alpha": self.inference.gradcam_overlay_alpha,
            },
            "aggregation": {
                "top_fraction": self.aggregation.top_fraction,
                "trim_fraction": self.aggregation.trim_fraction,
                "min_frames_for_trim": self.aggregation.min_frames_for_trim,
                "small_sample_fallback_threshold": self.aggregation.small_sample_fallback_threshold,
            },
            "early_exit": {
                "enabled": self.early_exit.enabled,
                "high_fake_threshold": self.early_exit.high_fake_threshold,
                "consecutive_high_frames": self.early_exit.consecutive_high_frames,
                "min_frames_before_exit": self.early_exit.min_frames_before_exit,
            },
            "cleanup": {
                "enabled": self.cleanup.enabled,
                "ttl_seconds": self.cleanup.ttl_seconds,
                "interval_seconds": self.cleanup.interval_seconds,
            },
            "storage": {
                "data_dir": str(self.storage.data_dir),
                "uploads_dir": str(self.storage.uploads_dir),
                "artifacts_dir": str(self.storage.artifacts_dir),
                "artifact_url_prefix": self.storage.artifact_url_prefix,
                "allow_overwrite_uploads": self.storage.allow_overwrite_uploads,
                "total_quota_bytes": self.storage.total_quota_bytes,
            },
            "result": {
                "max_summary_json_bytes": self.result.max_summary_json_bytes,
            },
            "job": {
                "timeout_seconds": self.job.timeout_seconds,
                "max_retries": self.job.max_retries,
            },
        }


# Singleton settings instance for imports throughout the backend.
settings = Settings.load()

