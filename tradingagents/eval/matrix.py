"""Confusion matrix + accuracy aggregates for the R10 evaluation set."""

from __future__ import annotations

from typing import Dict

DECISIONS = ["BUY", "HOLD", "SELL"]
LABELS = ["BUY", "SELL", "NEUTRAL"]


def confusion_matrix(true_labels: list, predictions: list) -> Dict[str, Dict[str, int]]:
    """Build {true_label: {predicted: count}} (rows=ground truth, cols=prediction)."""
    m: Dict[str, Dict[str, int]] = {t: {p: 0 for p in DECISIONS} for t in LABELS}
    for label, pred in zip(true_labels, predictions):
        label = label if label in LABELS else "NEUTRAL"
        pred = pred if pred in DECISIONS else "HOLD"
        m[label][pred] += 1
    return m


def directional_stats(matrix: Dict[str, Dict[str, int]]) -> Dict[str, float]:
    """On directional ground-truth cases (BUY/SELL), how often did the system pick
    the correct side. A HOLD prediction on a directional case counts as a miss."""
    correct = matrix["BUY"]["BUY"] + matrix["SELL"]["SELL"]
    total = sum(matrix["BUY"].values()) + sum(matrix["SELL"].values())
    return {
        "directional_correct": correct,
        "directional_total": total,
        "directional_accuracy": round(correct / total, 3) if total else 0.0,
    }


def overall_accuracy(matrix: Dict[str, Dict[str, int]]) -> Dict[str, float]:
    total = sum(sum(cols.values()) for cols in matrix.values())
    # correct = BUY->BUY, SELL->SELL, and NEUTRAL ground truth predicted as HOLD
    correct = matrix["BUY"]["BUY"] + matrix["SELL"]["SELL"] + matrix["NEUTRAL"]["HOLD"]
    return {"correct": correct, "total": total, "accuracy": round(correct / total, 3) if total else 0.0}
