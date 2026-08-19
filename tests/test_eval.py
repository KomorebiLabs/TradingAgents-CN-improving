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
    directional_stats,
    overall_accuracy,
)
from tradingagents.eval.report import build_report
from tradingagents.eval.runner import run_case_set


def test_label_from_return_thresholds():
    assert label_from_return(0.15) == "BUY"
    assert label_from_return(-0.12) == "SELL"
    assert label_from_return(0.0) == "NEUTRAL"
    assert label_from_return(None) == "NEUTRAL"


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
    class StubService:
        def run(self, request, on_event):
            return SimpleNamespace(decision="BUY", elapsed_time=1.0, confidence=70, final_state={})

    cases = [
        EvaluationCase(id="a", ticker="600519", eval_date="2025-06-02", label="BUY", horizon_return=0.21),
        EvaluationCase(id="b", ticker="000001", eval_date="2025-06-02", label="SELL", horizon_return=-0.15),
    ]
    results = run_case_set(StubService(), cases)
    assert len(results) == 2
    assert results[0]["decision"] == "BUY"
    assert results[0]["label"] == "BUY"
    assert results[1]["label"] == "SELL"


def test_report_renders_accuracy_and_matrix():
    labels = ["BUY", "SELL"]
    preds = ["BUY", "SELL"]
    md = build_report("unit", [{"label": l, "decision": p} for l, p in zip(labels, preds)], horizon_days=20)
    assert "Decision-Correctness Evaluation" in md
    assert "Overall accuracy" in md
    assert "Directional accuracy" in md
    assert "Confusion Matrix" in md
