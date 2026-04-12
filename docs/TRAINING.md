# Full pipeline: data to deployed model

## 1. Face crops

The deployed system operates on **face crops** (same as training). For video datasets:

1. Sample frames (similar FPS cap as production if possible).
2. Run face detection (MTCNN or equivalent).
3. Save aligned crops to `train/real`, `train/fake`, `val/real`, `val/fake`.

You can reuse logic from `backend/app/ml/preprocessing/face_detector.py` in a separate offline script if needed.

## 2. Train

See [`ml/train/README.md`](../ml/train/README.md). The trainer saves a checkpoint compatible with `INFER_MODEL_WEIGHTS_PATH`.

## 3. Evaluate (offline)

Export per-image or per-video scores and labels, then use `ml/scripts/compute_metrics.py` or sklearn for ROC-AUC / EER. Document splits and datasets in your thesis.

## 4. Deploy

- Copy or mount the `.pth` file into the runtime (e.g. `data/models/`).
- Set `INFER_MODEL_WEIGHTS_PATH` and optionally `INFER_MODEL_VERSION` for traceability.
- Rebuild/restart API and Celery workers.

## 5. Limitations

Fine-tuned models can overfit to compression and datasets. Report domain-shift limitations and avoid overstating legal “proof.”
