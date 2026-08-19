"""Evaluation (R10): decision-correctness test set vs known historical outcomes.

    cases.py   EvaluationCase + deterministic forward-return labels
    matrix.py  confusion matrix + directional/overall accuracy (pure)
    runner.py  run each case through the decision chain (service-driven)
    report.py  markdown evaluation report
    __main__.py CLI: python -m tradingagents.eval --tickers ... --date ...
"""

from __future__ import annotations

from tradingagents.eval.cases import (
    BUY_THRESHOLD,
    SELL_THRESHOLD,
    EvaluationCase,
    build_case_set,
    label_from_return,
)
from tradingagents.eval.matrix import confusion_matrix, directional_stats, overall_accuracy
from tradingagents.eval.runner import run_case_set

__all__ = [
    "BUY_THRESHOLD",
    "SELL_THRESHOLD",
    "EvaluationCase",
    "build_case_set",
    "label_from_return",
    "confusion_matrix",
    "directional_stats",
    "overall_accuracy",
    "run_case_set",
]
