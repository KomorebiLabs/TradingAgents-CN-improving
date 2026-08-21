"""Runner for the R10 decision-correctness evaluation set.

``run_case_set`` consumes any object exposing ``run(request, on_event) ->
AnalysisResult`` (real AnalysisService or a test stub), so the framework is
offline-testable; real runs need an LLM key.
"""

from __future__ import annotations

from typing import Callable, List, TypedDict

from tradingagents.application.contracts import AnalysisRequest
from tradingagents.eval.cases import EvaluationCase
from tradingagents.eval.matrix import decision_warning, normalize_decision


class EvaluationRecord(TypedDict, total=False):
    """Stable per-case record consumed by matrix and report builders."""

    case: EvaluationCase
    decision: str
    normalized_decision: str
    normalization_warning: str | None
    label: str
    horizon_return: float | None
    confidence: float | None
    elapsed_time: float | None
    llm_calls: int
    tool_calls: int
    tokens_in: int
    tokens_out: int
    warnings: List[str]
    provider: str
    research_depth: int


def run_case_set(
    service,
    cases: List[EvaluationCase],
    provider: str = "deepseek",
    on_event: Callable = lambda e: None,
) -> List[EvaluationRecord]:
    results: List[EvaluationRecord] = []
    for case in cases:
        request = AnalysisRequest(
            ticker=case.ticker,
            trade_date=case.eval_date,
            research_depth=1,
            llm_provider=provider,
        )
        result = service.run(request, on_event=on_event)
        raw_decision = getattr(result, "decision", "N/A")
        warning = decision_warning(raw_decision)
        warnings = list(getattr(result, "warnings", []) or [])
        if warning and warning not in warnings:
            warnings.append(warning)
        results.append(
            {
                "case": case,
                "decision": raw_decision,
                "normalized_decision": normalize_decision(raw_decision),
                "normalization_warning": warning,
                "label": case.label,
                "horizon_return": case.horizon_return,
                "confidence": getattr(result, "confidence", None),
                "elapsed_time": getattr(result, "elapsed_time", None),
                "llm_calls": getattr(result, "llm_calls", 0),
                "tool_calls": getattr(result, "tool_calls", 0),
                "tokens_in": getattr(result, "tokens_in", 0),
                "tokens_out": getattr(result, "tokens_out", 0),
                "warnings": warnings,
                "provider": request.llm_provider,
                "research_depth": request.research_depth,
            }
        )
    return results
