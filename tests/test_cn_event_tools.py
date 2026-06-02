"""
Tests for CN event-driven tools.

Tests cover:
- Tool definitions and imports
- Tool parameter validation
"""

import unittest

# Import tools to test
from tradingagents.agents.utils.cn_event_tools import (
    get_cn_earnings_calendar,
    get_cn_ipo_data,
    get_cn_m_a_news,
    get_cn_stock_pledge,
    get_cn_limit_up_stocks,
)


class TestEventToolDefinitions(unittest.TestCase):
    """Test that event tools are properly defined."""

    def test_earnings_calendar_tool_is_langchain_tool(self):
        """get_cn_earnings_calendar should be a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool
        self.assertIsInstance(get_cn_earnings_calendar, StructuredTool)
        self.assertEqual(get_cn_earnings_calendar.name, "get_cn_earnings_calendar")

    def test_ipo_data_tool_is_langchain_tool(self):
        """get_cn_ipo_data should be a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool
        self.assertIsInstance(get_cn_ipo_data, StructuredTool)
        self.assertEqual(get_cn_ipo_data.name, "get_cn_ipo_data")

    def test_m_a_news_tool_is_langchain_tool(self):
        """get_cn_m_a_news should be a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool
        self.assertIsInstance(get_cn_m_a_news, StructuredTool)
        self.assertEqual(get_cn_m_a_news.name, "get_cn_m_a_news")

    def test_stock_pledge_tool_is_langchain_tool(self):
        """get_cn_stock_pledge should be a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool
        self.assertIsInstance(get_cn_stock_pledge, StructuredTool)
        self.assertEqual(get_cn_stock_pledge.name, "get_cn_stock_pledge")

    def test_limit_up_stocks_tool_is_langchain_tool(self):
        """get_cn_limit_up_stocks should be a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool
        self.assertIsInstance(get_cn_limit_up_stocks, StructuredTool)
        self.assertEqual(get_cn_limit_up_stocks.name, "get_cn_limit_up_stocks")

    def test_tools_have_descriptions(self):
        """All event tools should have non-empty descriptions."""
        tools = [
            get_cn_earnings_calendar,
            get_cn_ipo_data,
            get_cn_m_a_news,
            get_cn_stock_pledge,
            get_cn_limit_up_stocks,
        ]
        for tool in tools:
            self.assertIsNotNone(tool.description)
            self.assertGreater(len(tool.description), 10)


class TestEventToolParameters(unittest.TestCase):
    """Test event tool parameter definitions."""

    def test_earnings_calendar_has_look_forward_param(self):
        """get_cn_earnings_calendar should have look_forward_days param."""
        params = get_cn_earnings_calendar.args_schema.model_json_schema()
        self.assertIn("look_forward_days", params.get("properties", {}))

    def test_earnings_calendar_has_market_param(self):
        """get_cn_earnings_calendar should have market param."""
        params = get_cn_earnings_calendar.args_schema.model_json_schema()
        self.assertIn("market", params.get("properties", {}))

    def test_ipo_data_has_status_param(self):
        """get_cn_ipo_data should have status param."""
        params = get_cn_ipo_data.args_schema.model_json_schema()
        self.assertIn("status", params.get("properties", {}))

    def test_ipo_data_has_limit_param(self):
        """get_cn_ipo_data should have limit param."""
        params = get_cn_ipo_data.args_schema.model_json_schema()
        self.assertIn("limit", params.get("properties", {}))

    def test_m_a_news_has_ticker_param(self):
        """get_cn_m_a_news should have ticker param."""
        params = get_cn_m_a_news.args_schema.model_json_schema()
        self.assertIn("ticker", params.get("properties", {}))

    def test_m_a_news_has_look_back_param(self):
        """get_cn_m_a_news should have look_back_days param."""
        params = get_cn_m_a_news.args_schema.model_json_schema()
        self.assertIn("look_back_days", params.get("properties", {}))

    def test_stock_pledge_has_ticker_param(self):
        """get_cn_stock_pledge should have ticker param."""
        params = get_cn_stock_pledge.args_schema.model_json_schema()
        self.assertIn("ticker", params.get("properties", {}))

    def test_limit_up_stocks_has_trade_date_param(self):
        """get_cn_limit_up_stocks should have trade_date param."""
        params = get_cn_limit_up_stocks.args_schema.model_json_schema()
        self.assertIn("trade_date", params.get("properties", {}))


if __name__ == "__main__":
    unittest.main()
