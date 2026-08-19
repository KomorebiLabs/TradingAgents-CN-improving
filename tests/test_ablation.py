"""Ablation module tests (R4). Offline: stub AnalysisService, pure math."""

from __future__ import annotations

from types import SimpleNamespace

from tradingagents.ablation.configs import build_matrix
from tradingagents.ablation.report import build_report
from tradingagents.ablation.runner import run_configuration
from tradingagents.ablation.stability import aggregate_outcomes


class StubService:
    """Minimal AnalysisService stand-in: yields scripted decisions, records requests."""

    def __init__(self, decisions):
        self._decisions = iter(decisions)
        self.requests = []

    def run(self, request, on_event):
        self.requests.append(request)
        decision = next(self._decisions, "N/A")
        return SimpleNamespace(
            decision=decision,
            confidence=72.0,
            elapsed_time=3.2,
            final_state={
                "orchestration": {
                    "event_trail": [{"compression_triggered": True}, {}, {}]
                }
            },
        )


def test_repeat_fixed_decision_is_fully_consistent():
    service = StubService(["BUY", "BUY"])
    cfg = build_matrix()[2]  # multi_debate_1
    assert service.requests == []
    cell = run_configuration(service, "600519", "2026-08-16", cfg, n_repeat=2)
    assert len(service.requests) == 2
    assert cell["aggregate"]["decisions"] == {"BUY": 2}
    assert cell["aggregate"]["consistency"] == 1.0
    assert service.requests[0].research_depth == 1


def test_decision_split_consistency():
    service = StubService(["BUY", "HOLD", "SELL"])
    cell = run_configuration(service, "000001", "2026-08-16", build_matrix()[2], n_repeat=3)
    agg = cell["aggregate"]
    assert agg["decisions"] == {"BUY": 1, "HOLD": 1, "SELL": 1}
    assert agg["consistency"] == round(1 / 3, 3)
    assert agg["confidence_mean"] == 72.0
    assert agg["avg_route_events"] == 3
    assert agg["compression_rate"] == round(1 / 3, 3)


def test_aggregate_empty_outcomes():
    agg = aggregate_outcomes([])
    assert agg["consistency"] == 0.0
    assert agg["decisions"] == {}
    assert agg["confidence_mean"] is None


def test_build_matrix_has_expected_cells():
    matrix = build_matrix()
    names = [c.name for c in matrix]
    assert "single_market" in names
    assert "multi_debate_1" in names
    assert "multi_debate_3" in names
    single = next(c for c in matrix if c.name == "single_market")
    assert single.selected_analysts == ("market",)
    off = next(c for c in matrix if c.name == "multi_debate_off")
    assert off.research_depth == 0


def test_report_table_renders(self=None):
    service = StubService(["BUY", "BUY"])
    cells = [run_configuration(service, "600519", "2026-08-16", build_matrix()[2], n_repeat=2)]
    md = build_report("test", cells, n_repeat=2)
    assert "Ablation Report" in md
    assert "Consistency" in md
    assert "BUY:2" in md
    assert "How to read this" in md
