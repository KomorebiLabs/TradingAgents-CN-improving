"""Offline tests for the unified graph streaming API (_AnalysisStream).

Uses a stub graph object — no LangGraph execution, no LLM, no network.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from tradingagents.graph.trading_graph import _AnalysisStream


def _make_stub_graph(chunks=None, error=None):
    """Build a graph-like stub with the surface _AnalysisStream touches."""
    graph = MagicMock()
    graph.debug = False
    graph._historical_context = None
    graph.graph_setup.selected_analysts = ["market", "news"]

    def _fake_stream(init_state, **kwargs):
        if error is not None:
            raise error
        yield from (chunks or [])

    graph.graph.stream.side_effect = _fake_stream
    graph.propagator.create_initial_state.return_value = {
        "messages": [],
        "company_of_interest": "600519",
    }
    graph.propagator.get_graph_args.return_value = {"stream_mode": "values", "config": {}}
    graph._create_fallback_state.side_effect = (
        lambda init, msg: {**init, "final_trade_decision": f"System error during analysis: {msg}"}
    )
    graph._synchronize_structured_state.side_effect = lambda state: dict(state)
    graph.process_signal.return_value = "BUY"
    return graph


def _consume(stream):
    return [chunk for chunk in stream]


class TestAnalysisStreamHappyPath:
    def test_yields_all_chunks_in_order(self):
        chunks = [{"step": 1, "messages": ["a"]}, {"step": 2, "messages": ["a", "b"]}]
        graph = _make_stub_graph(chunks=chunks)
        stream = _AnalysisStream(graph, "600519", "2026-08-16")
        assert _consume(stream) == chunks

    def test_finalize_sets_state_logs_and_result(self):
        chunks = [{"final_trade_decision": "old", "messages": []}]
        graph = _make_stub_graph(chunks=chunks)
        stream = _AnalysisStream(graph, "600519", "2026-08-16", callbacks=["cb"])
        _consume(stream)

        assert graph.curr_state == {"final_trade_decision": "old", "messages": []}
        assert graph._log_state.called
        assert stream.decision == "BUY"
        assert stream.result == ({"final_trade_decision": "old", "messages": []}, "BUY")

    def test_callbacks_forwarded_to_graph_args(self):
        graph = _make_stub_graph(chunks=[{"x": 1}])
        stream = _AnalysisStream(graph, "600519", "2026-08-16", callbacks=["cb"])
        _consume(stream)
        graph.propagator.get_graph_args.assert_called_once_with(callbacks=["cb"])

    def test_historical_context_injected_into_initial_state(self):
        graph = _make_stub_graph(chunks=[{"x": 1}])
        graph._historical_context = {"conclusion": "prior"}
        stream = _AnalysisStream(graph, "600519", "2026-08-16")
        _consume(stream)
        init_state = graph.propagator.create_initial_state.return_value
        assert init_state["historical_context"] == {"conclusion": "prior"}

    def test_result_before_consumption_raises(self):
        graph = _make_stub_graph(chunks=[{"x": 1}])
        stream = _AnalysisStream(graph, "600519", "2026-08-16")
        try:
            stream.result
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "not been consumed" in str(exc)

    def test_stream_is_single_consume(self):
        graph = _make_stub_graph(chunks=[{"x": 1}])
        stream = _AnalysisStream(graph, "600519", "2026-08-16")
        _consume(stream)
        try:
            _consume(stream)
            assert False, "expected RuntimeError on second iteration"
        except RuntimeError as exc:
            assert "only be consumed once" in str(exc)


class TestAnalysisStreamFailurePaths:
    def test_graph_exception_finalizes_into_fallback_state(self):
        graph = _make_stub_graph(error=RuntimeError("boom"))
        stream = _AnalysisStream(graph, "600519", "2026-08-16")
        consumed = _consume(stream)  # must not raise mid-iteration

        assert consumed == []
        assert stream.final_state is not None
        assert "Graph execution failed: boom" in stream.final_state["final_trade_decision"]
        assert graph._log_state.called

    def test_recursion_error_finalizes_into_fallback_state(self):
        graph = _make_stub_graph(error=RecursionError())
        stream = _AnalysisStream(graph, "600519", "2026-08-16")
        _consume(stream)
        assert "Max recursion limit reached" in stream.final_state["final_trade_decision"]

    def test_decision_extraction_failure_falls_back_to_na(self):
        graph = _make_stub_graph(chunks=[{"final_trade_decision": "x"}])
        graph.process_signal.side_effect = ValueError("bad signal")
        stream = _AnalysisStream(graph, "600519", "2026-08-16")
        _consume(stream)
        assert stream.decision == "N/A"
