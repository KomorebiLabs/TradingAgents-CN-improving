"""Runner for the R10 decision-correctness evaluation set.

``run_case_set`` consumes any object exposing ``run(request, on_event) ->
AnalysisResult`` (real AnalysisService or a test stub), so the framework is
offline-testable; real runs need an LLM key.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from tradingagents.application.contracts import AnalysisRequest
from tradingagents.eval.cases import EvaluationCase


def run_case_set(
    service,
    cases: List[EvaluationCase],
    provider: str = "deepseek",
    on_event: Callable = lambda e: None,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for case in cases:
        request = AnalysisRequest(
            ticker=case.ticker,
            trade_date=case.eval_date,
            research_depth=1,
            llm_provider=provider,
        )
        result = service.run(request, on_event=on_event)
        results.append(
            {
                "case": case,
                "decision": getattr(result, "decision", "N/A"),
                "label": case.label,
                "horizon_return": case.horizon_return,
            }
        )
    return results
