from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from ...config import settings
from ...utils.errors import AppError, ErrorCode
from ...utils.logging import get_logger


@dataclass(frozen=True, slots=True)
class FaceDetection:
    bbox_xyxy: tuple[int, int, int, int]
    score: float


def _area(b: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = b
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _clamp_bbox_xyxy(
    bbox: tuple[int, int, int, int], *, width: int, height: int
) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(width - 1, int(x1)))
    x2 = max(0, min(width - 1, int(x2)))
    y1 = max(0, min(height - 1, int(y1)))
    y2 = max(0, min(height - 1, int(y2)))
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


def _pad_bbox_xyxy(
    bbox: tuple[int, int, int, int], *, pad_ratio: float, width: int, height: int
) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = bbox
    w = x2 - x1
    h = y2 - y1
    pad_x = int(round(w * pad_ratio))
    pad_y = int(round(h * pad_ratio))
    return _clamp_bbox_xyxy((x1 - pad_x, y1 - pad_y, x2 + pad_x, y2 + pad_y), width=width, height=height)


class FaceDetector:
    """
    Face detector wrapper.

    Primary: MTCNN (facenet-pytorch)
    Optional fallback: Haar Cascade (OpenCV) when enabled.
    """

    def __init__(self) -> None:
        self._log = get_logger("face_detector", stage="face_detection")
        self._mtcnn = None
        self._haar = None

        try:
            from facenet_pytorch import MTCNN  # type: ignore

            device = "cpu"
            self._mtcnn = MTCNN(keep_all=True, device=device)
        except Exception:
            self._mtcnn = None

        if settings.face.enable_haar_fallback:
            try:
                self._haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            except Exception:
                self._haar = None

    def detect_faces(self, frame_bgr: np.ndarray, *, job_id: str | None = None) -> list[FaceDetection]:
        """
        Returns all detected faces (int bboxes), filtered by confidence/size.
        Designed so we can later batch this (e.g., multiple frames).
        """

        if frame_bgr is None or frame_bgr.size == 0:
            return []

        h, w = frame_bgr.shape[:2]
        min_sz = int(settings.face.min_face_size)
        min_conf = float(settings.face.min_confidence)
        pad_ratio = float(settings.face.bbox_padding_ratio)

        detections: list[FaceDetection] = []

        # 1) MTCNN (preferred)
        if self._mtcnn is not None:
            try:
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                boxes, probs = self._mtcnn.detect(frame_rgb)
                if boxes is not None and len(boxes) > 0:
                    for i, b in enumerate(boxes):
                        score = float(probs[i]) if probs is not None else 0.0
                        if score < min_conf:
                            continue
                        x1, y1, x2, y2 = (int(b[0]), int(b[1]), int(b[2]), int(b[3]))
                        clamped = _clamp_bbox_xyxy((x1, y1, x2, y2), width=w, height=h)
                        if clamped is None:
                            continue
                        cx1, cy1, cx2, cy2 = clamped
                        if (cx2 - cx1) < min_sz or (cy2 - cy1) < min_sz:
                            continue
                        padded = _pad_bbox_xyxy(clamped, pad_ratio=pad_ratio, width=w, height=h)
                        if padded is None:
                            continue
                        detections.append(FaceDetection(bbox_xyxy=padded, score=score))
            except Exception as e:
                self._log.warning("mtcnn_failed", extra={"job_id": job_id or "-", "reason": str(e)})

        # 2) Optional Haar fallback
        if not detections and self._haar is not None:
            try:
                gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
                faces = self._haar.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(min_sz, min_sz),
                )
                if faces is not None and len(faces) > 0:
                    for (x, y, fw, fh) in faces:
                        bbox = _clamp_bbox_xyxy((int(x), int(y), int(x + fw), int(y + fh)), width=w, height=h)
                        if bbox is None:
                            continue
                        padded = _pad_bbox_xyxy(bbox, pad_ratio=pad_ratio, width=w, height=h)
                        if padded is None:
                            continue
                        detections.append(FaceDetection(bbox_xyxy=padded, score=0.0))
            except Exception as e:
                self._log.warning("haar_failed", extra={"job_id": job_id or "-", "reason": str(e)})

        return detections

    def detect_largest_face(self, frame_bgr: np.ndarray, *, job_id: str | None = None) -> Optional[FaceDetection]:
        detections = self.detect_faces(frame_bgr, job_id=job_id)
        if not detections:
            self._log.info("no_face", extra={"job_id": job_id or "-"})
            return None

        if len(detections) > 1:
            self._log.info("multiple_faces_detected", extra={"job_id": job_id or "-", "count": len(detections)})

        # Largest by area (after padding/clamp)
        best = max(detections, key=lambda d: (d.bbox_xyxy[2] - d.bbox_xyxy[0]) * (d.bbox_xyxy[3] - d.bbox_xyxy[1]))
        self._log.info(
            "face_detected",
            extra={
                "job_id": job_id or "-",
                "score": best.score,
                "bbox": best.bbox_xyxy,
            },
        )
        return best


_SINGLETON: FaceDetector | None = None


def get_face_detector() -> FaceDetector:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = FaceDetector()
    return _SINGLETON

