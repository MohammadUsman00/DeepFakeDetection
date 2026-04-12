# Training: EfficientNet-B0 binary classifier

Aligned with the API inference convention: **class 0 = real**, **class 1 = fake**.

## Dataset layout

Prepare face crops (e.g. extracted with MTCNN from FaceForensics++ or your own source):

```text
your_dataset/
  train/
    real/   # PNG/JPG face crops, authentic
    fake/   # PNG/JPG face crops, manipulated
  val/
    real/
    fake/
```

Use **video-level or identity-level splits** so the same person does not appear in both train and val.

## Run

From the repository root (with the same Python env as the backend — PyTorch installed):

```bash
python ml/train/train_efficientnet.py --data-root ./data/my_dataset --epochs 10 --batch-size 32 --out ./data/models/efficientnet_b0.pth
```

Outputs:

- `efficientnet_b0.pth` — checkpoint (`state_dict` + metadata; compatible with `model_loader.py`)
- `efficientnet_b0.json` — training metadata (best val accuracy, etc.)

## Use the checkpoint in the API

Set the environment variable to the saved file (or place the file at the default path in `config.py`):

```text
INFER_MODEL_WEIGHTS_PATH=/absolute/path/to/efficientnet_b0.pth
```

Restart the API/worker so weights reload.

## Notes

- Training defaults to **CUDA** if available; pass `--device cpu` for CPU-only training (slower).
- Match preprocessing to inference: ImageNet normalization, 224×224 (see script).
- For thesis-quality results, report metrics on a held-out test set (see `docs/ML_EVALUATION.md`).
