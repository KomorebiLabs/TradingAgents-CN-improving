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

import json
import math
import time
import uuid
from dataclasses import asdict, fields as dataclass_fields, replace
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

from tradingagents.application.contracts import (
    AnalysisRequest,
    AnalysisResult,
    extract_confidence_from_state,
    normalize_trade_date,
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


def calibrate_compression_threshold(
    stats_paths: List[Path], percentile: float = 0.75, min_samples: int = 10
) -> Optional[int]:
    """Calculate a character threshold from persisted phase statistics.

    Both the new ``estimated_chars`` field and the old
    ``context_estimate`` field are accepted while existing run artifacts
    migrate. Fewer than ``min_samples`` values deliberately returns ``None``;
    a provisional config threshold must not be silently replaced by a small
    sample.
    """
    if not 0 < percentile < 1 or min_samples < 1:
        raise ValueError("percentile must be between 0 and 1; min_samples must be positive")
    values: List[float] = []
    for path in stats_paths:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            continue
        for phase in payload.get("phases", []) if isinstance(payload, dict) else []:
            if not isinstance(phase, dict):
                continue
            value = phase.get("estimated_chars", phase.get("context_estimate"))
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                values.append(float(value))
    if len(values) < min_samples:
        return None
    values.sort()
    rank = (len(values) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        result = values[lower]
    else:
        fraction = rank - lower
        result = values[lower] + (values[upper] - values[lower]) * fraction
    return int(round(result))


def _default_graph_factory():
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    return TradingAgentsGraph


class AnalysisEventStream:
    """Iterator over one run's events; ``result`` is set after exhaustion."""

    def __init__(
        self,
        request: AnalysisRequest,
        graph,
        stats_handler,
        translator: ChunkEventTranslator,
        run_id: Optional[str] = None,
        resume: bool = False,
        resume_payload: Optional[Dict[str, Any]] = None,
        request_warnings: Optional[List[str]] = None,
    ):
        self.request = request
        self.stats_handler = stats_handler
        self._graph = graph
        self._translator = translator
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.resume = resume
        self.resume_payload = resume_payload
        self._request_warnings = list(request_warnings or [])
        self._inner = None
        self.result: Optional[AnalysisResult] = None
        # Artifact paths (created eagerly, before any streaming). One
        # directory per run: reports/<ticker>/<date>/<run_id>/ (E7 trace;
        # pre-run_id layouts stay readable — nothing reads them by pattern).
        self.results_dir = (
            _PROJECT_ROOT / "reports" / request.ticker / request.trade_date / self.run_id
        )
        self.report_dir = self.results_dir / "reports"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        # Persist the request so a crashed run can be rebuilt and resumed
        # (E1): --resume <run_id> reloads exactly this config.
        request_file = self.results_dir / "request.json"
        try:
            request_file.write_text(
                json.dumps(asdict(request), ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except OSError:
            pass  # artifact persistence is best-effort; the run continues
        self._start_time = time.time()

    def mark_abandoned(self, reason: str, choice: str = "abort") -> Path:
        """Persist an explicit HumanGate abort outcome and consumed cost context."""
        stats = self.stats_handler.get_stats() if self.stats_handler is not None else {}
        artifact = {
            "run_id": self.run_id,
            "ticker": self.request.ticker,
            "trade_date": self.request.trade_date,
            "choice": choice,
            "reason": reason,
            "costs": stats,
            "timestamp": time.time(),
        }
        path = self.results_dir / "abandoned.json"
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def __iter__(self) -> Iterator[AnalysisEvent]:
        from tradingagents.agents.utils.untrusted_wrap import (
            finish_security_context,
            start_security_context,
        )
        from tradingagents.dataflows.vendor_health import TRACKER as VENDOR_HEALTH

        # Health is scoped to this run for the single-run CLI/API contract.
        # The tracker itself remains process-wide so screener and dataflow
        # adapters share one schema and one artifact format.
        VENDOR_HEALTH.reset()
        start_security_context(self.run_id)
        try:
            yield from self._iter_impl()
        finally:
            audit = finish_security_context()
            try:
                (self.results_dir / "security_audit.json").write_text(
                    json.dumps(audit, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except OSError:
                pass
            try:
                (self.results_dir / "vendor_health.json").write_text(
                    json.dumps(
                        {
                            "run_id": self.run_id,
                            "ticker": self.request.ticker,
                            "trade_date": self.request.trade_date,
                            "vendors": VENDOR_HEALTH.snapshot(),
                            "summary": VENDOR_HEALTH.summary_lines(),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except OSError:
                pass

    def _iter_impl(self) -> Iterator[AnalysisEvent]:
        from tradingagents.application.events import AnalysisStarted, TimelineNoted
        from tradingagents.agents.utils.untrusted_wrap import security_audit_snapshot

        security_entry_index = 0

        yield AnalysisStarted(
            ticker=self.request.ticker,
            trade_date=self.request.trade_date,
            selected_analysts=tuple(self.request.analyst_keys()),
            run_id=self.run_id,
        )

        callbacks = [self.stats_handler] if self.stats_handler is not None else None
        self._inner = self._graph.stream_analysis(
            self.request.ticker,
            self.request.trade_date,
            callbacks=callbacks,
            resume=self.resume,
            resume_payload=self.resume_payload,
        )
        for chunk in self._inner:
            for event in self._translator.translate(chunk, self.request.analyst_keys()):
                yield event
            audit = security_audit_snapshot()
            for entry in audit["entries"][security_entry_index:]:
                yield TimelineNoted(
                    text=f"injection_filtered: {entry['source']} x{entry['count']}"
                )
            security_entry_index = len(audit["entries"])

        final_state = self._inner.final_state if self._inner.final_state is not None else {}
        decision = self._inner.decision if self._inner.final_state is not None else "N/A"
        yield AnalysisCompleted(final_state=final_state, decision=decision)

        # A3 instrumentation: dump per-phase context sizes from the
        # orchestration event trail so the compression threshold can be
        # recalibrated from a real distribution (P75 rule) instead of guesswork.
        try:
            trail = (
                (final_state.get("orchestration") or {}).get("event_trail")
                or []
            )
            stats_dump = {
                "run_id": self.run_id,
                "ticker": self.request.ticker,
                "trade_date": self.request.trade_date,
                "phases": [
                    {
                        "stage": e.get("stage"),
                        "estimated_chars": e.get("context_estimate"),
                        "context_estimate": e.get("context_estimate"),
                    }
                    for e in trail
                    if isinstance(e, dict) and e.get("context_estimate") is not None
                ],
            }
            (self.results_dir / "context_stats.json").write_text(
                json.dumps(stats_dump, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass  # instrumentation is best-effort; never block a finished run

        stats = self.stats_handler.get_stats() if self.stats_handler is not None else {}
        # B2 hard check (the lint half of PIT): this system has NEVER run a
        # backtest — temporal-attribution phrasing in decision texts is
        # fabrication regardless of data level, so it is flagged unconditionally.
        pit_warnings = list(self._request_warnings)
        for label, text in (
            ("final_decision", str(final_state.get("final_trade_decision") or "")),
            ("investment_plan", str(final_state.get("investment_plan") or "")),
        ):
            low = text.lower()
            for phrase in ("历史回测", "回测显示", "回测表明", "backtest show"):
                if phrase in low:
                    pit_warnings.append(
                        f"[PIT-language] {label} 含 '{phrase}' — 系统从未运行回测，"
                        "此类时间归因表述属于虚构"
                    )
        self.result = AnalysisResult(
            ticker=self.request.ticker,
            trade_date=self.request.trade_date,
            run_id=self.run_id,
            decision=decision,
            confidence=extract_confidence_from_state(final_state),
            elapsed_time=time.time() - self._start_time,
            llm_calls=stats.get("llm_calls", 0),
            tool_calls=stats.get("tool_calls", 0),
            tokens_in=stats.get("tokens_in", 0),
            tokens_out=stats.get("tokens_out", 0),
            report_path=self.report_dir,
            final_state=final_state,
            warnings=pit_warnings,
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
        run_id: Optional[str] = None,
        resume: bool = False,
        resume_payload: Optional[Dict[str, Any]] = None,
    ) -> AnalysisEventStream:
        """Start one run and return its event stream.

        The graph is constructed EAGERLY here (not on first iteration) so a
        broken configuration fails before the caller enters any Live context.

        Args:
            request: what to analyze.
            stats_handler: optional callback handler for token/tool stats.
            run_id: reuse an existing run id (resume). Defaults to a fresh one.
            resume: continue the checkpointed thread for ``run_id`` instead of
                starting a new invocation — requires ``run_id`` and a saved
                checkpoint for it.
        """
        if resume and not run_id:
            raise ValueError("resume requires an explicit run_id")
        # Generate the run_id BEFORE building the graph so the checkpointer
        # thread and the artifact/stream id are the SAME id for fresh runs
        # (E1 bug fix: a stream-generated id never reached the graph).
        if not run_id:
            run_id = uuid.uuid4().hex[:12]
        normalized_date, date_warning = normalize_trade_date(request.trade_date)
        request_warnings = [date_warning] if date_warning else []
        if normalized_date != request.trade_date:
            request = replace(request, trade_date=normalized_date)
        graph_cls = self._graph_factory()
        graph = graph_cls(
            list(request.analyst_keys()),
            config=self._effective_config(request),
            debug=self._debug,
            callbacks=[stats_handler] if stats_handler is not None else None,
            run_id=run_id,
        )
        translator = ChunkEventTranslator(
            stats_provider=stats_handler.get_stats if stats_handler is not None else None
        )
        return AnalysisEventStream(
            request, graph, stats_handler, translator,
            run_id=run_id, resume=resume,
            resume_payload=resume_payload,
            request_warnings=request_warnings,
        )

    @staticmethod
    def _effective_config(request: AnalysisRequest) -> Dict[str, Any]:
        """Graph config with the file-level portfolio fallback applied (B3):
        an explicit request portfolio wins; otherwise ~/.tradingagents/portfolio.json."""
        config = request.to_graph_config()
        if request.portfolio_context is None:
            from tradingagents.agents.utils.portfolio_context import load_portfolio

            portfolio = load_portfolio()
            if portfolio:
                config["portfolio_context"] = portfolio
        return config

    @staticmethod
    def find_run(run_id: str) -> Optional[Path]:
        """Locate the artifact directory of a past run by its run_id."""
        for request_file in (_PROJECT_ROOT / "reports").glob(f"*/*/{run_id}/request.json"):
            return request_file.parent
        return None

    @classmethod
    def resume_run(
        cls,
        run_id: str,
        stats_handler: Optional[Any] = None,
        graph_factory=None,
        debug: bool = True,
    ) -> "AnalysisEventStream":
        """Rebuild the request saved for ``run_id`` and continue its thread.

        Raises FileNotFoundError when no artifacts exist for the run_id.
        """
        run_dir = cls.find_run(run_id)
        if run_dir is None:
            raise FileNotFoundError(
                f"No saved run found for run_id={run_id!r} "
                f"(expected reports/<ticker>/<date>/{run_id}/request.json)"
            )
        data = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
        known = {f.name for f in dataclass_fields(AnalysisRequest)}
        request = AnalysisRequest(
            **{k: v for k, v in data.items() if k in known}
        )
        service = cls(graph_factory=graph_factory, debug=debug)
        return service.stream_events(
            request, stats_handler=stats_handler, run_id=run_id, resume=True
        )

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
