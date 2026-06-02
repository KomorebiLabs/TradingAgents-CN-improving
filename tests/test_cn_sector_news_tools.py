"""
Tests for CN sector news tools.

Tests cover:
- Tool definitions and imports
- Sector mapping utilities
- Tool mounting logic in agent_utils
"""

import unittest
from unittest.mock import patch, MagicMock
from typing import List

# Import tools to test
from tradingagents.agents.utils.cn_sector_news_tools import (
    get_cn_tech_sector_news,
    get_cn_new_energy_news,
    get_cn_pharma_news,
    get_cn_real_estate_news,
    get_cn_fintech_news,
    get_sector_for_ticker,
    get_sector_tools_for_ticker,
    SEGMENT_SECTOR_MAP,
    STYLE_SECTOR_MAP,
    INDUSTRY_SECTOR_MAP,
)


class TestSectorMapping(unittest.TestCase):
    """Test sector mapping utilities."""

    def test_star_market_ticker_tech(self):
        """STAR Market tickers should map to tech sector."""
        # 688 prefix = STAR Market (Science and Technology Innovation Board)
        result = get_sector_for_ticker("688981.SH")
        self.assertEqual(result, "tech")

        result = get_sector_for_ticker("688041.SZ")  # Note: STAR is SH exchange
        self.assertEqual(result, "tech")

    def test_chinext_ticker_tech(self):
        """ChiNext tickers should map to tech sector."""
        # 300 prefix = ChiNext Growth Enterprise Market
        result = get_sector_for_ticker("300750.SZ")
        self.assertEqual(result, "tech")

        result = get_sector_for_ticker("300014.SZ")
        self.assertEqual(result, "tech")

    def test_main_board_ticker_no_default_sector(self):
        """Main board tickers should not map to specific sector by default."""
        # 600/601/000 prefix = Main board
        result = get_sector_for_ticker("600519.SH")
        self.assertIsNone(result)

        result = get_sector_for_ticker("000001.SZ")
        self.assertIsNone(result)

    def test_industry_based_sector_mapping(self):
        """Industry parameter should enable sector mapping for main board."""
        result = get_sector_for_ticker("600519.SH", industry="白酒")
        self.assertIsNone(result)  # No specific sector for liquor

        result = get_sector_for_ticker("601012.SH", industry="电气设备")
        self.assertEqual(result, "new_energy")

        result = get_sector_for_ticker("000002.SZ", industry="房地产")
        self.assertEqual(result, "real_estate")

    def test_industry_sector_map_completeness(self):
        """Verify industry sector map covers expected industries."""
        # Tech industries
        self.assertIn("计算机", INDUSTRY_SECTOR_MAP)
        self.assertIn("电子", INDUSTRY_SECTOR_MAP)
        self.assertIn("半导体", INDUSTRY_SECTOR_MAP)

        # New energy industries
        self.assertIn("电气设备", INDUSTRY_SECTOR_MAP)
        self.assertIn("汽车", INDUSTRY_SECTOR_MAP)

        # Pharma industries
        self.assertIn("医药生物", INDUSTRY_SECTOR_MAP)
        self.assertIn("医疗器械", INDUSTRY_SECTOR_MAP)

        # Real estate
        self.assertIn("房地产", INDUSTRY_SECTOR_MAP)


