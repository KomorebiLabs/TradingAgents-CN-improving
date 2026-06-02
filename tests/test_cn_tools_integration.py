"""
Integration tests for CN tools system.

Tests cover:
- Full tool mounting chain
- Tool routing through interface
- End-to-end tool definitions
"""

import unittest
from unittest.mock import patch, MagicMock

# Import tools
from tradingagents.agents.utils.agent_utils import get_tools_for_analyst


class TestIntegrationToolMounting(unittest.TestCase):
    """Integration tests for full tool mounting chain."""

    def test_star_market_news_analyst_tools(self):
        """STAR Market (688) should get tech + policy tools for news analyst."""
        tools = get_tools_for_analyst("news", "688981.SH")
        tool_names = [t.name for t in tools]

        # Should have base tools
        self.assertIn("get_news", tool_names)
        self.assertIn("get_cn_policy_news", tool_names)

        # Should have sector tools
        self.assertIn("get_cn_tech_sector_news", tool_names)

    def test_chinext_news_analyst_tools(self):
        """ChiNext (300) should get tech + policy tools for news analyst."""
        tools = get_tools_for_analyst("news", "300750.SZ")
        tool_names = [t.name for t in tools]

        # Should have base tools
        self.assertIn("get_news", tool_names)
        self.assertIn("get_cn_policy_news", tool_names)

        # Should have sector tools
        self.assertIn("get_cn_tech_sector_news", tool_names)

    def test_main_board_news_analyst_tools(self):
        """Main board (600/000) should get base news tools only."""
        tools = get_tools_for_analyst("news", "600519.SH")
        tool_names = [t.name for t in tools]

        # Should have base tools
        self.assertIn("get_news", tool_names)
        self.assertNotIn("get_cn_policy_news", tool_names)

        # Should NOT have sector tools by default
        self.assertNotIn("get_cn_tech_sector_news", tool_names)

    def test_market_analyst_cn_tools(self):
        """Market analyst should get CN market flow for growth tickers."""
        # Growth style ticker
        tools = get_tools_for_analyst("market", "300750.SZ")
        tool_names = [t.name for t in tools]
        self.assertIn("get_cn_market_flow", tool_names)

        # Non-growth main board
        tools = get_tools_for_analyst("market", "600519.SH")
        tool_names = [t.name for t in tools]
        self.assertNotIn("get_cn_market_flow", tool_names)

    def test_bse_market_analyst_tools(self):
        """BSE market analyst should NOT get indicators."""
        tools = get_tools_for_analyst("market", "430001.BJ")
        tool_names = [t.name for t in tools]
        self.assertNotIn("get_indicators", tool_names)


class TestIntegrationToolRouting(unittest.TestCase):
    """Test tool routing through interface layer."""

    def test_all_cn_sector_tools_registered(self):
        """All CN sector tools should be registered in interface."""
        from tradingagents.dataflows.interface import VENDOR_METHODS

        expected_tools = [
            "get_cn_tech_sector_news",
            "get_cn_new_energy_news",
            "get_cn_pharma_news",
            "get_cn_real_estate_news",
            "get_cn_fintech_news",
        ]

        for tool_name in expected_tools:
            self.assertIn(tool_name, VENDOR_METHODS)
            self.assertIn("akshare", VENDOR_METHODS[tool_name])

    def test_all_cn_macro_tools_registered(self):
        """All CN macro tools should be registered in interface."""
        from tradingagents.dataflows.interface import VENDOR_METHODS

        expected_tools = [
            "get_cn_macro_data",
            "get_cn_rate_outlook",
            "get_cn_trade_data",
        ]

        for tool_name in expected_tools:
            self.assertIn(tool_name, VENDOR_METHODS)
            self.assertIn("akshare", VENDOR_METHODS[tool_name])

    def test_all_cn_event_tools_registered(self):
        """All CN event tools should be registered in interface."""
        from tradingagents.dataflows.interface import VENDOR_METHODS

        expected_tools = [
            "get_cn_earnings_calendar",
            "get_cn_ipo_data",
            "get_cn_m_a_news",
            "get_cn_stock_pledge",
            "get_cn_limit_up_stocks",
        ]

        for tool_name in expected_tools:
            self.assertIn(tool_name, VENDOR_METHODS)
            self.assertIn("akshare", VENDOR_METHODS[tool_name])


