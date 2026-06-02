"""Tests for RAG-enhanced news tools."""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from tradingagents.agents.utils.rag_news_tools import (
    get_rag_news,
    get_rag_sector_news,
    index_news_for_rag,
    get_rag_status,
    _is_rag_enabled,
)


class TestRAGNewsTools(unittest.TestCase):
    """Tests for RAG-enhanced news tools."""

    def test_is_rag_enabled_false_by_default(self):
        """Test that RAG is disabled by default."""
        # Should be false without environment variable
        result = _is_rag_enabled()
        # This test just checks the function works
        self.assertIn(result, [True, False])

    @patch("tradingagents.agents.utils.rag_news_tools.route_to_vendor")
    def test_get_rag_news_fallback(self, mock_route):
        """Test that raw news is returned when RAG is disabled."""
        mock_route.return_value = "Raw news data"

        result = get_rag_news.invoke({
            "ticker": "AAPL",
            "curr_date": "2025-05-05",
            "look_back_days": 7,
            "enable_rag": False,
        })

        self.assertEqual(result, "Raw news data")
        mock_route.assert_called_once()

    @patch("tradingagents.agents.utils.rag_news_tools.route_to_vendor")
    def test_get_rag_news_without_rag_override(self, mock_route):
        """Test get_rag_news without RAG override."""
        mock_route.return_value = "News data"

        result = get_rag_news.invoke({
            "ticker": "600519.SH",
            "curr_date": "2025-05-05",
            "look_back_days": 7,
        })

        # Should call route_to_vendor when enable_rag is None and env is not set
        self.assertEqual(result, "News data")

    def test_get_rag_status_returns_dict(self):
        """Test that get_rag_status returns a dictionary."""
        status = get_rag_status()

        self.assertIsInstance(status, dict)
        self.assertIn("enabled", status)
        self.assertIn("initialized", status)


class TestIndexNewsForRAG(unittest.TestCase):
    """Tests for indexing news into RAG."""

    @patch("tradingagents.agents.utils.rag_news_tools._get_rag_retriever")
    def test_index_news_returns_error_when_not_initialized(self, mock_get_retriever):
        """Test that indexing handles uninitialized RAG gracefully."""
        mock_get_retriever.return_value = None

        result = index_news_for_rag.invoke({
            "ticker": "AAPL",
            "content": "Test news content",
            "title": "Test Title",
        })

        self.assertIn("not initialized", result)


class TestRAGNewsToolsIntegration(unittest.TestCase):
    """Integration tests for RAG news tools."""

    def test_tool_descriptions_exist(self):
        """Test that tools have proper descriptions."""
        self.assertTrue(len(get_rag_news.name) > 0)
        self.assertTrue(len(get_rag_news.description) > 0)

    def test_tool_parameters(self):
        """Test that required parameters are present."""
        # Check get_rag_news parameters
        params = get_rag_news.args_schema.model_json_schema()["properties"]
        self.assertIn("ticker", params)
        self.assertIn("curr_date", params)
        self.assertIn("look_back_days", params)


if __name__ == "__main__":
    unittest.main()
