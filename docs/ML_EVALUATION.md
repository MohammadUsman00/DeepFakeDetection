# ML evaluation (offline)

## Goals

Report **discrimination** (real vs. fake) and **calibration** honestly. Demo accuracy on a single folder is not sufficient for a defensible thesis.

## Data

- Use public benchmarks (e.g. FaceForensics++ subsets) with **video-level or identity-level splits** so the same person does not appear in train and test.
- Match preprocessing to deployment: face crop size, FPS sampling, compression.

## Splits

- **Train / val / test** by **video id** (or identity), not by frame, to reduce leakage.
- Report dataset name and version in the thesis.

## Metrics (binary fake vs. real)

| Metric | Meaning |
|--------|---------|
| **ROC-AUC** | Threshold-free ranking quality |
| **Average Precision (PR-AUC)** | Informative when classes are imbalanced |
| **EER** | Equal Error Rate: threshold where FPR ≈ FNR |
| **Accuracy @ fixed FPR** | Operational point (e.g. 1% false alarms on real) |

You can export per-video scores from your model and compute metrics with `ml/scripts/compute_metrics.py` (labels 0/1 + scores).

## Limitations to state explicitly

- Domain shift (new codecs, mobile cameras, social recompression).
- Face-only pipeline misses non-face manipulations.
- Grad-CAM explains model attention, not legal ground truth.

## Training tips (brief)

- Fine-tune classifier head (and optionally last blocks) on your split.
- Balance batches; use augmentations that mimic deployment (blur, JPEG, mild noise).
- Track **validation** metrics early; stop when overfitting.
