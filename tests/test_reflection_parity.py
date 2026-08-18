"""Legacy vs new reflection implementation parity tests.

Both `Reflector` implementations are fed identical (deep-copied) inputs and
stub LLM/memory objects; all observable outputs must match.  This is the
equivalence evidence for the reflection.py split (refactor/merger-pipeline).

Also compares module-level pure functions (extraction / route_analytics)
against the legacy class methods.

When reflection_legacy.py is eventually deleted, delete this file too.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import Any, Dict, List

from tradingagents.graph.reflection import Reflector as NewReflector
from tradingagents.graph.reflection import extraction, route_analytics
from tradingagents.graph.reflection_legacy import Reflector as LegacyReflector


# ---------------------------------------------------------------------------
# stubs
# ---------------------------------------------------------------------------


class FakeLLM:
    """Records invoke calls and returns a fixed content."""

    def __init__(self, content: str = "STUB-REFLECTION"):
        self.content = content
        self.calls: List[Any] = []

    def invoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.content)


class FakeMemory:
    """Records memory writes (add_situations / add_situation)."""

    def __init__(self):
        self.situation_pairs: List[tuple] = []
        self.route_situations: List[Dict[str, Any]] = []
        self._exported: List[Dict[str, Any]] = []

    def add_situations(self, pairs):
        self.situation_pairs.extend(pairs)

    def add_situation(self, situation, recommendation, metadata):
        self.route_situations.append(
            {"situation": situation, "recommendation": recommendation, "metadata": copy.deepcopy(metadata)}
        )

    def export_memories(self):
        return copy.deepcopy(self._exported)


# ---------------------------------------------------------------------------
# shared fixture state
# ---------------------------------------------------------------------------


def make_state() -> Dict[str, Any]:
    return {
        "company_of_interest": "600519",
        "trade_date": "2026-08-16",
        "market_report": "market: stable uptrend, MA20 above MA60",
        "sentiment_report": "sentiment: neutral-positive",
        "news_report": "news: no major catalysts",
        "fundamentals_report": "fundamentals: solid growth",
        "trader_investment_plan": "BUY 10% at 1450, stop 1400",
        "investment_debate_state": {
            "bull_history": "bull: strong growth momentum and sector tailwind",
            "bear_history": "bear: valuation stretched, margin pressure",
            "judge_decision": "investment_plan: BUY with medium conviction",
        },
        "risk_debate_state": {
            "judge_decision": "final: BUY 8% with stop-loss at 5% below entry",
        },
        "decision_blocks": {
            "investment_plan": "BUY with medium conviction",
            "trader_plan": "BUY 10% at 1450, stop 1400",
            "final_trade_decision": "BUY",
        },
        "ticker_info": {
            "ticker": "600519",
            "trade_date": "2026-08-16",
            "segment": "cn_main_board_equity",
            "style_bucket": "growth_style_candidate",
            "selected_analysts": ["market", "fundamentals"],
            "skills": ["technical", "valuation"],
        },
        "orchestration": {
            "stage": "risk_phase",
            "phase": "portfolio_handoff",
            "next_stage": "",
            "completed": True,
            "final_route": "handoff_compression",
            "final_reason": "long debate context",
            "compression_required": True,
            "compression_notes": "compressed 12k tokens to 2k",
            "route_family": "policy_core",
            "debate_rounds": 1,
            "event_trail": [
                {"node": "market_analyst", "phase": "analyst_phase", "stage": "analyst_phase", "context_estimate": 3000, "compression_triggered": False, "timestamp": "10:00:00"},
                {"node": "bull_researcher", "phase": "research_debate", "stage": "research_phase", "context_estimate": 9000, "compression_triggered": True, "timestamp": "10:05:00"},
                {"node": "bear_researcher", "phase": "research_debate", "stage": "research_phase", "context_estimate": 11000, "compression_triggered": True, "timestamp": "10:07:00"},
                {"node": "research_manager_handoff", "phase": "trader_handoff", "stage": "trader_phase", "context_estimate": 2000, "compression_triggered": False, "timestamp": "10:09:00"},
                {"node": "portfolio_manager", "phase": "risk_phase", "stage": "risk_phase", "context_estimate": 4000, "compression_triggered": False, "timestamp": "10:12:00"},
            ],
            "semantic_trigger_audit": {
                "semantic_trigger_reasons": ["long_debate"],
                "semantic_trigger_slots": {"debate_rounds": 1},
            },
        },
        "screener_context": {
            "route_decision": {
                "signal_card": {
                    "policy_signal_score": 0.8,
                    "technical_signal_score": 0.6,
                    "smart_money_signal_score": 0.7,
                }
            }
        },
    }


def norm_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Strip volatile timestamp fields for comparison."""
    out = copy.deepcopy(metadata)
    out.pop("created_at", None)
    return out


# ---------------------------------------------------------------------------
# parity tests
# ---------------------------------------------------------------------------


def test_parity_route_summary():
    legacy = LegacyReflector(FakeLLM())
    new = NewReflector(FakeLLM())
    assert legacy.get_route_summary(make_state()) == new.get_route_summary(make_state())


def test_parity_reflect_bull_and_bear():
    for method in ("reflect_bull_researcher", "reflect_bear_researcher"):
        llm_legacy, llm_new = FakeLLM(), FakeLLM()
        legacy = LegacyReflector(llm_legacy)
        new = NewReflector(llm_new)
        mem_legacy, mem_new = FakeMemory(), FakeMemory()
        getattr(legacy, method)(make_state(), "returns:+5%", mem_legacy)
        getattr(new, method)(make_state(), "returns:+5%", mem_new)
        assert mem_legacy.situation_pairs == mem_new.situation_pairs
        # both implementations must actually have called the LLM once
        assert len(llm_legacy.calls) == len(llm_new.calls) == 1


