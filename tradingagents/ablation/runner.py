"""Ablation runner (R4): run one configuration N times, collect decisions + route stats.

``run_configuration`` consumes any object exposing ``run(request, on_event) ->
AnalysisResult`` (the real AnalysisService or a test stub), so the runner is
offline-testable.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from tradingagents.ablation.configs import AblationConfig
from tradingagents.application.contracts import AnalysisRequest
from tradingagents.ablation.stability import aggregate_outcomes


def build_request(
    ticker: str,
    trade_date: str,
    config: AblationConfig,
    provider: str | None = None,
) -> AnalysisRequest:
    """Build the AnalysisRequest for one ablation cell, inheriting defaults."""
    return AnalysisRequest(
        ticker=ticker,
        trade_date=trade_date,
        selected_analysts=config.selected_analysts,
        research_depth=config.research_depth,
        llm_provider=provider if provider else "deepseek",  # codable default; override in real runs
    )


def run_configuration(
    service,
    ticker: str,
    trade_date: str,
    config: AblationConfig,
    n_repeat: int = 2,
    provider: str | None = None,
    on_event: Callable = lambda e: None,
) -> Dict[str, Any]:
    """Run one ablation cell n_repeat times; return outcome + aggregate."""
    outcomes: List[Dict[str, Any]] = []
    for _ in range(n_repeat):
        request = build_request(ticker, trade_date, config, provider)
        result = service.run(request, on_event=on_event)
        outcomes.append(
            {
                "decision": getattr(result, "decision", "N/A"),
                "confidence": getattr(result, "confidence", None),
                "elapsed": getattr(result, "elapsed_time", 0.0),
                "route_events": _route_events(getattr(result, "final_state", {})),
                "compressions": _compressions(getattr(result, "final_state", {})),
            }
        )
    return {
        "config": config.name,
        "description": config.description,
        "ticker": ticker,
        "outcomes": outcomes,
        "aggregate": aggregate_outcomes(outcomes),
    }


def _route_events(final_state: Dict[str, Any]) -> int:
    trail = (final_state.get("orchestration") or {}).get("event_trail") or []
    return len(trail) if isinstance(trail, list) else 0


def _compressions(final_state: Dict[str, Any]) -> int:
    trail = (final_state.get("orchestration") or {}).get("event_trail") or []
    if not isinstance(trail, list):
        return 0
    return sum(1 for e in trail if isinstance(e, dict) and e.get("compression_triggered"))
