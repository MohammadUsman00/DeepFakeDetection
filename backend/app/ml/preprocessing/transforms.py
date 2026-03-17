from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from PIL import Image
from torchvision import transforms

from ...utils.logging import get_logger


IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


@dataclass(frozen=True, slots=True)
class PreprocessConfig:
    input_size: int = 224


_DEFAULT_CFG = PreprocessConfig()


def build_preprocess(cfg: PreprocessConfig = _DEFAULT_CFG) -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize((cfg.input_size, cfg.input_size)),
            transforms.ToTensor(),  # converts uint8 [0..255] to float32 [0..1]
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


_PREPROCESS = build_preprocess()


def preprocess_face_rgb(face_rgb: np.ndarray) -> torch.Tensor:
    """
    Preprocess a face crop for EfficientNet-B0 inference.

    Input:
    - `face_rgb`: RGB image as a numpy array with shape (H, W, 3).
      - dtype can be uint8 (0..255) or float; it will be converted to uint8 safely.

    Steps:
    - Ensure RGB format (caller must provide RGB, not BGR)
    - Resize to (224, 224)
    - Convert to float32 and scale to [0, 1] (via `ToTensor()`)
    - Apply ImageNet normalization

    Output:
    - torch.Tensor on CPU, contiguous, shape (3, 224, 224)
    """
    log = get_logger("preprocess", stage="preprocessing")
    try:
        if face_rgb is None or getattr(face_rgb, "size", 0) == 0:
            raise ValueError("Empty face crop")
        if face_rgb.ndim != 3 or face_rgb.shape[2] != 3:
            raise ValueError("Expected RGB image with 3 channels")

        # Convert to uint8 for PIL; ToTensor() handles /255.0 scaling.
        img = Image.fromarray(face_rgb.astype(np.uint8), mode="RGB")
        t = _PREPROCESS(img)

        # Ensure CPU + contiguous float32 tensor.
        t = t.to(device="cpu", dtype=torch.float32).contiguous()

        if tuple(t.shape) != (3, 224, 224):
            raise ValueError(f"Unexpected tensor shape {tuple(t.shape)}; expected (3, 224, 224)")

        log.debug("preprocess_done")
        return t
    except Exception as e:
        log.warning("preprocess_failed", extra={"reason": str(e)})
        raise


def add_batch_dim(t: torch.Tensor) -> torch.Tensor:
    """
    Convert a (3, 224, 224) tensor into a batched (1, 3, 224, 224) tensor on CPU.
    """

    if tuple(t.shape) != (3, 224, 224):
        raise ValueError(f"Expected (3,224,224) tensor, got {tuple(t.shape)}")
    return t.unsqueeze(0).to(device="cpu").contiguous()

