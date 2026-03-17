from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Iterable, List

import torch

from ...config import settings
from ...utils.errors import AppError, ErrorCode
from ...utils.logging import get_logger
from .model_loader import get_model, logits_to_probabilities


@dataclass(frozen=True, slots=True)
class Prediction:
    p_fake: float
    p_real: float


def _validate_single(t: torch.Tensor) -> None:
    if t.device.type != "cpu":
        raise AppError(code=ErrorCode.INFERENCE_ERROR, message="Tensor must be on CPU")
    if t.dtype != torch.float32:
        raise AppError(code=ErrorCode.INFERENCE_ERROR, message="Tensor must be float32")
    if tuple(t.shape) != (3, 224, 224):
        raise AppError(code=ErrorCode.INFERENCE_ERROR, message="Invalid tensor shape", details={"shape": list(t.shape)})
    if not t.is_contiguous():
        raise AppError(code=ErrorCode.INFERENCE_ERROR, message="Tensor must be contiguous")


def predict_batch(face_tensors: Iterable[torch.Tensor]) -> List[Prediction]:
    """
    CPU batch inference.

    Input: iterable of tensors each shaped (3,224,224) float32 CPU.
    Output: list of Prediction with probabilities.
    """

    log = get_logger("predictor", stage="inference")

    items = list(face_tensors)
    if not items:
        return []

    # Fetch model once per call.
    lm = get_model()
    batch_size = int(settings.inference.batch_size)
    for t in items:
        _validate_single(t)

    out: List[Prediction] = []
    total_start = time.perf_counter()
    num_batches = 0
    try:
        with torch.no_grad():
            for i in range(0, len(items), batch_size):
                chunk = items[i : i + batch_size]
                # torch.stack is efficient for batch creation.
                x = torch.stack(chunk, dim=0).to(device="cpu", dtype=torch.float32).contiguous()
                logits = lm.model(x)
                if logits.ndim != 2 or logits.shape[1] != 2:
                    raise AppError(
                        code=ErrorCode.INFERENCE_ERROR,
                        message="Unexpected logits shape",
                        details={"shape": list(logits.shape)},
                    )
                probs = logits_to_probabilities(logits).cpu()

                # Convention: index 0 = real, 1 = fake
                for row in probs.tolist():
                    p_real = float(row[0])
                    p_fake = float(row[1])
                    # Clamp for safety.
                    p_real = max(0.0, min(1.0, p_real))
                    p_fake = max(0.0, min(1.0, p_fake))
                    out.append(Prediction(p_fake=p_fake, p_real=p_real))

                num_batches += 1
                # Free batch tensors promptly.
                del x, logits, probs

        elapsed_ms = int((time.perf_counter() - total_start) * 1000)
        log.info(
            "inference_timing",
            extra={
                "count": len(out),
                "batch_size": batch_size,
                "num_batches": num_batches,
                "elapsed_ms": elapsed_ms,
            },
        )
        return out
    except AppError:
        raise
    except Exception as e:
        log.exception("inference_failed")
        raise AppError(code=ErrorCode.INFERENCE_ERROR, message="Inference failed", details={"reason": str(e)}) from e