class TestSectorToolGetters(unittest.TestCase):
    """Test sector tool getter functions."""

    def test_get_sector_tools_star_market(self):
        """STAR Market tickers should get tech tools."""
        tools = get_sector_tools_for_ticker("688981.SH")
        tool_names = [t.name for t in tools]
        self.assertIn("get_cn_tech_sector_news", tool_names)

    def test_get_sector_tools_chinext(self):
        """ChiNext tickers should get tech tools."""
        tools = get_sector_tools_for_ticker("300750.SZ")
        tool_names = [t.name for t in tools]
        self.assertIn("get_cn_tech_sector_news", tool_names)

    def test_get_sector_tools_with_industry(self):
        """Industry should enable sector-specific tools for main board."""
        # New energy industry
        tools = get_sector_tools_for_ticker("601012.SH", industry="电气设备")
        tool_names = [t.name for t in tools]
        self.assertIn("get_cn_new_energy_news", tool_names)

        # Real estate
        tools = get_sector_tools_for_ticker("000002.SZ", industry="房地产")
        tool_names = [t.name for t in tools]
        self.assertIn("get_cn_real_estate_news", tool_names)

    def test_get_sector_tools_main_board_no_industry(self):
        """Main board tickers without industry should get no sector tools."""
        tools = get_sector_tools_for_ticker("600519.SH")
        self.assertEqual(len(tools), 0)

    def test_get_sector_tools_pharma(self):
        """Pharma industry should get pharma tools."""
        tools = get_sector_tools_for_ticker("600276.SH", industry="医药生物")
        tool_names = [t.name for t in tools]
        self.assertIn("get_cn_pharma_news", tool_names)

    def test_get_sector_tools_fintech(self):
        """Financial industry should get fintech tools."""
        tools = get_sector_tools_for_ticker("600036.SH", industry="银行")
        tool_names = [t.name for t in tools]
        self.assertIn("get_cn_fintech_news", tool_names)


class TestToolDefinitions(unittest.TestCase):
    """Test that tools are properly defined as LangChain tools."""

    def test_tech_tool_is_langchain_structured_tool(self):
        """get_cn_tech_sector_news should be a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool
        self.assertIsInstance(get_cn_tech_sector_news, StructuredTool)
        self.assertEqual(get_cn_tech_sector_news.name, "get_cn_tech_sector_news")

    def test_new_energy_tool_is_langchain_structured_tool(self):
        """get_cn_new_energy_news should be a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool
        self.assertIsInstance(get_cn_new_energy_news, StructuredTool)
        self.assertEqual(get_cn_new_energy_news.name, "get_cn_new_energy_news")

    def test_pharma_tool_is_langchain_structured_tool(self):
        """get_cn_pharma_news should be a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool
        self.assertIsInstance(get_cn_pharma_news, StructuredTool)
        self.assertEqual(get_cn_pharma_news.name, "get_cn_pharma_news")

    def test_real_estate_tool_is_langchain_structured_tool(self):
        """get_cn_real_estate_news should be a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool
        self.assertIsInstance(get_cn_real_estate_news, StructuredTool)
        self.assertEqual(get_cn_real_estate_news.name, "get_cn_real_estate_news")

    def test_fintech_tool_is_langchain_structured_tool(self):
        """get_cn_fintech_news should be a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool
        self.assertIsInstance(get_cn_fintech_news, StructuredTool)
        self.assertEqual(get_cn_fintech_news.name, "get_cn_fintech_news")

    def test_tools_have_proper_descriptions(self):
        """All sector tools should have non-empty descriptions."""
        tools = [
            get_cn_tech_sector_news,
            get_cn_new_energy_news,
            get_cn_pharma_news,
            get_cn_real_estate_news,
            get_cn_fintech_news,
        ]
        for tool in tools:
            self.assertIsNotNone(tool.description)
            self.assertGreater(len(tool.description), 10)


class TestSegmentSectorMap(unittest.TestCase):
    """Test segment to sector mapping."""

    def test_star_equity_maps_to_tech(self):
        """cn_star_equity should map to tech."""
        self.assertEqual(SEGMENT_SECTOR_MAP["cn_star_equity"], "tech")

    def test_chinext_maps_to_tech(self):
        """cn_chinext_equity should map to tech."""
        self.assertEqual(SEGMENT_SECTOR_MAP["cn_chinext_equity"], "tech")

    def test_main_board_no_default_sector(self):
        """cn_main_board_equity should not have default sector."""
        self.assertIsNone(SEGMENT_SECTOR_MAP["cn_main_board_equity"])

    def test_bse_no_default_sector(self):
        """cn_bse_equity should not have default sector."""
        self.assertIsNone(SEGMENT_SECTOR_MAP["cn_bse_equity"])


if __name__ == "__main__":
    unittest.main()
