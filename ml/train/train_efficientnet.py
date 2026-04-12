#!/usr/bin/env python3
"""
Fine-tune EfficientNet-B0 for binary real vs fake (aligned with backend inference).

Convention: class 0 = real, class 1 = fake (see backend predictor).

Example:
  python ml/train/train_efficientnet.py --data-root ./data/ff_subset --epochs 5 --out ./data/models/efficientnet_b0.pth

Requires: torch, torchvision, pillow (same as backend).
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import transforms
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights

# Same normalization as backend inference (transforms.py)
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

_TRAIN_DIR = Path(__file__).resolve().parent
if str(_TRAIN_DIR) not in sys.path:
    sys.path.insert(0, str(_TRAIN_DIR))

from binary_dataset import BinaryFaceFolderDataset, train_val_from_root


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def build_model() -> nn.Module:
    m = efficientnet_b0(weights=EfficientNet_B0_Weights.DEFAULT)
    in_features = m.classifier[1].in_features
    m.classifier[1] = nn.Linear(in_features, 2)
    return m


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
) -> tuple[float, float]:
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    for x, y in loader:
        x = x.to(device)
        y = y.to(device)
        optimizer.zero_grad()
        logits = model(x)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * y.size(0)
        pred = logits.argmax(dim=1)
        correct += (pred == y).sum().item()
        total += y.size(0)
    return total_loss / max(1, total), correct / max(1, total)


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, criterion: nn.Module, device: torch.device) -> tuple[float, float]:
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    for x, y in loader:
        x = x.to(device)
        y = y.to(device)
        logits = model(x)
        loss = criterion(logits, y)
        total_loss += loss.item() * y.size(0)
        pred = logits.argmax(dim=1)
        correct += (pred == y).sum().item()
        total += y.size(0)
    return total_loss / max(1, total), correct / max(1, total)


def main() -> int:
    p = argparse.ArgumentParser(description="Train EfficientNet-B0 binary deepfake classifier")
    p.add_argument("--data-root", type=Path, required=True, help="Folder with train/{real,fake} val/{real,fake}")
    p.add_argument("--out", type=Path, default=Path("data/models/efficientnet_b0.pth"))
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument(
        "--num-workers",
        type=int,
        default=0 if platform.system() == "Windows" else 4,
        help="DataLoader workers (0 recommended on Windows)",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = p.parse_args()

    set_seed(args.seed)
    device = torch.device(args.device)

    tr, tf, vr, vf = train_val_from_root(args.data_root)
    for name, path in [("train/real", tr), ("train/fake", tf), ("val/real", vr), ("val/fake", vf)]:
        if not path.is_dir():
            print(f"ERROR: missing directory: {path} ({name})")
            return 1

    train_tf = transforms.Compose(
        [
            transforms.Resize((256, 256)),
            transforms.RandomCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(0.1, 0.1, 0.1, 0.05),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )
    val_tf = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )

    ds_tr = BinaryFaceFolderDataset(tr, tf, train_tf)
    ds_va = BinaryFaceFolderDataset(vr, vf, val_tf)
    if len(ds_tr) == 0:
        print("ERROR: no training images found.")
        return 1
    if len(ds_va) == 0:
        print("ERROR: no validation images found.")
        return 1

    print(f"Train samples: {len(ds_tr)} | Val samples: {len(ds_va)}")

    loader_tr = DataLoader(
        ds_tr,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=device.type == "cuda",
    )
    loader_va = DataLoader(
        ds_va,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=device.type == "cuda",
    )

    model = build_model().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)

    best_acc = 0.0
    best_state: dict | None = None
    t0 = time.time()

    for epoch in range(1, args.epochs + 1):
        loss_tr, acc_tr = train_one_epoch(model, loader_tr, criterion, optimizer, device)
        loss_va, acc_va = evaluate(model, loader_va, criterion, device)
        print(f"Epoch {epoch}/{args.epochs}  train_loss={loss_tr:.4f} acc={acc_tr:.4f}  val_loss={loss_va:.4f} val_acc={acc_va:.4f}")
        if acc_va > best_acc:
            best_acc = acc_va
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    if best_state is None:
        best_state = model.state_dict()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state_dict": best_state,
        "meta": {
            "model": "efficientnet_b0",
            "classes": ["real", "fake"],
            "best_val_acc": float(best_acc),
            "epochs": args.epochs,
            "data_root": str(args.data_root.resolve()),
            "train_seconds": round(time.time() - t0, 2),
        },
    }
    torch.save(payload, args.out)
    print(f"\nSaved checkpoint to {args.out.resolve()}")
    print(f"Best val accuracy: {best_acc:.4f}")
    print("\nPoint the backend at this file, e.g.:")
    print(f"  set INFER_MODEL_WEIGHTS_PATH={args.out.resolve()}")
    with open(args.out.with_suffix(".json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in payload["meta"].items()}, f, indent=2)
    print(f"Wrote metadata: {args.out.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
