"""Canonical state contract tests (schema v2).

Freeze the reconciliation semantics of TradingAgentsGraph._ensure_structured_state:
structured blocks are canonical, flat fields are legacy mirrors filled both
ways only when missing. The old flat-wins direction (which wiped
structured-only writes) must never come back.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tradingagents.agents.utils.agent_states import STATE_SCHEMA_VERSION
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.propagation import Propagator
from tradingagents.graph.trading_graph import TradingAgentsGraph


def _bare_graph(tmp_path: Path) -> TradingAgentsGraph:
    """Build a TradingAgentsGraph without running its heavy __init__."""
    graph = object.__new__(TradingAgentsGraph)
    graph.config = dict(DEFAULT_CONFIG)
    graph.config["results_dir"] = str(tmp_path / "results")
    graph.ticker = "600519"
    graph.log_states_dict = {}
    graph.graph_setup = MagicMock()
    graph.graph_setup.selected_analysts = ["market", "news"]
    graph.reflector = MagicMock()
    graph.reflector.get_route_summary.return_value = {}
    return graph


class TestSchemaVersion:
    def test_constant_is_v2(self):
        assert STATE_SCHEMA_VERSION == 2

    def test_initial_state_carries_schema_version(self):
        state = Propagator(config={}).create_initial_state("600519", "2026-08-16")
        assert state["schema_version"] == STATE_SCHEMA_VERSION

    def test_ensure_backfills_schema_version_on_legacy_states(self):
        graph = _bare_graph(Path("."))
        state = {"company_of_interest": "600519", "trade_date": "2026-08-16"}
        result = graph._ensure_structured_state(state)
        assert result["schema_version"] == STATE_SCHEMA_VERSION


class TestCanonicalReconciliation:
    def test_structured_only_write_is_preserved_and_mirrored_to_flat(self):
        """The regression this whole phase exists for: the old flat-wins sync
        wiped structured-only writes; canonical policy must preserve them."""
        graph = _bare_graph(Path("."))
        state = {
            "company_of_interest": "600519",
            "trade_date": "2026-08-16",
            "analyst_reports": {"market": "STRUCTURED REPORT"},
            "market_report": "",  # legacy mirror empty
        }
        result = graph._ensure_structured_state(state)
        assert result["analyst_reports"]["market"] == "STRUCTURED REPORT"
        assert result["market_report"] == "STRUCTURED REPORT"  # backfilled for legacy readers

    def test_flat_only_write_fills_structured(self):
        """Legacy-only writers (e.g. _create_fallback_state) still work."""
        graph = _bare_graph(Path("."))
        state = {
            "company_of_interest": "600519",
            "trade_date": "2026-08-16",
            "final_trade_decision": "System error during analysis: boom",
        }
        result = graph._ensure_structured_state(state)
        assert result["decision_blocks"]["final_trade_decision"].startswith("System error")
        assert result["final_trade_decision"].startswith("System error")

    def test_dual_write_consistent_state_unchanged(self):
        graph = _bare_graph(Path("."))
        state = {
            "company_of_interest": "600519",
            "trade_date": "2026-08-16",
            "market_report": "R",
            "analyst_reports": {"market": "R"},
            "investment_plan": "P",
            "decision_blocks": {"investment_plan": "P", "trader_plan": "", "final_trade_decision": ""},
        }
        result = graph._ensure_structured_state(state)
        assert result["analyst_reports"]["market"] == "R"
        assert result["decision_blocks"]["investment_plan"] == "P"

    def test_structured_wins_on_conflict(self):
        graph = _bare_graph(Path("."))
        state = {
            "company_of_interest": "600519",
            "trade_date": "2026-08-16",
            "market_report": "STALE FLAT",
            "analyst_reports": {"market": "FRESH STRUCTURED"},
        }
        result = graph._ensure_structured_state(state)
        assert result["analyst_reports"]["market"] == "FRESH STRUCTURED"
        assert result["market_report"] == "FRESH STRUCTURED"

    def test_debate_flat_and_structured_share_one_object(self):
        """Debate states must be the same dict in both shapes so flat-reading
        routers (graph/setup.py) stay live-updated."""
        graph = _bare_graph(Path("."))
        debate = {"bull_history": "b", "count": 1}
        state = {
            "company_of_interest": "600519",
            "trade_date": "2026-08-16",
            "investment_debate_state": debate,
        }
        result = graph._ensure_structured_state(state)
        assert result["debate_blocks"]["investment"] is result["investment_debate_state"]

    def test_trader_plan_reconciles_both_directions(self):
        graph = _bare_graph(Path("."))
        # structured-only
        state = {
            "company_of_interest": "600519",
            "trade_date": "2026-08-16",
            "decision_blocks": {"trader_plan": "T1"},
        }
        assert graph._ensure_structured_state(state)["trader_investment_plan"] == "T1"
        # flat-only
        state2 = {
            "company_of_interest": "600519",
            "trade_date": "2026-08-16",
            "trader_investment_plan": "T2",
        }
        assert graph._ensure_structured_state(state2)["decision_blocks"]["trader_plan"] == "T2"


class TestLogStateSlimShape:
    def test_log_writes_structured_once_no_flat_duplicates(self, tmp_path):
        graph = _bare_graph(tmp_path)
        state = graph._ensure_structured_state(
            Propagator(config={}).create_initial_state("600519", "2026-08-16")
        )
        state["analyst_reports"]["market"] = "MARKET RPT"
        state["final_trade_decision"] = "BUY"
        state["decision_blocks"]["final_trade_decision"] = "BUY"

        graph._log_state("2026-08-16", state)

        log_path = (
            Path(graph.config["results_dir"]) / "600519" / "TradingAgentsStrategy_logs"
            / "full_states_log_2026-08-16.json"
        )
        assert log_path.exists()
        payload = json.loads(log_path.read_text(encoding="utf-8"))

        # canonical shape present
        assert payload["schema_version"] == STATE_SCHEMA_VERSION
        assert payload["analyst_reports"]["market"] == "MARKET RPT"
        assert payload["decision_blocks"]["final_trade_decision"] == "BUY"
        assert payload["debate_blocks"]["investment"]["bull_history"] == ""
        # legacy duplicated flat keys dropped (log slimming contract)
        assert "market_report" not in payload
        assert "investment_debate_state" not in payload
        assert "risk_debate_state" not in payload
        assert "trader_investment_decision" not in payload
        # quick-grep convenience key retained
        assert payload["final_trade_decision"] == "BUY"


class TestUiReaderMigration:
    def test_update_analyst_statuses_reads_structured_first(self):
        from cli.analyze import run_impl

        msg_buf = MagicMock()
        msg_buf.report_sections = {}
        dashboard = MagicMock()
        chunk = {
            "analyst_reports": {"market": "FROM STRUCTURED"},
            # flat deliberately absent — canonical read must still work
        }
        run_impl._update_analyst_statuses(
            msg_buf, dashboard, chunk,
            selected_keys=["market"], selected_set={"market"},
        )
        msg_buf.update_report_section.assert_any_call("market_report", "FROM STRUCTURED")

    def test_update_analyst_statuses_falls_back_to_flat(self):
        from cli.analyze import run_impl

        msg_buf = MagicMock()
        msg_buf.report_sections = {}
        dashboard = MagicMock()
        chunk = {"market_report": "FROM FLAT"}  # legacy shape only
        run_impl._update_analyst_statuses(
            msg_buf, dashboard, chunk,
            selected_keys=["market"], selected_set={"market"},
        )
        msg_buf.update_report_section.assert_any_call("market_report", "FROM FLAT")

    def test_handle_debate_states_reads_structured_blocks(self):
        from cli.analyze import run_impl

        msg_buf = MagicMock()
        msg_buf.agent_status = {}
        dashboard = MagicMock()
        chunk = {
            "debate_blocks": {"investment": {"bull_history": "BULL", "bear_history": "", "judge_decision": "J"}},
            "decision_blocks": {"trader_plan": "PLAN"},
        }
        run_impl._handle_debate_states(msg_buf, dashboard, chunk)
        msg_buf.update_report_section.assert_any_call("investment_plan", "### Bull Researcher\nBULL")
        msg_buf.update_report_section.assert_any_call("trader_investment_plan", "PLAN")
        dashboard.add_event.assert_any_call("Research complete, Trader started")
