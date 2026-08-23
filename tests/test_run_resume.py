"""Phase-1 engineering tests: run-id traceability (E7), checkpoint resume (E1),
and classified LLM retry (E2).

E7: every run gets a unique run_id threaded through the event stream, the
    artifact directory (reports/<ticker>/<date>/<run_id>/), request.json and
    the result payload.
E1: with a checkpointer attached, a crashed run resumes from its last
    completed super-step — finished nodes are not re-executed.
E2: retry happens at the openai SDK transport layer with the explicit
    max_retries=3 — 429/5xx/connection errors back off and recover, auth
    errors fail fast (never retried), and no second retry layer is stacked.
"""

from __future__ import annotations

import json as jsonlib

import pytest

import tradingagents.application.service as service_module
from tradingagents.application import (
    AnalysisRequest,
    AnalysisService,
    AnalysisStarted,
)
from tradingagents.application.events import AnalysisCompleted


def _request(ticker="600519", date="2026-08-20"):
    return AnalysisRequest(ticker=ticker, trade_date=date)


def _make_service(monkeypatch, tmp_path, chunks):
    """Service over a stub graph (pattern proven in test_analysis_service)."""
    from unittest.mock import MagicMock

    from tradingagents.graph.trading_graph import _AnalysisStream

    monkeypatch.setattr(service_module, "_PROJECT_ROOT", tmp_path)

    graph = MagicMock()
    graph.debug = False
    graph._historical_context = None
    graph.run_id = None
    graph.graph_setup.selected_analysts = ["market"]
    graph.propagator.create_initial_state.return_value = {
        "messages": [], "company_of_interest": "600519",
    }
    graph.propagator.get_graph_args.return_value = {"stream_mode": "values", "config": {}}

    def _fake_stream(init_state, **kwargs):
        yield from chunks

    graph.graph.stream.side_effect = _fake_stream
    graph._create_fallback_state.side_effect = (
        lambda init, msg: {**init, "final_trade_decision": f"error: {msg}"}
    )
    graph._ensure_structured_state.side_effect = lambda state: dict(state)
    graph.process_signal.return_value = "BUY"
    graph.stream_analysis = MagicMock(
        side_effect=lambda *a, **k: _AnalysisStream(graph, "600519", "2026-08-20")
    )

    service = AnalysisService.__new__(AnalysisService)
    service._graph_factory = lambda: (lambda *a, **k: graph)
    service._debug = False
    return service


# ── E7: run_id traceability ──────────────────────────────────────────────


class TestRunId:
    def test_unique_run_ids_and_artifact_layout(self, monkeypatch, tmp_path):
        service = _make_service(monkeypatch, tmp_path, chunks=[{"messages": []}])
        s1 = service.stream_events(_request())
        list(s1)
        s2 = service.stream_events(_request())
        list(s2)

        assert s1.run_id != s2.run_id
        assert len(s1.run_id) == 12
        # reports/<ticker>/<date>/<run_id>/ with persisted request
        run_dir = tmp_path / "reports" / "600519" / "2026-08-20" / s1.run_id
        assert run_dir.is_dir()
        assert (run_dir / "request.json").is_file()
        assert (run_dir / "reports").is_dir()
        saved = jsonlib.loads((run_dir / "request.json").read_text(encoding="utf-8"))
        assert saved["ticker"] == "600519"

    def test_analysis_started_carries_run_id_first(self, monkeypatch, tmp_path):
        service = _make_service(monkeypatch, tmp_path, chunks=[{"messages": []}])
        stream = service.stream_events(_request())
        events = list(stream)
        assert isinstance(events[0], AnalysisStarted)
        assert events[0].run_id == stream.run_id
        assert isinstance(events[-1], AnalysisCompleted)

    def test_result_carries_run_id(self, monkeypatch, tmp_path):
        service = _make_service(monkeypatch, tmp_path, chunks=[{"messages": []}])
        stream = service.stream_events(_request())
        list(stream)
        assert stream.result.run_id == stream.run_id
        assert stream.result.to_dict()["run_id"] == stream.run_id

    def test_find_run_and_resume_rebuilds_request(self, monkeypatch, tmp_path):
        service = _make_service(monkeypatch, tmp_path, chunks=[{"messages": []}])
        stream = service.stream_events(_request())
        list(stream)

        assert AnalysisService.find_run(stream.run_id) == stream.results_dir

        resumed = AnalysisService.resume_run(
            stream.run_id, graph_factory=service._graph_factory, debug=False
        )
        assert resumed.run_id == stream.run_id
        assert resumed.resume is True
        assert resumed.request.ticker == "600519"
        # resume requires the stub graph to be called with the same run_id
        # so the checkpoint thread continues instead of starting anew.
        events = list(resumed)
        assert events[-1].__class__ is AnalysisCompleted

    def test_resume_without_run_id_rejected(self, monkeypatch, tmp_path):
        service = _make_service(monkeypatch, tmp_path, chunks=[])
        with pytest.raises(ValueError):
            service.stream_events(_request(), resume=True)

    def test_resume_unknown_run_id(self, monkeypatch, tmp_path):
        _make_service(monkeypatch, tmp_path, chunks=[])
        with pytest.raises(FileNotFoundError):
            AnalysisService.resume_run("deadbeefdead")


