"""Confusion matrix + accuracy aggregates for the R10 evaluation set."""

from __future__ import annotations

from typing import Dict

DECISIONS = ["BUY", "HOLD", "SELL"]
LABELS = ["BUY", "SELL", "NEUTRAL"]


def normalize_decision(value: object) -> str:
    """Normalize model output into the evaluator's decision vocabulary.

    Unknown, empty, and missing outputs are treated as HOLD so the matrix
    remains total; callers can inspect the raw decision in the run record.
    """
    normalized = str(value or "").strip().upper()
    return normalized if normalized in DECISIONS else "HOLD"


def decision_warning(value: object) -> str | None:
    """Return an audit warning when a raw model decision is not recognized."""
    normalized = str(value or "").strip().upper()
    if normalized in DECISIONS:
        return None
    return f"Unknown decision normalized to HOLD: {value!r}"


def confusion_matrix(true_labels: list, predictions: list) -> Dict[str, Dict[str, int]]:
    """Build {true_label: {predicted: count}} (rows=ground truth, cols=prediction)."""
    m: Dict[str, Dict[str, int]] = {t: {p: 0 for p in DECISIONS} for t in LABELS}
    for label, pred in zip(true_labels, predictions):
        label = label if label in LABELS else "NEUTRAL"
        pred = normalize_decision(pred)
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
