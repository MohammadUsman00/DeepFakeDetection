import time
from pathlib import Path
from typing import Any
import cv2
import numpy as np

from .config import settings
from .ml.preprocessing.face_detector import get_face_detector
from .ml.preprocessing.transforms import preprocess_face_rgb
from .ml.inference.predictor import predict_batch
from .ml.inference.model_loader import get_model
from .ml.inference.gradcam import GradCam, default_efficientnet_target_layer, encode_png_bytes
from .services.job_service import JobService
from .services.storage_service import StorageService
from .utils.enums import ProcessingStage
from .utils.errors import AppError, ErrorCode
from .utils.logging import get_logger
from .video.pipeline import _crop_rgb, _score_to_confidence_label, _score_interpretation

def analyze_image_pipeline(
    *,
    job_id: str,
    image_path: Path,
    job_svc: JobService,
) -> dict[str, Any]:
    log = get_logger("image_pipeline", job_id=job_id, stage="pipeline")
    detector = get_face_detector()
    model_info = get_model()
    storage = StorageService()

    t0 = time.perf_counter()
    warnings = []
    
    job_svc.set_stage(job_id=job_id, stage=ProcessingStage.face_detection)
    job_svc.update_progress(job_id=job_id, stage=ProcessingStage.face_detection, within_stage_percent=0.5)

    img_bgr = cv2.imread(str(image_path))
    if img_bgr is None or img_bgr.size == 0:
        raise AppError(code=ErrorCode.IMAGE_DECODE_ERROR, message="Could not decode image", details={"path": str(image_path)})

    det = detector.detect_largest_face(img_bgr, job_id=job_id)
    
    low_confidence = False
    low_confidence_reason = None
    final_score = None
    top_k_payload = []
    generated = 0
    explainability_meta = {
        "method": "gradcam",
        "top_k": 1,
        "target_class": 1,
        "overlay_alpha": float(settings.inference.gradcam_overlay_alpha),
    }

    if det is None:
        low_confidence = True
        low_confidence_reason = "no_face_detected"
        warnings.append("No face detected in the image.")
        frames_with_face = 0
    else:
        frames_with_face = 1
        try:
            face_rgb = _crop_rgb(img_bgr, det.bbox_xyxy)
            job_svc.set_stage(job_id=job_id, stage=ProcessingStage.inference)
            job_svc.update_progress(job_id=job_id, stage=ProcessingStage.inference, within_stage_percent=0.5)

            t = preprocess_face_rgb(face_rgb)
            preds = predict_batch([t])
            final_score = preds[0].p_fake

            job_svc.set_stage(job_id=job_id, stage=ProcessingStage.explainability)
            cam = GradCam(model_info.model, default_efficientnet_target_layer(model_info.model))
            
            t_grad = preprocess_face_rgb(face_rgb).unsqueeze(0).to(device="cpu").contiguous()
            res = cam.generate(
                t_grad,
                class_index=1,
                overlay_alpha=float(settings.inference.gradcam_overlay_alpha),
                frame_index=0,
            )
            png_bytes = encode_png_bytes(res.overlay_bgr)
            stored = storage.save_heatmap_overlay(job_id=job_id, frame_index=0, png_bytes=png_bytes)
            name = stored.key.split("/")[-1]
            url = f"{settings.storage.artifact_url_prefix}/{job_id}/{name}"
            
            top_k_payload.append({
                "frame_index": 0,
                "timestamp_ms": 0,
                "p_fake": float(final_score),
                "face_bbox": det.bbox_xyxy,
                "heatmap_overlay_url": url,
            })
            generated = 1
            cam.close()
        except Exception as e:
            log.warning("image_processing_failed", extra={"reason": str(e)})
            warnings.append(f"Image processing failed: {str(e)}")

    if final_score is not None:
        final_score = max(0.0, min(1.0, float(final_score)))

    confidence_label = "Low Confidence" if low_confidence or final_score is None else _score_to_confidence_label(final_score)
    interpretation = _score_interpretation(final_score)
    processing_ms = int((time.perf_counter() - t0) * 1000)

    return {
        "final_score": final_score,
        "confidence_label": confidence_label,
        "confidence_explanation": "Single image static analysis.",
        "aggregation_method": "single_frame",
        "aggregation_formula": "p_fake",
        "frames_used_for_score": frames_with_face,
        "aggregation_debug": {},
        "score_interpretation": interpretation,
        "low_confidence": low_confidence,
        "low_confidence_reason": low_confidence_reason,
        "analysis_completed_at": time.time(),
        "model_version": model_info.model_version,
        "pipeline_version": "0.1.0",
        "frames_sampled": 1,
        "frames_with_face": frames_with_face,
        "skipped_no_face": 1 if frames_with_face == 0 else 0,
        "skipped_error": 0,
        "early_exit_triggered": False,
        "early_exit_reason": None,
        "processing_ms": processing_ms,
        "warnings": warnings,
        "explainability": explainability_meta,
        "heatmaps_generated": generated,
        "top_k_suspicious": top_k_payload,
        "per_frame": top_k_payload,
    }
