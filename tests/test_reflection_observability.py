import tempfile
import unittest
from pathlib import Path

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.reflection import Reflector
from tradingagents.graph.trading_graph import TradingAgentsGraph


class ReflectionObservabilityTests(unittest.TestCase):
    class _StubResponse:
        def __init__(self, content):
            self.content = content

    class _StubLLM:
        def __init__(self, content="reflection output"):
            self.content = content
            self.last_messages = None

        def invoke(self, messages):
            self.last_messages = messages
            return ReflectionObservabilityTests._StubResponse(self.content)

    def test_reflector_includes_orchestration_context_in_situation(self):
        llm = self._StubLLM()
        reflector = Reflector(llm)
        state = {
            "market_report": "market",
            "sentiment_report": "sentiment",
            "news_report": "news",
            "fundamentals_report": "fundamentals",
            "ticker_info": {
                "segment": "cn_star_equity",
                "style_bucket": "growth_style_candidate",
                "skills": ["cn_market_data", "cn_policy_news"],
                "selected_analysts": ["market", "news"],
            },
            "orchestration": {
                "stage": "completed",
                "phase": "completed",
                "next_stage": "completed",
                "completed": True,
                "final_route": "portfolio_handoff",
                "final_reason": "risk_debate_exceeded_safe_context",
                "compression_required": False,
                "compression_notes": "compressed handoff memo",
                "selected_analysts": ["market", "news"],
            },
        }

        situation = reflector._extract_current_situation(state)

        self.assertIn("Execution Orchestration Context:", situation)
        self.assertIn("final_route: portfolio_handoff", situation)
        self.assertIn("final_reason: risk_debate_exceeded_safe_context", situation)
        self.assertIn("compression_notes_excerpt: compressed handoff memo", situation)
        self.assertIn("segment: cn_star_equity", situation)

    def test_reflector_passes_component_context_to_llm(self):
        llm = self._StubLLM()
        reflector = Reflector(llm)

        reflector._reflect_on_component(
            "PORTFOLIO MANAGER",
            "final decision",
            "market context",
            0.12,
        )

        self.assertIsNotNone(llm.last_messages)
        human_message = llm.last_messages[1][1]
        self.assertIn("Component: PORTFOLIO MANAGER", human_message)
        self.assertIn("risk finalization route", human_message)

    def test_log_state_writes_orchestration_summary(self):
        config = DEFAULT_CONFIG.copy()
        with tempfile.TemporaryDirectory() as tmpdir:
            config["results_dir"] = tmpdir
            graph = TradingAgentsGraph(
                selected_analysts=["market"],
                config=config,
                debug=False,
            )
            graph.ticker = "600519.SH"
            final_state = {
                "company_of_interest": "600519.SH",
                "trade_date": "2026-05-05",
                "ticker_info": {
                    "segment": "cn_main_board_equity",
                    "style_bucket": "dividend_style_candidate",
                    "skills": ["cn_market_data"],
                },
                "analyst_reports": {},
                "decision_blocks": {},
                "orchestration": {
                    "completed": True,
                    "stage": "completed",
                    "phase": "completed",
                    "next_stage": "completed",
                    "final_route": "portfolio",
                    "final_reason": "existing_risk_handoff_available",
                    "compression_required": False,
                    "compression_notes": "memo text",
                    "selected_analysts": ["market"],
                },
                "market_report": "market",
                "sentiment_report": "sentiment",
                "news_report": "news",
                "fundamentals_report": "fundamentals",
                "investment_debate_state": {
                    "bull_history": "",
                    "bear_history": "",
                    "history": "",
                    "current_response": "",
                    "judge_decision": "",
                },
                "risk_debate_state": {
                    "aggressive_history": "",
                    "conservative_history": "",
                    "neutral_history": "",
                    "history": "",
                    "judge_decision": "",
                },
                "investment_plan": "plan",
                "trader_investment_plan": "trader",
                "final_trade_decision": "final decision",
            }

            graph._log_state("2026-05-05", final_state)
            logged = graph.log_states_dict["2026-05-05"]

            self.assertIn("orchestration_summary", logged)
            self.assertEqual(logged["orchestration_summary"]["final_route"], "portfolio")
            self.assertEqual(
                logged["orchestration_summary"]["final_reason"],
                "existing_risk_handoff_available",
            )
            self.assertEqual(
                logged["orchestration_summary"]["compression_notes_preview"],
                "memo text",
            )

            log_path = Path(tmpdir) / "600519.SH" / "TradingAgentsStrategy_logs" / "full_states_log_2026-05-05.json"
            self.assertTrue(log_path.exists())

    def test_extract_orchestration_context_structured(self):
        """Test the structured context extraction method."""
        llm = self._StubLLM()
        reflector = Reflector(llm)

        state = {
            "ticker_info": {
                "segment": "cn_star_equity",
                "style_bucket": "growth_style_candidate",
                "skills": ["cn_macro_news"],
                "selected_analysts": ["market", "news"],
                "ticker": "688981",
                "company_name": "Test Tech Co",
                "trade_date": "2025-05-01",
            },
            "orchestration": {
                "stage": "completed",
                "phase": "completed",
                "final_route": "direct",
                "final_reason": "simple_query",
                "event_trail": [
                    {"stage": "analyst", "phase": "analyst_market", "compression_triggered": False},
                    {"stage": "research", "phase": "research_bull", "compression_triggered": False},
                    {"stage": "research", "phase": "research_bear", "compression_triggered": False},
                    {"stage": "trader", "phase": "trader_phase", "compression_triggered": False},
                    {"stage": "risk", "phase": "risk_debate", "compression_triggered": False},
                ],
            },
        }

        structured = reflector._extract_orchestration_context_structured(state)

        # Check basic fields
        self.assertEqual(structured["segment"], "cn_star_equity")
        self.assertEqual(structured["style_bucket"], "growth_style_candidate")
        self.assertEqual(structured["final_route"], "direct")
        self.assertEqual(structured["route_category"], "normal")  # No compression

        # Check sequences
        self.assertEqual(structured["stage_sequence"], ["analyst", "research", "research", "trader", "risk"])
        self.assertEqual(structured["phase_sequence"], ["analyst_market", "research_bull", "research_bear", "trader_phase", "risk_debate"])

        # Check compression info
        self.assertEqual(structured["compression_rate"], 0.0)
        self.assertFalse(structured["compression_triggered"])
        self.assertEqual(structured["compression_phases"], [])

        # Check event stats
        self.assertEqual(structured["total_events"], 5)
        self.assertEqual(structured["unique_stages"], ["analyst", "research", "trader", "risk"])

        # Check ticker info
        self.assertEqual(structured["ticker"], "688981")
        self.assertEqual(structured["company_name"], "Test Tech Co")

    def test_extract_orchestration_context_structured_with_compression(self):
        """Test structured context extraction with compression events."""
        llm = self._StubLLM()
        reflector = Reflector(llm)

        state = {
            "ticker_info": {
                "segment": "cn_main_board_equity",
                "style_bucket": "dividend_style_candidate",
                "skills": [],
                "selected_analysts": [],
                "ticker": "600519",
                "company_name": "Kweichow Moutai",
                "trade_date": "2025-05-01",
            },
            "orchestration": {
                "stage": "completed",
                "phase": "completed",
                "final_route": "portfolio_handoff",
                "final_reason": "complex_risk",
                "event_trail": [
                    {"stage": "analyst", "phase": "analyst_market", "compression_triggered": True},
                    {"stage": "analyst", "phase": "analyst_news", "compression_triggered": True},
                    {"stage": "research", "phase": "research_bull", "compression_triggered": False},
                    {"stage": "research", "phase": "research_bear", "compression_triggered": False},
                    {"stage": "trader", "phase": "trader_phase", "compression_triggered": True},
                ],
            },
        }

        structured = reflector._extract_orchestration_context_structured(state)

        # Check compression info
        self.assertEqual(structured["compression_rate"], 0.6)  # 3/5 = 0.6
        self.assertTrue(structured["compression_triggered"])
        self.assertEqual(structured["compression_phases"], ["analyst_market", "analyst_news", "trader_phase"])
        self.assertEqual(structured["route_category"], "complex")  # >= 0.5

        # Check bottleneck detection
        self.assertIn("analyst", structured["bottleneck_stages"])  # visited twice

    def test_extract_orchestration_context_structured_mixed_route(self):
        """Test structured context extraction with mixed compression rate."""
        llm = self._StubLLM()
        reflector = Reflector(llm)

        state = {
            "ticker_info": {
                "segment": "cn_chinext_equity",
                "style_bucket": "value_style_candidate",
                "skills": [],
                "selected_analysts": [],
                "ticker": "300750",
                "company_name": "Test Co",
                "trade_date": "2025-05-01",
            },
            "orchestration": {
                "stage": "completed",
                "phase": "completed",
                "final_route": "compression_handoff",
                "final_reason": "medium_complexity",
                "event_trail": [
                    {"stage": "analyst", "phase": "analyst_market", "compression_triggered": False},
                    {"stage": "research", "phase": "research_bull", "compression_triggered": True},
                    {"stage": "research", "phase": "research_bear", "compression_triggered": False},
                    {"stage": "trader", "phase": "trader_phase", "compression_triggered": False},
                ],
            },
        }

        structured = reflector._extract_orchestration_context_structured(state)

        # Check mixed route category (0 < rate < 0.5)
        self.assertEqual(structured["compression_rate"], 0.25)  # 1/4 = 0.25
        self.assertEqual(structured["route_category"], "mixed")

    def test_get_route_summary_returns_structured_data(self):
        """Test that get_route_summary returns comprehensive structured data."""
        llm = self._StubLLM()
        reflector = Reflector(llm)

        state = {
            "ticker_info": {},
            "orchestration": {
                "final_route": "portfolio",
                "final_reason": "test_reason",
                "event_trail": [
                    {"stage": "analyst", "phase": "analyst_market", "compression_triggered": False, "node": "market_analyst"},
                    {"stage": "research", "phase": "research_bull", "compression_triggered": True, "node": "bull_researcher"},
                    {"stage": "trader", "phase": "trader_phase", "compression_triggered": False, "node": "trader"},
                ],
            },
        }

        summary = reflector.get_route_summary(state)

        self.assertEqual(summary["final_route"], "portfolio")
        self.assertEqual(summary["final_reason"], "test_reason")
        self.assertEqual(summary["route_taken"], ["market_analyst", "bull_researcher", "trader"])
        self.assertTrue(summary["compression_triggered"])
        self.assertEqual(summary["compression_phases"], ["research_bull"])
        self.assertEqual(summary["pattern_analysis"]["total_events"], 3)
        self.assertEqual(summary["pattern_analysis"]["compression_count"], 1)


if __name__ == "__main__":
    unittest.main()
