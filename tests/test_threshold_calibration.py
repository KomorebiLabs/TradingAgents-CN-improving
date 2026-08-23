"""A3: compression-threshold unit fix + calibration instrumentation.

- The field named *_tokens actually measured characters (unit lie): now
  renamed *_chars everywhere and driven by DEFAULT_CONFIG.
- Every run dumps per-phase context sizes to context_stats.json so the
  threshold can be recalibrated from a real distribution (P75 rule).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import tradingagents.application.service as service_module
from tradingagents.application import AnalysisRequest, AnalysisService


def _grep_count(pattern: str) -> int:
    root = Path(__file__).resolve().parents[1] / "tradingagents"
    count = 0
    for f in root.rglob("*.py"):
        if "__pycache__" in str(f):
            continue
        count += f.read_text(encoding="utf-8").count(pattern)
    return count


class TestThresholdRename:
    def test_old_unit_lie_name_gone(self):
        # renamed 2026-08: the field said tokens but the router counts chars
        assert _grep_count("compression_threshold_tokens") == 0

    def test_config_default_wins_over_literals(self):
        from tradingagents.default_config import DEFAULT_CONFIG

        v = DEFAULT_CONFIG["orchestration_compression_threshold_chars"]
        assert isinstance(v, int) and 30000 <= v <= 50000  # provisional anchor

    def test_router_reads_configured_threshold(self, monkeypatch):
        from tradingagents.dataflows.config import set_config
        from tradingagents.graph.setup import create_orchestration_router

        router = create_orchestration_router("analyst", "research")
        state = {"analyst_reports": {"market": "x" * 10}, "orchestration": {}}

        set_config({"orchestration_compression_threshold_chars": 50000})
        out = router(dict(state))
        assert out["orchestration"]["compression_required"] is False  # 10 < 50000

        set_config({"orchestration_compression_threshold_chars": 5})
        out = router(dict(state))
        assert out["orchestration"]["compression_required"] is True   # 10 >= 5


class TestContextStatsInstrumentation:
    def test_stats_dumped_after_run(self, monkeypatch, tmp_path):
        from unittest.mock import MagicMock

        from tradingagents.graph.trading_graph import _AnalysisStream

        monkeypatch.setattr(service_module, "_PROJECT_ROOT", tmp_path)
        graph = MagicMock()
        graph.debug = False
        graph._historical_context = None
        graph.run_id = None
        graph.graph_setup.selected_analysts = ["market"]
        graph.propagator.create_initial_state.return_value = {"messages": []}
        graph.propagator.get_graph_args.return_value = {"stream_mode": "values", "config": {}}

        def _fake_stream(init_state, **kwargs):
            yield {
                "messages": [],
                "orchestration": {
                    "event_trail": [
                        {"stage": "route_research", "context_estimate": 26400},
                        {"stage": "route_trader", "context_estimate": 31000},
                    ]
                },
            }

        graph.graph.stream.side_effect = _fake_stream
        graph._ensure_structured_state.side_effect = lambda state: dict(state)
        graph.stream_analysis = MagicMock(
            side_effect=lambda *a, **k: _AnalysisStream(graph, "600519", "2026-08-20")
        )

        service = AnalysisService.__new__(AnalysisService)
        service._graph_factory = lambda: (lambda *a, **k: graph)
        service._debug = False
        stream = service.stream_events(AnalysisRequest(ticker="600519", trade_date="2026-08-20"))
        list(stream)

        stats_file = stream.results_dir / "context_stats.json"
        assert stats_file.is_file()
        data = json.loads(stats_file.read_text(encoding="utf-8"))
        assert data["run_id"] == stream.run_id
        phases = data["phases"]
        assert phases == [
            {"stage": "route_research", "context_estimate": 26400},
            {"stage": "route_trader", "context_estimate": 31000},
        ]