def test_parity_reflect_trader_and_judge():
    for method in ("reflect_trader", "reflect_invest_judge"):
        llm_legacy, llm_new = FakeLLM(), FakeLLM()
        legacy = LegacyReflector(llm_legacy)
        new = NewReflector(llm_new)
        mem_legacy, mem_new = FakeMemory(), FakeMemory()
        getattr(legacy, method)(make_state(), "returns:-2%", mem_legacy)
        getattr(new, method)(make_state(), "returns:-2%", mem_new)
        assert mem_legacy.situation_pairs == mem_new.situation_pairs


def test_parity_reflect_portfolio_manager_with_route_memory():
    llm_legacy, llm_new = FakeLLM(), FakeLLM()
    legacy = LegacyReflector(llm_legacy)
    new = NewReflector(llm_new)
    mem_legacy, mem_new = FakeMemory(), FakeMemory()
    route_legacy, route_new = FakeMemory(), FakeMemory()
    route_legacy._exported = [
        {"metadata": {"segment": "cn_main_board_equity", "style_bucket": "growth_style_candidate", "compression_rate": 0.4, "bottleneck_stages": ["research_phase"]}},
        {"metadata": {"segment": "cn_main_board_equity", "style_bucket": "growth_style_candidate", "compression_rate": 0.6, "bottleneck_stages": []}},
        {"metadata": {"segment": "cn_main_board_equity", "style_bucket": "value_style_candidate", "compression_rate": 0.2, "bottleneck_stages": []}},
        {"metadata": {"segment": "cn_main_board_equity", "style_bucket": "growth_style_candidate", "compression_rate": 0.3, "bottleneck_stages": []}},
        {"metadata": {"segment": "cn_main_board_equity", "style_bucket": "growth_style_candidate", "compression_rate": 0.5, "bottleneck_stages": []}},
    ]
    route_new._exported = copy.deepcopy(route_legacy._exported)

    legacy.reflect_portfolio_manager(
        make_state(), "returns:+3%", mem_legacy, route_memory=route_legacy
    )
    new.reflect_portfolio_manager(
        make_state(), "returns:+3%", mem_new, route_memory=route_new
    )

    assert mem_legacy.situation_pairs == mem_new.situation_pairs
    assert len(route_legacy.route_situations) == len(route_new.route_situations) == 1
    assert route_legacy.route_situations[0]["situation"] == route_new.route_situations[0]["situation"]
    assert route_legacy.route_situations[0]["recommendation"] == route_new.route_situations[0]["recommendation"]
    assert norm_metadata(route_legacy.route_situations[0]["metadata"]) == norm_metadata(
        route_new.route_situations[0]["metadata"]
    )


def test_parity_generate_conclusion_summary():
    llm_legacy, llm_new = FakeLLM("一句话总结：买入"), FakeLLM("一句话总结：买入")
    legacy = LegacyReflector(llm_legacy)
    new = NewReflector(llm_new)
    assert legacy.generate_conclusion_summary(make_state()) == new.generate_conclusion_summary(make_state())


def test_parity_generate_route_insight():
    llm_legacy, llm_new = FakeLLM("route insight stub"), FakeLLM("route insight stub")
    legacy = LegacyReflector(llm_legacy)
    new = NewReflector(llm_new)
    assert legacy.generate_route_insight(make_state()) == new.generate_route_insight(make_state())


def test_parity_conclusion_llm_failure_fallback():
    class BoomLLM:
        def invoke(self, messages):
            raise RuntimeError("llm down")

    legacy = LegacyReflector(BoomLLM())
    new = NewReflector(BoomLLM())
    assert legacy.generate_conclusion_summary(make_state()) == new.generate_conclusion_summary(make_state())


# ---------------------------------------------------------------------------
# module-level pure functions vs legacy methods
# ---------------------------------------------------------------------------


def test_parity_pure_functions_match_legacy_methods():
    legacy = LegacyReflector(FakeLLM())
    trail = make_state()["orchestration"]["event_trail"]

    assert route_analytics.analyze_route_efficiency(trail) == legacy.analyze_route_efficiency(trail)
    assert route_analytics.identify_route_patterns(trail) == legacy.identify_route_patterns(trail)
    assert route_analytics._analyze_route_patterns(trail) == legacy._analyze_route_patterns(trail)
    assert extraction._extract_event_trail(make_state()) == legacy._extract_event_trail(make_state())
    assert extraction._extract_route_decision(make_state()) == legacy._extract_route_decision(make_state())
    assert extraction._extract_semantic_trigger_audit(make_state()) == legacy._extract_semantic_trigger_audit(make_state())
    assert extraction._format_event_trail(trail) == legacy._format_event_trail(trail)
    assert extraction._extract_orchestration_context(make_state()) == legacy._extract_orchestration_context(make_state())
    assert extraction._extract_current_situation(make_state()) == legacy._extract_current_situation(make_state())


def test_parity_empty_event_trail():
    legacy = LegacyReflector(FakeLLM())
    empty_state = make_state()
    empty_state["orchestration"] = {"event_trail": []}
    assert legacy.get_route_summary(empty_state) == NewReflector(FakeLLM()).get_route_summary(empty_state)
    assert route_analytics.analyze_route_efficiency([]) == legacy.analyze_route_efficiency([])
    assert route_analytics.identify_route_patterns([]) == legacy.identify_route_patterns([])
