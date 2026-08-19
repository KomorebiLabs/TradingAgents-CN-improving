"""Ablation module (R4): quantify whether the multi-agent machinery actually helps.

Runs the SAME set of tickers through controlled configurations:
  - analyst count   (single vs all four)
  - debate depth    (off / 1 round / 3 rounds)
and aggregates per-config repeat outcomes (decision distribution, consistency,
confidence spread, cost) into a comparison report.

The runner's ``run_configuration`` is service-based, so it is fully testable
offline with a stubbed AnalysisService; real runs need an LLM key and consume
tokens (documented in the report).
"""

from tradingagents.ablation.configs import AblationConfig, build_matrix, DEFAULT_TICKERS
from tradingagents.ablation.runner import run_configuration
from tradingagents.ablation.report import build_report
from tradingagents.ablation.stability import aggregate_outcomes

__all__ = [
    "AblationConfig",
    "build_matrix",
    "DEFAULT_TICKERS",
    "run_configuration",
    "aggregate_outcomes",
    "build_report",
]
