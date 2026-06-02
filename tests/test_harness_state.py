import unittest

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.propagation import Propagator
from tradingagents.graph.trading_graph import TradingAgentsGraph


class HarnessStateTests(unittest.TestCase):
    def test_create_initial_state_preserves_selected_analysts(self):
        propagator = Propagator(
            config={
                "enable_confidence_score": True,
                "screener_context": {
                    "semantic_prompt_slots": {
                        "schema_name": "screener.semantic_prompt_slots",
                        "schema_version": "1.0",
                        "policy_role": "policy_top_stock",
                        "capital_quality": "capital_quality_high",
                    }
                },
                "semantic_flow_controls": {
                    "debate_round_limit": 2,
                    "risk_round_limit": 1,
                    "force_risk_review": False,
                    "risk_hardening": False,
                },
                "instrument_skill_rules": {
                    "cn_equity": ["cn_market_data", "cn_macro_news"],
                    "cn_main_board_equity": ["cn_main_board_routing"],
                    "dividend_style_candidate": ["dividend_factor_focus"],
                    "us_equity": ["global_news"],
                },
            }
        )
        state = propagator.create_initial_state(
            "600519.SH",
            "2026-05-05",
            ["market", "news"],
        )

        self.assertEqual(state["ticker_info"]["selected_analysts"], ["market", "news"])
        self.assertEqual(state["orchestration"]["selected_analysts"], ["market", "news"])
        self.assertTrue(state["orchestration"]["enable_confidence_score"])
        self.assertEqual(state["orchestration"]["phase"], "analyst")
        self.assertEqual(state["orchestration"]["next_stage"], "analyst")
        self.assertFalse(state["orchestration"]["completed"])
        self.assertEqual(state["orchestration"]["final_route"], "")
        self.assertEqual(state["orchestration"]["final_reason"], "")
        self.assertFalse(state["orchestration"]["compression_required"])
        self.assertEqual(state["ticker_info"]["market"], "cn_equity")
        self.assertTrue(state["ticker_info"]["is_cn_equity"])
        self.assertEqual(state["ticker_info"]["segment"], "cn_main_board_equity")
        self.assertEqual(state["ticker_info"]["style_bucket"], "dividend_style_candidate")
        self.assertIn("cn_market_data", state["ticker_info"]["skills"])
        self.assertEqual(state["semantic_prompt_slots"]["policy_role"], "policy_top_stock")
        self.assertEqual(state["semantic_prompt_slots"]["schema_name"], "screener.semantic_prompt_slots")
        self.assertEqual(state["semantic_prompt_slots"]["schema_version"], "1.0")
        self.assertEqual(state["screener_context"]["semantic_prompt_slots"]["capital_quality"], "capital_quality_high")
        self.assertEqual(state["ticker_info"]["semantic_flow_controls"]["debate_round_limit"], 2)
        self.assertEqual(state["orchestration"]["semantic_flow_controls"]["risk_round_limit"], 1)

    def test_synchronize_structured_state_backfills_blocks(self):
        graph = TradingAgentsGraph(
            selected_analysts=["market"],
            config=DEFAULT_CONFIG.copy(),
            debug=False,
        )
        state = {
            "company_of_interest": "000001.SZ",
            "trade_date": "2026-05-05",
            "market_report": "market",
            "sentiment_report": "sentiment",
            "news_report": "news",
            "fundamentals_report": "fundamentals",
            "investment_debate_state": {"history": "bull vs bear"},
            "risk_debate_state": {"history": "risk debate"},
            "investment_plan": "plan",
            "trader_investment_plan": "trader",
            "final_trade_decision": "final",
        }

        synced = graph._synchronize_structured_state(state)

        self.assertEqual(synced["ticker_info"]["symbol"], "000001.SZ")
        self.assertEqual(synced["ticker_info"]["market"], "cn_equity")
        self.assertEqual(synced["ticker_info"]["segment"], "cn_main_board_equity")
        self.assertIn("cn_market_data", synced["ticker_info"]["skills"])
        self.assertEqual(synced["orchestration"]["phase"], "completed")
        self.assertTrue(synced["orchestration"]["completed"])
        self.assertEqual(synced["analyst_reports"]["market"], "market")
        self.assertEqual(synced["decision_blocks"]["trader_plan"], "trader")
        self.assertEqual(synced["debate_blocks"]["investment"]["history"], "bull vs bear")


if __name__ == "__main__":
    unittest.main()
