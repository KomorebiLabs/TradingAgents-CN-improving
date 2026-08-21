"""R10 evaluation-set tests. Offline: mocked history + stub service + pure matrix math."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from tradingagents.eval.cases import (
    EvaluationCase,
    build_case_set,
    label_from_return,
)
from tradingagents.eval.matrix import (
    confusion_matrix,
    decision_warning,
    directional_stats,
    normalize_decision,
    overall_accuracy,
)
from tradingagents.eval.report import build_report
from tradingagents.eval.runner import run_case_set


def test_label_from_return_thresholds():
    assert label_from_return(0.15) == "BUY"
    assert label_from_return(-0.12) == "SELL"
    assert label_from_return(0.0) == "NEUTRAL"
    assert label_from_return(None) == "NEUTRAL"


def test_decision_normalization_is_total_and_case_insensitive():
    assert normalize_decision("buy") == "BUY"
    assert normalize_decision(" HOLD ") == "HOLD"
    assert normalize_decision("neutral") == "HOLD"
    assert normalize_decision("") == "HOLD"
    assert normalize_decision(None) == "HOLD"
    assert decision_warning("BUY") is None
    assert "Unknown decision" in decision_warning("MAYBE")


def _fake_hist(symbol_list):
    """Factory returning a fetch_hist mock with a +21% forward move."""

    def fetch_hist(ticker, start, end, adjust="qfq"):
        return pd.DataFrame(
            {"date": ["2025-06-02", "2025-06-30", "2025-06-30"], "close": [100.0, 121.0, 121.0]}
        )

    return fetch_hist


def test_build_case_set_labelled_from_history(monkeypatch):
    class FakeDA:
        pass

    monkeypatch.setattr(
        "tradingagents.eval.cases._forward_return",
        lambda da, ticker, date, horizon: 0.21,
    )
    cases = build_case_set(FakeDA(), ["600519", "000001"], "2025-06-02", horizon_days=20, n=2)
    assert len(cases) == 2
    assert all(c.label == "BUY" for c in cases)
    assert all(c.horizon_return == 0.21 for c in cases)


def test_confusion_matrix_counts():
    labels = ["BUY", "SELL", "BUY", "NEUTRAL"]
    preds = ["BUY", "SELL", "HOLD", "HOLD"]
    m = confusion_matrix(labels, preds)
    assert m["BUY"]["BUY"] == 1
    assert m["BUY"]["HOLD"] == 1
    assert m["SELL"]["SELL"] == 1
    assert m["NEUTRAL"]["HOLD"] == 1


def test_directional_and_overall_accuracy():
    m = confusion_matrix(
        ["BUY", "BUY", "SELL", "SELL"],
        ["BUY", "HOLD", "SELL", "BUY"],
    )
    d = directional_stats(m)
    assert d["directional_correct"] == 2  # BUY->BUY, SELL->SELL
    assert d["directional_total"] == 4
    assert d["directional_accuracy"] == 0.5
    o = overall_accuracy(m)
    assert o["accuracy"] == 0.5


def test_run_case_set_uses_service_and_labels():
    seen_requests = []

    class StubService:
        def run(self, request, on_event):
            seen_requests.append(request)
            return SimpleNamespace(
                decision="BUY",
                elapsed_time=1.0,
                confidence=70,
                llm_calls=2,
                tool_calls=3,
                tokens_in=100,
                tokens_out=40,
                warnings=["stub warning"],
                final_state={},
            )

    cases = [
        EvaluationCase(id="a", ticker="600519", eval_date="2025-06-02", label="BUY", horizon_return=0.21),
        EvaluationCase(id="b", ticker="000001", eval_date="2025-06-02", label="SELL", horizon_return=-0.15),
    ]
    results = run_case_set(StubService(), cases)
    assert len(results) == 2
    assert [request.trade_date for request in seen_requests] == ["2025-06-02", "2025-06-02"]
    assert [request.ticker for request in seen_requests] == ["600519", "000001"]
    assert results[0]["decision"] == "BUY"
    assert results[0]["normalized_decision"] == "BUY"
    assert results[0]["normalization_warning"] is None
    assert results[0]["label"] == "BUY"
    assert results[1]["label"] == "SELL"
    assert results[0]["confidence"] == 70
    assert results[0]["elapsed_time"] == 1.0
    assert results[0]["llm_calls"] == 2
    assert results[0]["tool_calls"] == 3
    assert results[0]["tokens_in"] == 100
    assert results[0]["tokens_out"] == 40
    assert results[0]["warnings"] == ["stub warning"]
    assert results[0]["provider"] == "deepseek"
    assert results[0]["research_depth"] == 1


def test_run_case_set_records_unknown_decision_warning():
    class StubService:
        def run(self, request, on_event):
            return SimpleNamespace(decision="MAYBE", warnings=[])

    records = run_case_set(
        StubService(),
        [EvaluationCase(id="unknown", ticker="600519", eval_date="2025-06-02")],
    )

    assert records[0]["decision"] == "MAYBE"
    assert records[0]["normalized_decision"] == "HOLD"
    assert records[0]["normalization_warning"] == "Unknown decision normalized to HOLD: 'MAYBE'"
    assert records[0]["warnings"] == [records[0]["normalization_warning"]]


def test_report_renders_accuracy_and_matrix():
    labels = ["BUY", "SELL"]
    preds = ["BUY", "SELL"]
    md = build_report("unit", [{"label": l, "decision": p} for l, p in zip(labels, preds)], horizon_days=20)
    assert "Decision-Correctness Evaluation" in md
    assert "Overall accuracy" in md
    assert "Directional accuracy" in md
    assert "Confusion Matrix" in md


def test_report_renders_framework_and_real_model_flags():
    md = build_report(
        "offline",
        [{"label": "BUY", "decision": "BUY"}],
        framework_ready=True,
        real_model_run=False,
    )
    assert "Framework ready: True" in md
    assert "Real model run: False" in md
    assert "not an LLM benchmark result" in md


def test_case_set_is_deterministic_with_seed(monkeypatch):
    class FakeDA:
        pass

    monkeypatch.setattr(
        "tradingagents.eval.cases._forward_return",
        lambda da, ticker, date, horizon: 0.10,
    )
    first = build_case_set(FakeDA(), ["600519", "000001", "300750"], "2025-06-02", n=3, seed=42)
    second = build_case_set(FakeDA(), ["600519", "000001", "300750"], "2025-06-02", n=3, seed=42)
    assert [c.ticker for c in first] == [c.ticker for c in second]
    assert len(first) == 3


def test_case_set_caps_n_and_dedups_tickers(monkeypatch):
    class FakeDA:
        pass

    monkeypatch.setattr(
        "tradingagents.eval.cases._forward_return",
        lambda da, ticker, date, horizon: 0.10,
    )
    # duplicates collapse; n above ticker count is capped
    cases = build_case_set(
        FakeDA(),
        ["600519", "600519", "000001"],
        "2025-06-02",
        n=10,
        seed=7,
    )
    tickers = [c.ticker for c in cases]
    assert len(tickers) == len(set(tickers)) == 2


def test_case_set_empty_when_no_tickers(monkeypatch):
    class FakeDA:
        pass

    monkeypatch.setattr(
        "tradingagents.eval.cases._forward_return",
        lambda da, ticker, date, horizon: 0.10,
    )
    assert build_case_set(FakeDA(), [], "2025-06-02", n=5) == []


def test_eval_request_uses_eval_date_not_future_horizon():
    """The Agent request must be anchored to eval_date; forward-return data
    is only used to build the label, never handed to the service."""
    seen = []

    class StubService:
        def run(self, request, on_event):
            seen.append((request.ticker, request.trade_date))
            return SimpleNamespace(decision="HOLD")

    cases = [
        EvaluationCase(id="c", ticker="600519", eval_date="2025-06-02", label="BUY", horizon_return=0.21)
    ]
    run_case_set(StubService(), cases)
    assert seen == [("600519", "2025-06-02")]