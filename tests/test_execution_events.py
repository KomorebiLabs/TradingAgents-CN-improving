"""Contract tests for the execution event protocol + ChunkEventTranslator.

These freeze the chunk->event semantics that the dashboard consumes. The
translator is the ONLY component allowed to understand chunk internals.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from tradingagents.application.events import (
    AgentStatusChanged,
    ChunkEventTranslator,
    MessageEmitted,
    MetricsUpdated,
    ReportSectionUpdated,
    StageMarked,
    TimelineNoted,
    ToolCallObserved,
    _classify_message,
)


def _events_of(translator, chunk, analysts=("market", "social", "news", "fundamentals")):
    return translator.translate(chunk, list(analysts))


class TestMessageClassification:
    def test_ai_message_truncated_to_100(self):
        mtype, content = _classify_message(AIMessage(content="x" * 300))
        assert mtype == "Agent"
        assert len(content) == 100

    def test_human_message_user(self):
        assert _classify_message(HumanMessage(content="hi"))[0] == "User"

    def test_tool_message_data_80(self):
        mtype, content = _classify_message(ToolMessage(content="y" * 200, tool_call_id="t1"))
        assert mtype == "Data" and len(content) == 80

    def test_list_content_blocks_extracted(self):
        msg = AIMessage(content=[{"text": "part1"}, "part2"])
        assert _classify_message(msg) == ("Agent", "part1 part2")


class TestMessageDedup:
    def test_same_message_id_emitted_once(self):
        translator = ChunkEventTranslator()
        msg = AIMessage(content="hello", id="msg-1")
        first = _events_of(translator, {"messages": [msg]})
        second = _events_of(translator, {"messages": [msg]})
        emitted = [e for e in first + second if isinstance(e, MessageEmitted)]
        assert len(emitted) == 1

    def test_tool_calls_observed(self):
        translator = ChunkEventTranslator()
        msg = AIMessage(content="", id="m1")
        msg.tool_calls = [{"name": "get_stock_data", "args": {"ticker": "600519"}}]
        events = _events_of(translator, {"messages": [msg]})
        tool_events = [e for e in events if isinstance(e, ToolCallObserved)]
        assert len(tool_events) == 1
        assert tool_events[0].name == "get_stock_data"
        assert "ticker=600519" in tool_events[0].args_repr


class TestAnalystReports:
    def test_structured_first_detection(self):
        translator = ChunkEventTranslator()
        chunk = {"analyst_reports": {"market": "FROM STRUCTURED"}}
        events = _events_of(translator, chunk)
        assert ReportSectionUpdated("market_report", "FROM STRUCTURED") in events
        assert AgentStatusChanged("Market Analyst", "completed") in events

    def test_flat_fallback_detection(self):
        translator = ChunkEventTranslator()
        events = _events_of(translator, {"market_report": "FROM FLAT"})
        assert ReportSectionUpdated("market_report", "FROM FLAT") in events

    def test_without_report_first_selected_is_in_progress(self):
        translator = ChunkEventTranslator()
        events = _events_of(translator, {}, analysts=("market", "news"))
        assert AgentStatusChanged("Market Analyst", "in_progress") in events
        assert AgentStatusChanged("News Analyst", "pending") in events

    def test_all_done_transitions_to_bull_researcher(self):
        translator = ChunkEventTranslator()
        chunk = {"analyst_reports": {k: "R" for k in ("market", "social", "news", "fundamentals")}}
        events = _events_of(translator, chunk)
        assert AgentStatusChanged("Bull Researcher", "in_progress") in events
        assert TimelineNoted("Stage 1 complete, Bull Researcher started") in events


class TestDebateCascade:
    def test_bull_history_creates_section_and_timeline(self):
        translator = ChunkEventTranslator()
        chunk = {"debate_blocks": {"investment": {"bull_history": "BULL", "bear_history": "", "judge_decision": ""}}}
        events = _events_of(translator, chunk)
        assert ReportSectionUpdated("investment_plan", "### Bull Researcher\nBULL") in events
        assert TimelineNoted("Research: debate in progress") in events

    def test_judge_decision_cascades_to_trader_with_stage(self):
        translator = ChunkEventTranslator()
        chunk = {"debate_blocks": {"investment": {"bull_history": "b", "bear_history": "", "judge_decision": "JUDGE"}}}
        events = _events_of(translator, chunk)
        assert AgentStatusChanged("Research Manager", "completed") in events
        assert AgentStatusChanged("Bull Researcher", "completed") in events
        assert AgentStatusChanged("Trader", "in_progress") in events
        assert StageMarked("Stage C") in events
        assert TimelineNoted("Research complete, Trader started") in events

    def test_trader_plan_starts_risk_team(self):
        translator = ChunkEventTranslator()
        events = _events_of(translator, {"decision_blocks": {"trader_plan": "PLAN"}})
        assert ReportSectionUpdated("trader_investment_plan", "PLAN") in events
        assert AgentStatusChanged("Trader", "completed") in events
        assert AgentStatusChanged("Aggressive Analyst", "in_progress") in events

    def test_risk_histories_and_judge_complete_everyone(self):
        translator = ChunkEventTranslator()
        risk = {
            "aggressive_history": "A",
            "conservative_history": "C",
            "neutral_history": "N",
            "judge_decision": "FINAL",
        }
        events = _events_of(translator, {"debate_blocks": {"risk": risk}})
        assert ReportSectionUpdated("final_trade_decision", "### Aggressive Analyst\nA") in events
        assert ReportSectionUpdated("final_trade_decision", "### Portfolio Manager\nFINAL") in events
        for agent in ("Aggressive Analyst", "Conservative Analyst", "Neutral Analyst", "Portfolio Manager"):
            assert AgentStatusChanged(agent, "completed") in events
        assert TimelineNoted("Portfolio: final decision complete") in events

    def test_flat_debate_fields_still_translated(self):
        translator = ChunkEventTranslator()
        events = _events_of(translator, {"risk_debate_state": {"aggressive_history": "A"}})
        assert ReportSectionUpdated("final_trade_decision", "### Aggressive Analyst\nA") in events


class TestMetrics:
    def test_metrics_polled_per_chunk(self):
        provider = MagicMock(
            return_value={"llm_calls": 3, "tool_calls": 5, "tokens_in": 100, "tokens_out": 200}
        )
        translator = ChunkEventTranslator(stats_provider=provider)
        events = _events_of(translator, {})
        metrics = [e for e in events if isinstance(e, MetricsUpdated)]
        assert len(metrics) == 1
        assert metrics[0].llm_calls == 3 and metrics[0].tokens_out == 200

    def test_no_provider_no_metrics(self):
        assert not [e for e in _events_of(ChunkEventTranslator(), {}) if isinstance(e, MetricsUpdated)]


class TestSpeakerPrefixStripped:
    """Real-run regression: risk debaters open with their own name
    ("Aggressive Analyst: ..."), which duplicated the "### {agent}" heading
    in final_trade_decision.md. The translator must strip the byline."""

    def test_risk_speaker_prefix_not_duplicated(self):
        translator = ChunkEventTranslator()
        chunk = {"risk_debate_state": {"aggressive_history": "Aggressive Analyst: BLAH"}}
        events = _events_of(translator, chunk)
        assert ReportSectionUpdated("final_trade_decision", "### Aggressive Analyst\nBLAH") in events

    def test_risk_content_without_prefix_unchanged(self):
        translator = ChunkEventTranslator()
        chunk = {"risk_debate_state": {"aggressive_history": "plain take"}}
        events = _events_of(translator, chunk)
        assert ReportSectionUpdated("final_trade_decision", "### Aggressive Analyst\nplain take") in events

    def test_judge_prefix_stripped(self):
        translator = ChunkEventTranslator()
        chunk = {"risk_debate_state": {"judge_decision": "Portfolio Manager: FINAL"}}
        events = _events_of(translator, chunk)
        assert ReportSectionUpdated("final_trade_decision", "### Portfolio Manager\nFINAL") in events
