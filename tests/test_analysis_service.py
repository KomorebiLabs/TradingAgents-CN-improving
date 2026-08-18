"""Tests for AnalysisService / contracts (typed request -> events -> result)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tradingagents.application import (
    AnalysisCompleted,
    AnalysisRequest,
    AnalysisResult,
    AnalysisService,
    MessageEmitted,
    ReportSectionUpdated,
)
from tradingagents.default_config import DEFAULT_CONFIG


class TestContracts:
    def test_from_questionnaire_roundtrip(self):
        class FakeAnalyst:
            def __init__(self, value):
                self.value = value

        config = {
            "ticker": "600519",
            "date": "2026-08-16",
            "output_language": "Chinese",
            "analysts": [FakeAnalyst("market"), FakeAnalyst("news")],
            "research_depth": 3,
            "llm_provider": "OpenAI",
            "backend_url": "https://api.example.com/v1",
            "shallow_thinking_model": "gpt-mini",
            "deep_thinking_model": "gpt-big",
            "thinking_level": None,
            "reasoning_effort": "high",
            "anthropic_effort": None,
        }
        request = AnalysisRequest.from_questionnaire(config)
        assert request.ticker == "600519"
        assert request.selected_analysts == ("market", "news")
        assert request.analyst_keys() == ["market", "news"]  # canonical order
        assert request.reasoning_effort == "high"

        graph_config = request.to_graph_config()
        assert graph_config["llm_provider"] == "openai"  # lowercased
        assert graph_config["max_debate_rounds"] == 3
        assert graph_config["deep_think_llm"] == "gpt-big"
        assert graph_config["output_language"] == "Chinese"

    def test_default_for_uses_config_defaults(self):
        request = AnalysisRequest.default_for("000001", "2026-08-16")
        assert request.selected_analysts == tuple(request.analyst_keys())
        assert request.llm_provider == DEFAULT_CONFIG["llm_provider"]
        assert request.research_depth == 1

    def test_result_dict_shape_matches_summary_consumer(self):
        result = AnalysisResult(
            ticker="600519", trade_date="2026-08-16", decision="BUY",
            report_path=Path("reports"), final_state={"x": 1},
        )
        payload = result.to_dict()
        # keys consumed by ui/summary.py — must not drift
        assert set(payload) == {
            "ticker", "decision", "confidence", "elapsed_time",
            "llm_calls", "tool_calls", "tokens_in", "tokens_out",
            "report_path", "final_state",
        }
        assert payload["confidence"] is None  # default stays None — never faked

    def test_result_confidence_pass_through_intact(self):
        result = AnalysisResult(
            ticker="600519", trade_date="2026-08-16", decision="BUY", confidence=72
        )
        assert result.to_dict()["confidence"] == 72


def _stub_graph(chunks):
    """Graph stub: stream_analysis returns a REAL _AnalysisStream over mocks.

    Reuses the pattern proven in test_graph_stream.py — the stream yields the
    given chunks and finalizes via the mocked graph methods.
    """
    from tradingagents.graph.trading_graph import _AnalysisStream

    graph = MagicMock()
    graph.debug = False
    graph._historical_context = None
    graph.graph_setup.selected_analysts = ["market"]
    graph.propagator.create_initial_state.return_value = {
        "messages": [], "company_of_interest": "600519",
    }
    graph.propagator.get_graph_args.return_value = {"stream_mode": "values", "config": {}}

    def _fake_stream(init_state, **kwargs):
        yield from chunks

    graph.graph.stream.side_effect = _fake_stream
    graph._create_fallback_state.side_effect = (
        lambda init, msg: {**init, "final_trade_decision": f"System error during analysis: {msg}"}
    )
    graph._ensure_structured_state.side_effect = lambda state: dict(state)
    graph.process_signal.return_value = "BUY"
    graph.stream_analysis = MagicMock(
        return_value=_AnalysisStream(graph, "600519", "2026-08-16")
    )
    return graph


class TestAnalysisServiceStream:
    def _make_service(self, graph):
        service = AnalysisService.__new__(AnalysisService)
        service._graph_factory = lambda: (lambda *a, **k: graph)
        service._debug = False
        return service

    def test_stream_events_yields_translated_events_then_completed(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        chunks = [
            {"messages": [], "analyst_reports": {"market": "R1"}},
        ]
        graph = _stub_graph(chunks)
        service = self._make_service(graph)

        request = AnalysisRequest.default_for("600519", "2026-08-16")
        stream = service.stream_events(request)
        assert stream.report_dir.exists()  # artifacts created eagerly

        events = list(stream)
        kinds = [type(e).__name__ for e in events]
        assert kinds[-1] == "AnalysisCompleted"
        assert any(isinstance(e, ReportSectionUpdated) and e.section_key == "market_report" for e in events)

        assert stream.result is not None
        assert stream.result.decision == "BUY"
        assert stream.result.ticker == "600519"
        assert stream.result.report_path == stream.report_dir

    def test_graph_construction_happens_eagerly(self, tmp_path, monkeypatch):
        """A broken configuration must fail in stream_events() — before the
        caller enters any Live context — not on first iteration."""
        monkeypatch.chdir(tmp_path)

        def exploding_factory():
            def ctor(*a, **k):
                raise RuntimeError("boom")

            return ctor

        service = AnalysisService.__new__(AnalysisService)
        service._graph_factory = exploding_factory
        service._debug = False
        with pytest.raises(RuntimeError):
            service.stream_events(AnalysisRequest.default_for("600519", "2026-08-16"))

    def test_run_headless_collects_events(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        chunks = [{"messages": [], "analyst_reports": {"news": "N1"}}]
        graph = _stub_graph(chunks)
        service = self._make_service(graph)

        seen = []
        result = service.run(
            AnalysisRequest.default_for("000001", "2026-08-16"),
            on_event=seen.append,
        )
        assert result.decision == "BUY"  # stub process_signal return
        assert any(isinstance(e, AnalysisCompleted) for e in seen)
