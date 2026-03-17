from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
import torch
from torch import nn

from ...utils.errors import AppError, ErrorCode
from ...utils.logging import get_logger


@dataclass(frozen=True, slots=True)
class GradCamResult:
    overlay_bgr: np.ndarray
    heatmap_bgr: np.ndarray


class GradCam:
    """
    Grad-CAM implementation for CNN-based models.

    Usage (planned):
    - Select Top-K suspicious frames (K=5)
    - For each face crop, compute Grad-CAM heatmap on a target conv layer
    - Overlay heatmap on the face crop and return/save PNG
    """

    def __init__(self, model: nn.Module, target_layer: nn.Module):
        self.model = model
        self.target_layer = target_layer
        self._log = get_logger("gradcam", stage="explainability")

        self._activations: Optional[torch.Tensor] = None
        self._gradients: Optional[torch.Tensor] = None

        def fwd_hook(_, __, output):
            self._activations = output

        def bwd_hook(_, grad_input, grad_output):
            # grad_output is a tuple; [0] is gradients w.r.t layer output
            self._gradients = grad_output[0]

        self._fwd_handle = self.target_layer.register_forward_hook(fwd_hook)
        self._bwd_handle = self.target_layer.register_full_backward_hook(bwd_hook)

    def close(self) -> None:
        try:
            self._fwd_handle.remove()
        except Exception:
            pass
        try:
            self._bwd_handle.remove()
        except Exception:
            pass

    def __del__(self) -> None:
        self.close()

    def generate(
        self,
        x: torch.Tensor,
        *,
        class_index: int = 1,
        overlay_alpha: float = 0.45,
        frame_index: int | None = None,
    ) -> GradCamResult:
        """
        Generate Grad-CAM for a single input tensor.

        Input:
        - x: (1,3,224,224) float32 CPU contiguous
        - class_index: which logit to explain (default 1 = fake)

        Output:
        - overlay_bgr: heatmap overlay on the input image (BGR)
        - heatmap_bgr: colored heatmap (BGR)
        """

        # Must be single input (batch size = 1).
        if tuple(x.shape) != (1, 3, 224, 224):
            raise AppError(code=ErrorCode.EXPLAINABILITY_ERROR, message="Invalid input tensor shape for Grad-CAM", details={"shape": list(x.shape)})
        if x.device.type != "cpu":
            raise AppError(code=ErrorCode.EXPLAINABILITY_ERROR, message="Grad-CAM expects CPU tensor")

        # Grad-CAM requires gradients; do NOT wrap in torch.no_grad().
        self.model.eval()
        self.model.zero_grad(set_to_none=True)
        self._activations = None
        self._gradients = None

        self._log.info(
            "gradcam_generate",
            extra={"frame_index": frame_index if frame_index is not None else -1, "alpha": overlay_alpha, "class_index": int(class_index)},
        )

        try:
            logits = self.model(x)
            if logits.ndim != 2:
                raise AppError(code=ErrorCode.EXPLAINABILITY_ERROR, message="Unexpected logits shape", details={"shape": list(logits.shape)})

            # Convention: class_index=1 is "fake" everywhere in this project.
            score = logits[0, int(class_index)]
            score.backward()

            if self._activations is None or self._gradients is None:
                raise AppError(code=ErrorCode.EXPLAINABILITY_ERROR, message="Missing activations/gradients for Grad-CAM")

            acts = self._activations.detach()  # (1,C,H,W)
            grads = self._gradients.detach()   # (1,C,H,W)

            weights = grads.mean(dim=(2, 3), keepdim=True)  # (1,C,1,1)
            cam = (weights * acts).sum(dim=1, keepdim=False)  # (1,H,W)
            cam = torch.relu(cam)

            cam_np = cam[0].cpu().numpy()
            # Stable normalization to [0,1]
            cam_min = float(cam_np.min())
            cam_max = float(cam_np.max())
            cam_np = cam_np - cam_min
            denom = (cam_max - cam_min) + 1e-8
            cam_np = cam_np / denom

            heatmap_u8 = np.clip(cam_np * 255.0, 0.0, 255.0).astype(np.uint8)
            heatmap_bgr = cv2.applyColorMap(heatmap_u8, cv2.COLORMAP_JET)

            # Reconstruct input image for overlay (approx): unnormalize is omitted in this step.
            # In later steps, we will pass original face crop for true overlay.
            img = x[0].detach().cpu()
            img = img.permute(1, 2, 0).numpy()
            img = np.clip(img, 0.0, 1.0)
            img_bgr = np.clip(img[..., ::-1] * 255.0, 0.0, 255.0).astype(np.uint8)

            heatmap_bgr = cv2.resize(heatmap_bgr, (img_bgr.shape[1], img_bgr.shape[0]))
            alpha = float(max(0.0, min(1.0, overlay_alpha)))
            overlay = cv2.addWeighted(img_bgr, 1.0 - alpha, heatmap_bgr, alpha, 0)

            # Cleanup references to avoid retaining tensors.
            self._activations = None
            self._gradients = None
            self.model.zero_grad(set_to_none=True)

            self._log.debug("gradcam_done")
            return GradCamResult(overlay_bgr=overlay, heatmap_bgr=heatmap_bgr)
        except AppError:
            raise
        except Exception as e:
            self._log.exception("gradcam_failed")
            raise AppError(code=ErrorCode.EXPLAINABILITY_ERROR, message="Grad-CAM failed", details={"reason": str(e)}) from e


def encode_png_bytes(bgr_img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", bgr_img)
    if not ok:
        raise AppError(code=ErrorCode.EXPLAINABILITY_ERROR, message="Failed to encode PNG")
    return bytes(buf)


def default_efficientnet_target_layer(model: nn.Module) -> nn.Module:
    """
    Best-effort default target layer for EfficientNet-B0 from torchvision.
    """

    # torchvision EfficientNet has `features` as a sequential.
    # Using the last block usually provides good spatial maps.
    return model.features[-1]  # type: ignore[attr-defined,index]