# ── E1: checkpoint resume semantics ──────────────────────────────────────


class TestCheckpointResume:
    def _build_app(self, saver, calls, fail_first_n):
        from langgraph.graph import END, START, StateGraph
        from typing_extensions import TypedDict

        class S(TypedDict, total=False):
            count: int
            done: str

        def node1(state):
            calls["node1"] += 1
            return {"count": state.get("count", 0) + 1}

        def node2(state):
            calls["node2"] += 1
            if calls["node2"] <= fail_first_n:
                raise RuntimeError("simulated crash mid-run")
            return {"done": "yes"}

        g = StateGraph(S)
        g.add_node("n1", node1)
        g.add_node("n2", node2)
        g.add_edge(START, "n1")
        g.add_edge("n1", "n2")
        g.add_edge("n2", END)
        return g.compile(checkpointer=saver)

    def test_resume_does_not_rerun_completed_nodes(self, tmp_path):
        import sqlite3

        from langgraph.checkpoint.sqlite import SqliteSaver

        conn = sqlite3.connect(tmp_path / "ckpt.db", check_same_thread=False)
        saver = SqliteSaver(conn)
        thread = {"configurable": {"thread_id": "run-abc"}}
        calls = {"node1": 0, "node2": 0}

        app = self._build_app(saver, calls, fail_first_n=1)
        with pytest.raises(RuntimeError):
            list(app.stream({"count": 0}, thread, stream_mode="values"))
        assert calls == {"node1": 1, "node2": 1}  # crash happened in node2

        # "process restarted": same saver + thread, input=None resumes
        app2 = self._build_app(saver, calls, fail_first_n=1)
        chunks = list(app2.stream(None, thread, stream_mode="values"))
        final = chunks[-1]
        assert final["done"] == "yes"
        # THE assertion: node1 ran exactly once across both processes —
        # its LLM result came from the checkpoint, no re-billing.
        assert calls == {"node1": 1, "node2": 2}

    def test_build_checkpointer_creates_db(self, tmp_path, monkeypatch):
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        monkeypatch.setattr(
            "pathlib.Path.home", classmethod(lambda cls: tmp_path)
        )
        saver = TradingAgentsGraph._build_checkpointer("runxyz")
        assert saver is not None
        db = tmp_path / ".tradingagents" / "checkpoints" / "runxyz" / "checkpoint.db"
        assert db.is_file()


# ── E2: classified retry at the transport layer ──────────────────────────


def _chat_ok_body():
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "test",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "ok"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


class TestLLMRetry:
    def _client(self, handler):
        import httpx

        from tradingagents.llm_clients.openai_client import OpenAIClient

        # deepseek = chat-completions protocol (the "openai" provider uses the
        # Responses API); the retry-under-test lives in the shared openai SDK
        # transport layer, identical for every OpenAI-compatible provider.
        return OpenAIClient(
            "deepseek-chat",
            provider="deepseek",
            api_key="test-key",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

    def test_max_retries_explicit(self):
        import httpx

        from tradingagents.llm_clients.openai_client import OpenAIClient

        client = OpenAIClient(
            "deepseek-chat",
            provider="deepseek",
            api_key="k",
            http_client=httpx.Client(transport=httpx.MockTransport(
                lambda req: httpx.Response(200, json=_chat_ok_body(), request=req)
            )),
        )
        assert client.get_llm().max_retries == 3

    def test_429_backs_off_and_recovers(self):
        import httpx

        attempts = {"n": 0}

        def handler(request):
            attempts["n"] += 1
            if attempts["n"] < 3:
                return httpx.Response(
                    429, request=request, headers={"retry-after": "0"}
                )
            return httpx.Response(200, json=_chat_ok_body(), request=request)

        llm = self._client(handler).get_llm()
        out = llm.invoke("hi")
        assert "ok" in str(out.content)
        assert attempts["n"] == 3  # two 429s retried, third succeeded

    def test_auth_error_fails_fast(self):
        import httpx
        import openai

        attempts = {"n": 0}

        def handler(request):
            attempts["n"] += 1
            return httpx.Response(401, json={"error": {"message": "bad key"}}, request=request)

        llm = self._client(handler).get_llm()
        with pytest.raises(openai.AuthenticationError):
            llm.invoke("hi")
        assert attempts["n"] == 1  # never retried: retrying config errors burns money
