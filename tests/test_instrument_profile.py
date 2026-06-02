import unittest

from tradingagents.agents.utils.agent_utils import (
    build_instrument_profile,
    get_segment_advisory,
)


class InstrumentProfileTests(unittest.TestCase):
    def test_cn_equity_profile_activates_cn_skills(self):
        config = {
            "instrument_skill_rules": {
                "cn_equity": ["cn_market_data", "cn_macro_news"],
                "cn_main_board_equity": ["cn_main_board_routing"],
                "dividend_style_candidate": ["dividend_factor_focus"],
                "us_equity": ["global_news"],
            }
        }

        profile = build_instrument_profile("600519.SH", config)

        self.assertEqual(profile["market"], "cn_equity")
        self.assertEqual(profile["exchange"], "SH")
        self.assertTrue(profile["is_cn_equity"])
        self.assertEqual(profile["segment"], "cn_main_board_equity")
        self.assertEqual(profile["style_bucket"], "dividend_style_candidate")
        self.assertEqual(
            profile["skills"],
            [
                "cn_market_data",
                "cn_macro_news",
                "cn_main_board_routing",
                "dividend_factor_focus",
            ],
        )

    def test_us_equity_profile_activates_us_skills(self):
        config = {
            "instrument_skill_rules": {
                "cn_equity": ["cn_market_data"],
                "us_equity": ["global_news", "us_financial_statements"],
            }
        }

        profile = build_instrument_profile("NVDA", config)

        self.assertEqual(profile["market"], "global_equity")
        self.assertFalse(profile["is_cn_equity"])
        self.assertEqual(profile["skills"], ["global_news", "us_financial_statements"])

    def test_chinext_and_star_segments_are_classified(self):
        config = {
            "instrument_skill_rules": {
                "cn_equity": ["cn_market_data"],
                "cn_chinext_equity": ["chinext_growth_board"],
                "cn_star_equity": ["star_market_policy"],
                "growth_style_candidate": ["growth_factor_focus"],
            }
        }

        chinext = build_instrument_profile("300750.SZ", config)
        star = build_instrument_profile("688041.SH", config)

        self.assertEqual(chinext["segment"], "cn_chinext_equity")
        self.assertIn("chinext_growth_board", chinext["skills"])
        self.assertIn("growth_factor_focus", chinext["skills"])
        self.assertEqual(star["segment"], "cn_star_equity")
        self.assertIn("star_market_policy", star["skills"])

    def test_segment_advisory_varies_by_audience(self):
        self.assertIn(
            "policy",
            get_segment_advisory("688041.SH", "news").lower(),
        )
        self.assertIn(
            "volatility",
            get_segment_advisory("300750.SZ", "market").lower(),
        )
        self.assertIn(
            "conservative sizing",
            get_segment_advisory("430047.BJ", "risk").lower(),
        )


if __name__ == "__main__":
    unittest.main()