class TestIntegrationCategories(unittest.TestCase):
    """Test tool categories registration."""

    def test_news_data_category_includes_sector_tools(self):
        """news_data category should include CN sector tools."""
        from tradingagents.dataflows.interface import TOOLS_CATEGORIES

        news_tools = TOOLS_CATEGORIES["news_data"]["tools"]

        self.assertIn("get_cn_tech_sector_news", news_tools)
        self.assertIn("get_cn_new_energy_news", news_tools)
        self.assertIn("get_cn_pharma_news", news_tools)
        self.assertIn("get_cn_real_estate_news", news_tools)
        self.assertIn("get_cn_fintech_news", news_tools)

    def test_cn_macro_data_category_exists(self):
        """cn_macro_data category should exist."""
        from tradingagents.dataflows.interface import TOOLS_CATEGORIES

        self.assertIn("cn_macro_data", TOOLS_CATEGORIES)

        macro_tools = TOOLS_CATEGORIES["cn_macro_data"]["tools"]
        self.assertIn("get_cn_macro_data", macro_tools)
        self.assertIn("get_cn_rate_outlook", macro_tools)
        self.assertIn("get_cn_trade_data", macro_tools)

    def test_cn_event_data_category_exists(self):
        """cn_event_data category should exist."""
        from tradingagents.dataflows.interface import TOOLS_CATEGORIES

        self.assertIn("cn_event_data", TOOLS_CATEGORIES)

        event_tools = TOOLS_CATEGORIES["cn_event_data"]["tools"]
        self.assertIn("get_cn_earnings_calendar", event_tools)
        self.assertIn("get_cn_ipo_data", event_tools)
        self.assertIn("get_cn_m_a_news", event_tools)
        self.assertIn("get_cn_stock_pledge", event_tools)
        self.assertIn("get_cn_limit_up_stocks", event_tools)


class TestIntegrationCompleteChain(unittest.TestCase):
    """End-to-end integration tests."""

    def test_all_new_tools_importable(self):
        """All new CN tools should be importable."""
        # Sector tools
        from tradingagents.agents.utils.cn_sector_news_tools import (
            get_cn_tech_sector_news,
            get_cn_new_energy_news,
            get_cn_pharma_news,
            get_cn_real_estate_news,
            get_cn_fintech_news,
        )

        # Macro tools
        from tradingagents.agents.utils.cn_macro_tools import (
            get_cn_macro_data,
            get_cn_rate_outlook,
            get_cn_trade_data,
        )

        # Event tools
        from tradingagents.agents.utils.cn_event_tools import (
            get_cn_earnings_calendar,
            get_cn_ipo_data,
            get_cn_m_a_news,
            get_cn_stock_pledge,
            get_cn_limit_up_stocks,
        )

        # All should have names
        all_tools = [
            get_cn_tech_sector_news,
            get_cn_new_energy_news,
            get_cn_pharma_news,
            get_cn_real_estate_news,
            get_cn_fintech_news,
            get_cn_macro_data,
            get_cn_rate_outlook,
            get_cn_trade_data,
            get_cn_earnings_calendar,
            get_cn_ipo_data,
            get_cn_m_a_news,
            get_cn_stock_pledge,
            get_cn_limit_up_stocks,
        ]

        for tool in all_tools:
            self.assertTrue(hasattr(tool, 'name'))
            self.assertTrue(hasattr(tool, 'description'))

    def test_tool_count_increase(self):
        """Verify tool count has increased from baseline."""
        from tradingagents.dataflows.interface import TOOLS_CATEGORIES

        # Count all tools across all categories
        all_tools = []
        for category_info in TOOLS_CATEGORIES.values():
            all_tools.extend(category_info["tools"])

        # Should have significantly more tools now
        # Baseline was about 8-10 tools in news_data
        # Now should have 5 sector + 3 macro + 5 event = 13 new tools
        news_tools = TOOLS_CATEGORIES["news_data"]["tools"]
        self.assertGreaterEqual(len(news_tools), 10)  # At least original + sector tools


if __name__ == "__main__":
    unittest.main()
