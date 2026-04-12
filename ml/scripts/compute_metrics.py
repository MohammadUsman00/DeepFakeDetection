#!/usr/bin/env python3
"""
Minimal offline metrics from a CSV with columns: label,score
- label: 0 = real, 1 = fake (or use --fake-is-one)
- score: model fake probability or score in [0,1]

Usage:
  python compute_metrics.py --csv predictions.csv

No sklearn required; AUC uses trapezoid rule on ROC curve.
"""
from __future__ import annotations

import argparse
import csv


def roc_points(labels: list[int], scores: list[float]) -> tuple[list[float], list[float]]:
    """Returns (fpr_list, tpr_list) including (0,0) and (1,1)."""
    pairs = sorted(zip(scores, labels), key=lambda x: x[0])
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        raise ValueError("Need both classes for ROC-AUC")

    tp = fp = 0
    fpr: list[float] = [0.0]
    tpr: list[float] = [0.0]
    i = 0
    n = len(pairs)
    while i < n:
        thresh = pairs[i][0]
        while i < n and pairs[i][0] == thresh:
            _, y = pairs[i]
            if y == 1:
                tp += 1
            else:
                fp += 1
            i += 1
        fpr.append(fp / n_neg)
        tpr.append(tp / n_pos)
    fpr.append(1.0)
    tpr.append(1.0)
    return fpr, tpr


def auc_trapezoid(x: list[float], y: list[float]) -> float:
    s = 0.0
    for i in range(1, len(x)):
        s += (x[i] - x[i - 1]) * (y[i] + y[i - 1]) / 2.0
    return max(0.0, min(1.0, s))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True, help="CSV with header: label,score")
    args = p.parse_args()

    labels: list[int] = []
    scores: list[float] = []
    with open(args.csv, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            labels.append(int(row["label"].strip()))
            scores.append(float(row["score"].strip()))

    fpr, tpr = roc_points(labels, scores)
    auc = auc_trapezoid(fpr, tpr)
    print(f"n={len(labels)} ROC-AUC={auc:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
