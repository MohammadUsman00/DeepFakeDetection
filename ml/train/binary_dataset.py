"""
Binary face-image dataset: label 0 = real, 1 = fake (matches inference predictor).
Expected layout:

    data_root/
      train/
        real/   *.jpg, *.jpeg, *.png
        fake/
      val/
        real/
        fake/
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image
from torch.utils.data import Dataset

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _collect_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(folder.rglob("*")):
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            out.append(p)
    return out


class BinaryFaceFolderDataset(Dataset):
    """Loads images from two subfolders with explicit real/fake labels."""

    def __init__(
        self,
        real_dir: Path,
        fake_dir: Path,
        transform: Callable,
    ) -> None:
        self.transform = transform
        self._items: list[tuple[Path, int]] = []
        for p in _collect_images(Path(real_dir)):
            self._items.append((p, 0))
        for p in _collect_images(Path(fake_dir)):
            self._items.append((p, 1))

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int):
        path, label = self._items[idx]
        img = Image.open(path).convert("RGB")
        return self.transform(img), label


def train_val_from_root(data_root: Path) -> tuple[Path, Path, Path, Path]:
    root = Path(data_root)
    tr, tf = root / "train" / "real", root / "train" / "fake"
    vr, vf = root / "val" / "real", root / "val" / "fake"
    return tr, tf, vr, vf
