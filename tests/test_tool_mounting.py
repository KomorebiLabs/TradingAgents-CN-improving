import unittest

from tradingagents.agents.utils.agent_utils import build_instrument_context, get_tools_for_analyst


class ToolMountingTests(unittest.TestCase):
    def test_cn_fundamentals_only_mounts_snapshot_tool_when_akshare_enabled(self):
        config = {
            "data_vendors": {
                "fundamental_data": "akshare",
            },
            "tool_vendors": {},
        }

        tools = get_tools_for_analyst("fundamentals", "600519.SH", config)

        self.assertEqual([tool.name for tool in tools], ["get_fundamentals"])

    def test_us_fundamentals_keeps_full_financial_toolset(self):
        config = {
            "data_vendors": {
                "fundamental_data": "yfinance",
            },
            "tool_vendors": {},
        }

        tools = get_tools_for_analyst("fundamentals", "NVDA", config)

        self.assertEqual(
            [tool.name for tool in tools],
            [
                "get_fundamentals",
                "get_balance_sheet",
                "get_cashflow",
                "get_income_statement",
            ],
        )

    def test_cn_market_tools_remain_available(self):
        config = {
            "data_vendors": {
                "core_stock_apis": "akshare",
            },
            "instrument_skill_rules": {
                "cn_equity": ["cn_market_data", "cn_macro_news"],
                "us_equity": ["global_news"],
            },
            "tool_vendors": {},
        }

        tools = get_tools_for_analyst("market", "300750.SZ", config)

        self.assertEqual([tool.name for tool in tools], ["get_stock_data", "get_indicators"])

    def test_cn_news_tools_follow_skill_mounting(self):
        # Test that CN news tools follow skill mounting rules
        enabled_config = {
            "data_vendors": {
                "news_data": "akshare",
            },
            "instrument_skill_rules": {
                "cn_equity": ["cn_market_data", "cn_macro_news"],  # cn_macro_news enables macro tools
                "us_equity": ["global_news"],
            },
            "tool_vendors": {},
        }

        disabled_config = {
            "data_vendors": {
                "news_data": "akshare",
            },
            "instrument_skill_rules": {
                "cn_equity": ["cn_market_data"],  # No cn_macro_news
                "us_equity": ["global_news"],
            },
            "tool_vendors": {},
        }

        enabled_tools = get_tools_for_analyst("news", "600519.SH", enabled_config)
        disabled_tools = get_tools_for_analyst("news", "600519.SH", disabled_config)

        # With cn_macro_news skill: macro tools are mounted
        enabled_tool_names = [tool.name for tool in enabled_tools]
        self.assertIn("get_cn_macro_data", enabled_tool_names)
        self.assertIn("get_cn_rate_outlook", enabled_tool_names)
        self.assertIn("get_cn_trade_data", enabled_tool_names)

        # Without cn_macro_news skill: no macro tools
        disabled_tool_names = [tool.name for tool in disabled_tools]
        self.assertNotIn("get_cn_macro_data", disabled_tool_names)
        self.assertNotIn("get_cn_rate_outlook", disabled_tool_names)
        self.assertNotIn("get_cn_trade_data", disabled_tool_names)

    def test_segment_profiles_change_tool_mounting(self):
        config = {
            "data_vendors": {
                "fundamental_data": "yfinance",
            },
            "instrument_skill_rules": {
                "cn_equity": ["cn_market_data", "cn_macro_news"],
                "cn_chinext_equity": ["chinext_growth_board"],
                "cn_star_equity": ["star_market_policy"],
                "cn_bse_equity": ["bse_liquidity_watch"],
                "growth_style_candidate": ["growth_factor_focus"],
            },
            "tool_vendors": {},
        }

        chinext_fundamentals = get_tools_for_analyst("fundamentals", "300750.SZ", config)
        star_fundamentals = get_tools_for_analyst("fundamentals", "688041.SH", config)
        bse_market = get_tools_for_analyst("market", "430047.BJ", config)

        self.assertEqual(
            [tool.name for tool in chinext_fundamentals],
            ["get_fundamentals", "get_balance_sheet", "get_cashflow"],
        )
        self.assertEqual(
            [tool.name for tool in star_fundamentals],
            ["get_fundamentals", "get_balance_sheet", "get_cashflow"],
        )
        self.assertEqual([tool.name for tool in bse_market], ["get_stock_data", "get_cn_market_flow"])

    def test_instrument_context_includes_segment_notes(self):
        context = build_instrument_context("688041.SH")

        self.assertIn("segment=cn_star_equity", context)
        self.assertIn("STAR Market listing", context)

    def test_cn_specialized_tools_mount_for_growth_and_bse_segments(self):
        config = {
            "data_vendors": {
                "fundamental_data": "yfinance",
            },
            "instrument_skill_rules": {
                "cn_equity": ["cn_market_data", "cn_macro_news"],
                "cn_chinext_equity": ["chinext_growth_board"],
                "cn_star_equity": ["star_market_policy"],
                "cn_bse_equity": ["bse_liquidity_watch"],
                "growth_style_candidate": ["growth_factor_focus"],
            },
            "tool_vendors": {},
        }

        star_news = get_tools_for_analyst("news", "688041.SH", config)
        chinext_market = get_tools_for_analyst("market", "300750.SZ", config)
        bse_market = get_tools_for_analyst("market", "430047.BJ", config)

        self.assertIn("get_cn_policy_news", [tool.name for tool in star_news])
        self.assertIn("get_cn_market_flow", [tool.name for tool in chinext_market])
        self.assertIn("get_cn_market_flow", [tool.name for tool in bse_market])


if __name__ == "__main__":
    unittest.main()
