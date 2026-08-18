"""AnalysisService: the application-layer use case "run one deep analysis".

Sits between the CLI (dashboard/questionnaire) and the graph runtime:
- converts a typed ``AnalysisRequest`` into graph config and runs the graph;
- translates raw state chunks into the stable event protocol;
- assembles the typed ``AnalysisResult``.

The CLI consumes ``stream_events()`` inside its Live-dashboard loop and maps
events to widgets — it never touches LangGraph internals. A Python API (or
future Web API) can call ``run()`` with an ``on_event`` callback instead.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

from tradingagents.application.contracts import (
    AnalysisRequest,
    AnalysisResult,
    extract_confidence_from_state,
)
from tradingagents.application.events import (
    AnalysisCompleted,
    AnalysisEvent,
    ChunkEventTranslator,
)

# Repo root (service.py lives at <root>/tradingagents/application/service.py).
# Report artifacts go to <root>/reports/<ticker>/<date>/, matching the
# pre-service layout that wrote them from cli/analyze/run_impl.py.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _default_graph_factory():
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    return TradingAgentsGraph


class AnalysisEventStream:
    """Iterator over one run's events; ``result`` is set after exhaustion."""

    def __init__(self, request: AnalysisRequest, graph, stats_handler, translator: ChunkEventTranslator):
        self.request = request
        self.stats_handler = stats_handler
        self._graph = graph
        self._translator = translator
        self._inner = None
        self.result: Optional[AnalysisResult] = None
        # Artifact paths (created eagerly, before any streaming).
        self.results_dir = (
            _PROJECT_ROOT / "reports" / request.ticker / request.trade_date
        )
        self.report_dir = self.results_dir / "reports"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._start_time = time.time()

    def __iter__(self) -> Iterator[AnalysisEvent]:
        callbacks = [self.stats_handler] if self.stats_handler is not None else None
        self._inner = self._graph.stream_analysis(
            self.request.ticker,
            self.request.trade_date,
            callbacks=callbacks,
        )
        for chunk in self._inner:
            for event in self._translator.translate(chunk, self.request.analyst_keys()):
                yield event

        final_state = self._inner.final_state if self._inner.final_state is not None else {}
        decision = self._inner.decision if self._inner.final_state is not None else "N/A"
        yield AnalysisCompleted(final_state=final_state, decision=decision)

        stats = self.stats_handler.get_stats() if self.stats_handler is not None else {}
        self.result = AnalysisResult(
            ticker=self.request.ticker,
            trade_date=self.request.trade_date,
            decision=decision,
            confidence=extract_confidence_from_state(final_state),
            elapsed_time=time.time() - self._start_time,
            llm_calls=stats.get("llm_calls", 0),
            tool_calls=stats.get("tool_calls", 0),
            tokens_in=stats.get("tokens_in", 0),
            tokens_out=stats.get("tokens_out", 0),
            report_path=self.report_dir,
            final_state=final_state,
        )


class AnalysisService:
    """Run one deep analysis per ``AnalysisRequest``.

    Args:
        graph_factory: zero-arg callable returning a graph class/constructor
            (injectable for tests; defaults to TradingAgentsGraph).
        debug: forwarded to the graph (pretty-prints streamed messages).
    """

    def __init__(self, graph_factory=None, debug: bool = True):
        self._graph_factory = graph_factory or _default_graph_factory
        self._debug = debug

    def stream_events(
        self,
        request: AnalysisRequest,
        stats_handler: Optional[Any] = None,
    ) -> AnalysisEventStream:
        """Start one run and return its event stream.

        The graph is constructed EAGERLY here (not on first iteration) so a
        broken configuration fails before the caller enters any Live context.
        """
        graph_cls = self._graph_factory()
        graph = graph_cls(
            list(request.analyst_keys()),
            config=request.to_graph_config(),
            debug=self._debug,
            callbacks=[stats_handler] if stats_handler is not None else None,
        )
        translator = ChunkEventTranslator(
            stats_provider=stats_handler.get_stats if stats_handler is not None else None
        )
        return AnalysisEventStream(request, graph, stats_handler, translator)

    def run(
        self,
        request: AnalysisRequest,
        on_event: Optional[Callable[[AnalysisEvent], None]] = None,
    ) -> AnalysisResult:
        """Headless run: consume all events (optionally observing them)."""
        stats_handler = self._make_stats_handler()
        stream = self.stream_events(request, stats_handler=stats_handler)
        for event in stream:
            if on_event is not None:
                on_event(event)
        assert stream.result is not None, "event stream exhausted without a result"
        return stream.result

    @staticmethod
    def _make_stats_handler():
        try:
            from cli.stats_handler import StatsCallbackHandler

            return StatsCallbackHandler()
        except ImportError:
            return None
