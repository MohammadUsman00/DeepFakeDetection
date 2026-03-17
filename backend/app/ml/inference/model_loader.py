from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Optional

import torch
from torch import nn
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights

from ...config import settings
from ...utils.errors import AppError, ErrorCode
from ...utils.logging import get_logger


@dataclass(frozen=True, slots=True)
class LoadedModel:
    model: nn.Module
    weights_path: Optional[Path]
    device: str
    num_threads: int
    model_id: str
    model_version: str


_SINGLETON: LoadedModel | None = None
_LOCK = threading.Lock()


def _build_model() -> nn.Module:
    """
    EfficientNet-B0 backbone with a binary classification head.

    Note: by default, if a deepfake checkpoint is not present locally, we fall back
    to ImageNet weights for the backbone (for local-dev ergonomics). Later steps
    will provide a real deepfake checkpoint download pipeline.
    """

    # ImageNet pretrained backbone
    m = efficientnet_b0(weights=EfficientNet_B0_Weights.DEFAULT)
    # Replace classifier head for binary classification.
    in_features = m.classifier[1].in_features  # type: ignore[index]
    m.classifier[1] = nn.Linear(in_features, 2)  # type: ignore[index]
    return m


def get_model() -> LoadedModel:
    global _SINGLETON
    if _SINGLETON is not None:
        return _SINGLETON
    with _LOCK:
        if _SINGLETON is not None:
            return _SINGLETON

        log = get_logger("model_loader", stage="inference")

        # Configure CPU threads.
        num_threads = int(settings.inference.pytorch_num_threads)
        if num_threads > 0:
            torch.set_num_threads(num_threads)

        model = _build_model()
        device = "cpu"
        model.to(device=device)

        weights_path = settings.inference.model_weights_path
        loaded_from: Optional[Path] = None

        if weights_path.exists():
            try:
                with torch.no_grad():
                    sd = torch.load(str(weights_path), map_location=device)
                # Support both raw state_dict and wrapped checkpoints.
                if isinstance(sd, dict) and "state_dict" in sd and isinstance(sd["state_dict"], dict):
                    sd = sd["state_dict"]
                model.load_state_dict(sd, strict=False)
                loaded_from = weights_path
                log.info(
                    "model_weights_loaded",
                    extra={"model_id": settings.inference.model_id, "model_version": settings.inference.model_version, "weights": str(weights_path)},
                )
            except Exception as e:
                log.exception(
                    "model_weights_load_failed",
                    extra={"model_id": settings.inference.model_id, "model_version": settings.inference.model_version, "weights": str(weights_path)},
                )
                raise AppError(
                    code=ErrorCode.MODEL_NOT_AVAILABLE,
                    message="Failed to load model weights",
                    details={"path": str(weights_path), "reason": str(e)},
                ) from e
        else:
            log.warning(
                "model_weights_missing_using_imagenet_backbone",
                extra={"model_id": settings.inference.model_id, "model_version": settings.inference.model_version, "weights": str(weights_path)},
            )

        # Ensure eval mode after loading (required).
        model.eval()

        _SINGLETON = LoadedModel(
            model=model,
            weights_path=loaded_from,
            device=device,
            num_threads=(num_threads if num_threads > 0 else torch.get_num_threads()),
            model_id=settings.inference.model_id,
            model_version=settings.inference.model_version,
        )
        return _SINGLETON


def warmup_model() -> None:
    """
    Runs a lightweight forward pass on CPU to avoid first-request delay.
    """

    log = get_logger("model_loader", stage="inference")
    lm = get_model()
    with torch.no_grad():
        x = torch.zeros((1, 3, 224, 224), dtype=torch.float32, device=lm.device).contiguous()
        _ = lm.model(x)
    log.info(
        "model_warmup_done",
        extra={
            "model_id": lm.model_id,
            "model_version": lm.model_version,
            "device": lm.device,
            "threads": lm.num_threads,
            "weights_loaded": lm.weights_path is not None,
        },
    )


def validate_input_tensor(x: torch.Tensor) -> None:
    if x is None:
        raise AppError(code=ErrorCode.INFERENCE_ERROR, message="Missing input tensor")
    if x.device.type != "cpu":
        raise AppError(code=ErrorCode.INFERENCE_ERROR, message="Input tensor must be on CPU")
    if x.dtype != torch.float32:
        raise AppError(code=ErrorCode.INFERENCE_ERROR, message="Input tensor must be float32")
    if tuple(x.shape) != (1, 3, 224, 224):
        raise AppError(code=ErrorCode.INFERENCE_ERROR, message="Invalid input tensor shape", details={"shape": list(x.shape)})
    if not x.is_contiguous():
        raise AppError(code=ErrorCode.INFERENCE_ERROR, message="Input tensor must be contiguous")


def logits_to_probabilities(logits: torch.Tensor) -> torch.Tensor:
    """
    Convert logits (N,2) to probabilities (N,2) using softmax.
    """

    with torch.no_grad():
        return torch.softmax(logits, dim=-1)

