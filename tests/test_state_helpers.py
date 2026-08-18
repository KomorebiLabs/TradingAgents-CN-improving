"""Characterization tests for state_helpers (freeze current routing behavior).

These freeze the dual-write update shapes and the compression-handoff
threshold routing so refactors cannot silently change execution paths.
"""

from __future__ import annotations

import pytest

from tradingagents.agents.utils import state_helpers as sh


class TestCompressionHandoffThresholds:
    def test_research_manager_short_history_goes_direct(self):
        assert sh.determine_research_manager_next_stage("short", "short", "") == "trader"

    def test_research_manager_long_history_triggers_handoff(self):
        assert sh.determine_research_manager_next_stage("x" * 4000, "short", "") == "trader_handoff"

    def test_research_manager_long_decision_triggers_handoff(self):
        assert sh.determine_research_manager_next_stage("short", "x" * 2500, "") == "trader_handoff"

    def test_research_manager_compression_notes_bypass_thresholds(self):
        assert sh.determine_research_manager_next_stage("x" * 9000, "x" * 9000, "notes") == "trader"

    def test_trader_short_outputs_go_direct(self):
        assert sh.determine_trader_next_stage("p", "o", "") == "risk"

    def test_trader_long_plan_triggers_handoff(self):
        assert sh.determine_trader_next_stage("x" * 3200, "o", "") == "risk_handoff"

    def test_trader_long_output_triggers_handoff(self):
        assert sh.determine_trader_next_stage("p", "x" * 2200, "") == "risk_handoff"

    def test_risk_short_history_goes_direct(self):
        assert sh.determine_risk_next_stage("h", "a", "") == "portfolio"

    def test_risk_long_history_triggers_handoff(self):
        assert sh.determine_risk_next_stage("x" * 3500, "a", "") == "portfolio_handoff"

    def test_risk_long_argument_triggers_handoff(self):
        assert sh.determine_risk_next_stage("h", "x" * 1600, "") == "portfolio_handoff"

    def test_threshold_constants_exposed(self):
        # Tuning entry point: constants must stay importable under these names.
        assert sh.RESEARCH_MANAGER_HISTORY_CHARS == 4000
        assert sh.RISK_ARGUMENT_CHARS == 1600


class TestDualWriteUpdates:
    def test_sync_report_updates_writes_both_shapes(self):
        update = sh.sync_report_updates("market", "REPORT", messages=["m"], sender="S")
        assert update["market_report"] == "REPORT"
        assert update["analyst_reports"] == {"market": "REPORT"}
        assert update["messages"] == ["m"]
        assert update["sender"] == "S"

    def test_sync_report_updates_rejects_unknown_key(self):
        with pytest.raises(ValueError):
            sh.sync_report_updates("unknown", "x")

    def test_sync_decision_updates_trader_plan_maps_to_legacy_key(self):
        update = sh.sync_decision_updates("trader_plan", "PLAN")
        assert update["trader_investment_plan"] == "PLAN"
        assert update["decision_blocks"] == {"trader_plan": "PLAN"}

    def test_sync_investment_debate_update(self):
        debate = {"bull_history": "b"}
        update = sh.sync_investment_debate_update(debate, sender="Bull")
        assert update["investment_debate_state"] is debate
        assert update["debate_blocks"] == {"investment": debate}

    def test_sync_risk_debate_update(self):
        debate = {"aggressive_history": "a"}
        update = sh.sync_risk_debate_update(debate)
        assert update["risk_debate_state"] is debate
        assert update["debate_blocks"] == {"risk": debate}


class TestStageNormalization:
    def test_handoff_suffix_collapsed(self):
        assert sh.normalize_next_stage("trader_handoff", "analyst") == "trader"

    def test_plain_stage_passthrough(self):
        assert sh.normalize_next_stage("trader", "analyst") == "trader"

    def test_empty_stage_falls_back_to_default(self):
        assert sh.normalize_next_stage("", "analyst") == "analyst"
        assert sh.normalize_next_stage(None, "risk") == "risk"

    def test_risk_follow_up_speaker_order(self):
        empty = {
            "current_aggressive_response": "",
            "current_conservative_response": "",
            "current_neutral_response": "",
            "latest_speaker": "",
        }
        assert sh.determine_risk_follow_up_speaker(empty) == "Aggressive Analyst"
        partial = dict(empty, current_aggressive_response="a")
        assert sh.determine_risk_follow_up_speaker(partial) == "Conservative Analyst"
        full = dict(empty, current_aggressive_response="a", current_conservative_response="c", latest_speaker="Aggressive")
        assert sh.determine_risk_follow_up_speaker(full) == "Neutral Analyst"


class TestDebateStateValidation:
    def test_valid_investment_state(self):
        state = {"bull_history": "", "bear_history": "", "history": "", "current_response": "", "count": 1}
        report = sh.validate_debate_state(state, "investment")
        assert report["is_valid"]

    def test_missing_fields_reported(self):
        report = sh.validate_debate_state({}, "investment")
        assert not report["is_valid"]
        assert any("bull_history" in issue for issue in report["issues"])

    def test_sanitize_debate_count_bounds(self):
        assert sh.sanitize_debate_count(-5) == 0
        assert sh.sanitize_debate_count("7") == 7
        assert sh.sanitize_debate_count(10**6) == 1000
