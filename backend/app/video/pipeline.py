from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import time

from ..config import settings
from ..ml.preprocessing.face_detector import get_face_detector
from ..ml.preprocessing.transforms import preprocess_face_rgb
from ..ml.inference.predictor import predict_batch
from ..ml.inference.model_loader import get_model
from ..ml.inference.gradcam import GradCam, default_efficientnet_target_layer, encode_png_bytes
from ..ml.result_decision import predicted_manipulation
from ..services.job_service import JobService
from ..services.storage_service import StorageService
from ..utils.enums import ProcessingStage
from ..utils.errors import AppError, ErrorCode
from ..utils.logging import get_logger
from .frame_sampler import iter_sampled_frames


@dataclass(frozen=True, slots=True)
class FramePrediction:
    frame_index: int
    timestamp_ms: int
    p_fake: float
    face_bbox: tuple[int, int, int, int]


def _crop_rgb(frame_bgr: np.ndarray, bbox_xyxy: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = bbox_xyxy
    crop_bgr = frame_bgr[y1:y2, x1:x2]
    if crop_bgr is None or crop_bgr.size == 0:
        raise AppError(code=ErrorCode.IMAGE_DECODE_ERROR, message="Empty face crop after bbox")
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    return crop_rgb


def analyze_video_up_to_inference(
    *,
    job_id: str,
    video_path: Path,
    job_svc: JobService,
) -> dict[str, Any]:
    """
    End-to-end video pipeline up to inference (no aggregation, no Grad-CAM).
    Streaming over sampled frames, batching inference for CPU.
    """

    log = get_logger("video_pipeline", job_id=job_id, stage="pipeline")
    detector = get_face_detector()
    model_info = get_model()
    storage = StorageService()

    per_frame: list[FramePrediction] = []
    batch_tensors: list[Any] = []
    batch_meta: list[tuple[int, int, tuple[int, int, int, int], np.ndarray]] = []
    # Holds only minimal data for Grad-CAM (resized face crop) for Top-K frames.
    topk: list[dict[str, Any]] = []

    frames_sampled = 0
    frames_with_face = 0
    skipped_no_face = 0
    skipped_error = 0
    early_exit_triggered = False
    early_exit_reason: str | None = None
    warnings: list[str] = []

    t0 = time.perf_counter()

    def _maybe_early_exit_placeholder() -> bool:
        # Placeholder hook: real early-exit logic will be implemented in a later step.
        return False

    try:
        # Stage: frame_extraction (sampling)
        job_svc.set_stage(job_id=job_id, stage=ProcessingStage.frame_extraction)

        # Stream sampled frames; cap enforced by sampler.
        sampled_iter = iter_sampled_frames(video_path)

        # Move into face detection stage once we start consuming frames.
        job_svc.set_stage(job_id=job_id, stage=ProcessingStage.face_detection)

        for sf in sampled_iter:
            frames_sampled += 1
            # Progress based on sampled frames (bounded by max_frames cap).
            job_svc.update_progress(
                job_id=job_id,
                stage=ProcessingStage.face_detection,
                within_stage_percent=min(1.0, frames_sampled / float(settings.video.max_frames)),
            )

            det = detector.detect_largest_face(sf.frame_bgr, job_id=job_id)
            if det is None:
                skipped_no_face += 1
                continue

            frames_with_face += 1
            try:
                # Validate crop before preprocessing.
                face_rgb = _crop_rgb(sf.frame_bgr, det.bbox_xyxy)
                if face_rgb is None or face_rgb.size == 0:
                    skipped_error += 1
                    continue
                # Minimize memory: keep only a small (224x224) RGB crop for Top-K explainability.
                face_rgb_224 = cv2.resize(face_rgb, (224, 224), interpolation=cv2.INTER_AREA)
                t = preprocess_face_rgb(face_rgb)
                batch_tensors.append(t)
                batch_meta.append((sf.frame_index, sf.timestamp_ms, det.bbox_xyxy, face_rgb_224))
            except Exception as e:
                skipped_error += 1
                log.warning("preprocess_or_crop_failed", extra={"reason": str(e)})
                continue

            if len(batch_tensors) >= settings.inference.batch_size:
                job_svc.set_stage(job_id=job_id, stage=ProcessingStage.inference)
                preds = predict_batch(batch_tensors)
                for (fi, ts, bbox, face_rgb_224), pr in zip(batch_meta, preds, strict=False):
                    per_frame.append(FramePrediction(frame_index=fi, timestamp_ms=ts, p_fake=pr.p_fake, face_bbox=bbox))
                    # Maintain Top-K suspicious candidates for Grad-CAM (K=5).
                    cand = {"frame_index": fi, "timestamp_ms": ts, "p_fake": pr.p_fake, "face_bbox": bbox, "face_rgb_224": face_rgb_224}
                    topk.append(cand)
                    topk.sort(key=lambda d: float(d["p_fake"]), reverse=True)
                    if len(topk) > int(settings.inference.top_k_explainability):
                        topk.pop()
                batch_tensors.clear()
                batch_meta.clear()

                job_svc.update_progress(
                    job_id=job_id,
                    stage=ProcessingStage.inference,
                    within_stage_percent=min(1.0, len(per_frame) / float(settings.video.max_frames)),
                )

                if _maybe_early_exit_placeholder():
                    early_exit_triggered = True
                    early_exit_reason = "placeholder"
                    break

            if len(per_frame) >= settings.video.max_frames:
                break

            # Performance warning if unusually slow.
            elapsed = time.perf_counter() - t0
            if frames_sampled >= 30 and elapsed / max(1, frames_sampled) > 0.5:
                warnings.append("Slow processing detected; consider enabling downscaling.")
                log.warning("slow_processing_warning", extra={"frames_sampled": frames_sampled})

        # Flush remaining batch (streaming: only leftover buffer)
        if batch_tensors and len(per_frame) < settings.video.max_frames:
            job_svc.set_stage(job_id=job_id, stage=ProcessingStage.inference)
            preds = predict_batch(batch_tensors)
            for (fi, ts, bbox, face_rgb_224), pr in zip(batch_meta, preds, strict=False):
                per_frame.append(FramePrediction(frame_index=fi, timestamp_ms=ts, p_fake=pr.p_fake, face_bbox=bbox))
                cand = {"frame_index": fi, "timestamp_ms": ts, "p_fake": pr.p_fake, "face_bbox": bbox, "face_rgb_224": face_rgb_224}
                topk.append(cand)
                topk.sort(key=lambda d: float(d["p_fake"]), reverse=True)
                if len(topk) > int(settings.inference.top_k_explainability):
                    topk.pop()
            batch_tensors.clear()
            batch_meta.clear()

        # Enforce strict per_frame cap
        per_frame = per_frame[: settings.video.max_frames]

        processing_ms = int((time.perf_counter() - t0) * 1000)
        log.info(
            "pipeline_summary",
            extra={
                "frames_sampled": frames_sampled,
                "frames_with_face": frames_with_face,
                "skipped_no_face": skipped_no_face,
                "skipped_error": skipped_error,
                "count": len(per_frame),
                "elapsed_ms": processing_ms,
            },
        )

        # Step 15/16: low-confidence handling + scoring/labels
        low_confidence = frames_with_face < int(settings.face.min_face_frames_for_confident_result)
        low_confidence_reason = None
        if low_confidence:
            low_confidence_reason = "insufficient_face_frames"

        # Step 16: robust aggregation (top 30% + trimmed mean), with small-sample fallback.
        job_svc.set_stage(job_id=job_id, stage=ProcessingStage.aggregation)
        probs = [fp.p_fake for fp in per_frame]
        final_score, frames_used_for_score, aggregation_debug = _aggregate_score(probs)
        if final_score is not None:
            final_score = max(0.0, min(1.0, float(final_score)))

        confidence_label = "Low Confidence" if low_confidence or final_score is None else _score_to_confidence_label(final_score)

        if model_info.weights_path is None:
            warnings.append("Model weights not fine-tuned: using ImageNet backbone weights.")

        aggregation_method = "robust_top30_trimmed_mean"
        aggregation_formula = (
            "p = sorted(p_fake, desc); S = top ceil(0.30 * n); "
            "if |S| >= 3 and |S| >= 10: trim t=round(0.10*|S|) from both ends; score = mean(S)"
        )
        confidence_explanation = (
            "Score is computed from per-frame fake probabilities using a robust rule. "
            "If fewer than 5 face-frames are available, we fall back to a simple mean. "
            "Otherwise we sort descending, take the top 30%, optionally trim 10% from both ends "
            "(only when the selected slice is large enough), then take the mean."
        )
        interpretation = _score_interpretation(final_score)
        analysis_completed_at = time.time()

        th = float(settings.inference.fake_decision_threshold)
        result_summary = {
            "final_score": final_score,
            "decision_threshold": th,
            "predicted_manipulation": predicted_manipulation(
                final_score=final_score,
                low_confidence=low_confidence,
                threshold=th,
            ),
            "confidence_label": confidence_label,
            "confidence_explanation": confidence_explanation,
            "aggregation_method": aggregation_method,
            "aggregation_formula": aggregation_formula,
            "frames_used_for_score": frames_used_for_score,
            "aggregation_debug": aggregation_debug,
            "score_interpretation": interpretation,
            "low_confidence": low_confidence,
            "low_confidence_reason": low_confidence_reason,
            "analysis_completed_at": analysis_completed_at,
            "model_version": model_info.model_version,
            "pipeline_version": "0.1.0",
        }

        log.info(
            "aggregation_summary",
            extra={
                "top_k_count": aggregation_debug.get("top_k"),
                "trimmed_count": aggregation_debug.get("trim_n", 0) * 2,
                "final_score": final_score if final_score is not None else -1,
            },
        )

        log.info(
            "final_result_summary",
            extra={
                "score": final_score if final_score is not None else -1,
                "label": confidence_label,
                "low_confidence": low_confidence,
                "frames_used_for_score": frames_used_for_score,
            },
        )

        # Step 18: Grad-CAM integration (Top-K suspicious) AFTER inference is complete.
        job_svc.set_stage(job_id=job_id, stage=ProcessingStage.explainability)
        overlays: dict[int, str] = {}
        top_k_payload: list[dict[str, Any]] = []
        explainability_meta = {
            "method": "gradcam",
            "top_k": int(settings.inference.top_k_explainability),
            "target_class": 1,
            "overlay_alpha": float(settings.inference.gradcam_overlay_alpha),
        }
        requested = min(int(settings.inference.top_k_explainability), len(topk))
        generated = 0
        failures = 0
        time_budget_ms = int(settings.inference.gradcam_time_budget_ms)
        cam_start = time.perf_counter()
        try:
            cam = GradCam(model_info.model, default_efficientnet_target_layer(model_info.model))
            # Ensure top_k_suspicious is sorted by p_fake descending.
            topk_sorted = sorted(topk, key=lambda d: float(d["p_fake"]), reverse=True)[:requested]
            for item in topk_sorted:
                if time_budget_ms > 0 and (time.perf_counter() - cam_start) * 1000.0 > time_budget_ms:
                    warnings.append("Grad-CAM time budget reached; some heatmaps were skipped.")
                    break
                fi = int(item["frame_index"])
                face_rgb = item["face_rgb_224"]
                # Recreate tensor (grad enabled) for Grad-CAM.
                try:
                    t = preprocess_face_rgb(face_rgb).unsqueeze(0).to(device="cpu").contiguous()
                    res = cam.generate(
                        t,
                        class_index=1,
                        overlay_alpha=float(settings.inference.gradcam_overlay_alpha),
                        frame_index=fi,
                    )
                    png_bytes = encode_png_bytes(res.overlay_bgr)
                    stored = storage.save_heatmap_overlay(job_id=job_id, frame_index=fi, png_bytes=png_bytes)
                    if not stored.key.startswith("artifacts/"):
                        raise AppError(code=ErrorCode.STORAGE_ERROR, message="Invalid artifact key returned", details={"key": stored.key})
                    name = stored.key.split("/")[-1]
                    url = f"{settings.storage.artifact_url_prefix}/{job_id}/{name}"
                    overlays[fi] = url
                    top_k_payload.append(
                        {
                            "frame_index": fi,
                            "timestamp_ms": int(item["timestamp_ms"]),
                            "p_fake": float(item["p_fake"]),
                            "heatmap_overlay_url": url,
                        }
                    )
                    generated += 1
                except Exception as e:
                    failures += 1
                    log.warning("gradcam_frame_failed", extra={"frame_index": fi, "reason": str(e)})
        except Exception as e:
            warnings.append("Grad-CAM generation failed for one or more frames.")
            log.warning("gradcam_integration_failed", extra={"reason": str(e)})
        finally:
            try:
                cam.close()  # type: ignore[has-type]
            except Exception:
                pass

        # Sort payload by p_fake descending for frontend.
        top_k_payload.sort(key=lambda d: float(d.get("p_fake", 0.0)), reverse=True)
        log.info(
            "gradcam_summary",
            extra={"requested": requested, "generated": generated, "failures": failures},
        )

        return {
            **result_summary,
            "low_confidence": low_confidence,
            "low_confidence_reason": low_confidence_reason,
            "frames_sampled": frames_sampled,
            "frames_with_face": frames_with_face,
            "skipped_no_face": skipped_no_face,
            "skipped_error": skipped_error,
            "early_exit_triggered": early_exit_triggered,
            "early_exit_reason": early_exit_reason,
            "processing_ms": processing_ms,
            "warnings": warnings,
            "explainability": explainability_meta,
            "heatmaps_generated": generated,
            "top_k_suspicious": top_k_payload,
            "per_frame": [
                {
                    "frame_index": fp.frame_index,
                    "timestamp_ms": fp.timestamp_ms,
                    "p_fake": fp.p_fake,
                    "face_bbox": list(fp.face_bbox),
                    "heatmap_overlay_url": overlays.get(fp.frame_index),
                }
                for fp in per_frame
            ],
        }
    except AppError:
        raise
    except Exception as e:
        log.exception("pipeline_failed")
        raise AppError(code=ErrorCode.INTERNAL_ERROR, message="Pipeline failed", job_id=job_id, details={"reason": str(e)}) from e


def _score_to_confidence_label(score: float) -> str:
    """
    Categorize the final score into a user-friendly, authoritative label.
    """

    if score >= 0.85:
        return "Deepfake Detected"
    if score >= 0.65:
        return "High Suspicion"
    if score >= 0.40:
        return "Inconclusive"
    return "Authenticity Verified"


def _score_interpretation(score: float | None) -> dict[str, Any]:
    if score is None:
        return {"text": "Insufficient biometric data to verify authenticity.", "range": None}
    if score >= 0.85:
        return {"text": "Strong structural anomalies detected in facial regions. Content is highly likely synthesized by AI.", "range": "0.85-1.00"}
    if score >= 0.65:
        return {"text": "Significant inconsistencies detected. Advanced manipulation patterns are present.", "range": "0.65-0.84"}
    if score >= 0.40:
        return {"text": "Minor artifacts detected. Unable to verify authenticity with absolute certainty.", "range": "0.40-0.64"}
    return {"text": "No evidence of AI-generated manipulation detected. Media shows natural biometric consistency.", "range": "0.00-0.39"}


def _aggregate_score(probs: list[float]) -> tuple[float | None, int, dict[str, Any]]:
    """
    Step 16: Robust aggregation.

    Deterministic rule:
    1) Sort probabilities descending (stable/deterministic for equal values)
    2) Take top fraction (default 30%)
    3) If selected slice is large enough, trim trim_fraction (default 10%) from both ends
    4) Compute mean

    Fallback:
    - If <5 probabilities overall, return mean of all.

    Notes:
    - Uses float64 accumulation for numerical stability.
    - Clamping to [0,1] is applied by the caller after aggregation.
    """

    n = len(probs)
    if n == 0:
        return None, 0, {"n": 0, "top_k": 0, "trim_n": 0, "used": 0, "method": "none"}

    # Fast path: uniform probabilities.
    if all(p == probs[0] for p in probs):
        v = float(probs[0])
        used = n if n < int(settings.aggregation.small_sample_fallback_threshold) else max(1, int(round(n * float(settings.aggregation.top_fraction))))
        return v, used, {"n": n, "top_k": used, "trim_n": 0, "used": used, "method": "uniform_fast_path"}

    if n < int(settings.aggregation.small_sample_fallback_threshold):
        mean = float(np.mean(np.array(probs, dtype=np.float64)))
        return mean, n, {"n": n, "top_k": n, "trim_n": 0, "used": n, "method": "fallback_mean"}

    # Deterministic sorting: include original index as secondary key.
    indexed = list(enumerate(probs))
    indexed.sort(key=lambda x: (-float(x[1]), x[0]))
    sorted_desc = [float(v) for _, v in indexed]

    top_k = max(1, int(round(n * float(settings.aggregation.top_fraction))))
    top_slice = sorted_desc[:top_k]

    trim_n = 0
    # Guard: skip trimming when selected slice is too small (<3).
    if len(top_slice) >= 3 and len(top_slice) >= int(settings.aggregation.min_frames_for_trim) and float(settings.aggregation.trim_fraction) > 0.0:
        trim_n = int(round(len(top_slice) * float(settings.aggregation.trim_fraction)))
        if 2 * trim_n < len(top_slice):
            top_slice = top_slice[trim_n : len(top_slice) - trim_n]
        else:
            trim_n = 0

    used = len(top_slice)
    if used == 0:
        return None, 0, {"n": n, "top_k": top_k, "trim_n": trim_n, "used": 0, "method": "empty_after_trim"}

    score = float(np.mean(np.array(top_slice, dtype=np.float64)))
    debug = {"n": n, "top_k": top_k, "trim_n": trim_n, "used": used, "method": "top30_trimmed_mean"}
    return score, used, debug

