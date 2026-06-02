"""
Tests for CN macro economic tools.

Tests cover:
- Tool definitions and imports
- Skill-based mounting logic
"""

import unittest
from unittest.mock import patch, MagicMock

# Import tools to test
from tradingagents.agents.utils.cn_macro_tools import (
    get_cn_macro_data,
    get_cn_rate_outlook,
    get_cn_trade_data,
    should_mount_macro_tools,
    MACRO_TOOL_SKILLS,
)


class TestMacroToolDefinitions(unittest.TestCase):
    """Test that macro tools are properly defined."""

    def test_macro_data_tool_is_langchain_tool(self):
        """get_cn_macro_data should be a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool
        self.assertIsInstance(get_cn_macro_data, StructuredTool)
        self.assertEqual(get_cn_macro_data.name, "get_cn_macro_data")

    def test_rate_outlook_tool_is_langchain_tool(self):
        """get_cn_rate_outlook should be a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool
        self.assertIsInstance(get_cn_rate_outlook, StructuredTool)
        self.assertEqual(get_cn_rate_outlook.name, "get_cn_rate_outlook")

    def test_trade_data_tool_is_langchain_tool(self):
        """get_cn_trade_data should be a LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool
        self.assertIsInstance(get_cn_trade_data, StructuredTool)
        self.assertEqual(get_cn_trade_data.name, "get_cn_trade_data")

    def test_tools_have_descriptions(self):
        """All macro tools should have non-empty descriptions."""
        tools = [get_cn_macro_data, get_cn_rate_outlook, get_cn_trade_data]
        for tool in tools:
            self.assertIsNotNone(tool.description)
            self.assertGreater(len(tool.description), 10)


class TestMacroSkillMounting(unittest.TestCase):
    """Test skill-based macro tool mounting logic."""

    def test_cn_macro_news_skill_enables_macro_tools(self):
        """cn_macro_news skill should enable macro tools."""
        skills = ["cn_macro_news"]
        self.assertTrue(should_mount_macro_tools(skills))

    def test_empty_skills_does_not_mount(self):
        """Empty skills should not enable macro tools."""
        skills = []
        self.assertFalse(should_mount_macro_tools(skills))

    def test_unrelated_skills_does_not_mount(self):
        """Unrelated skills should not enable macro tools."""
        skills = ["growth_factor_focus", "dividend_style"]
        self.assertFalse(should_mount_macro_tools(skills))

    def test_multiple_skills_with_macro(self):
        """Multiple skills including cn_macro_news should enable macro tools."""
        skills = ["growth_factor_focus", "cn_macro_news", "dividend_style"]
        self.assertTrue(should_mount_macro_tools(skills))

    def test_macro_skill_constant(self):
        """Verify MACRO_TOOL_SKILLS contains expected skills."""
        self.assertIn("cn_macro_news", MACRO_TOOL_SKILLS)


class TestMacroToolParameters(unittest.TestCase):
    """Test macro tool parameter definitions."""

    def test_macro_data_has_indicators_param(self):
        """get_cn_macro_data should accept indicators parameter."""
        # Check tool accepts list of indicators
        params = get_cn_macro_data.args_schema.model_json_schema()
        self.assertIn("indicators", params.get("properties", {}))

    def test_macro_data_has_period_param(self):
        """get_cn_macro_data should accept period parameter."""
        params = get_cn_macro_data.args_schema.model_json_schema()
        self.assertIn("period", params.get("properties", {}))

    def test_rate_outlook_has_focus_param(self):
        """get_cn_rate_outlook should accept focus parameter."""
        params = get_cn_rate_outlook.args_schema.model_json_schema()
        self.assertIn("focus", params.get("properties", {}))

    def test_trade_data_has_months_param(self):
        """get_cn_trade_data should accept months parameter."""
        params = get_cn_trade_data.args_schema.model_json_schema()
        self.assertIn("months", params.get("properties", {}))

    def test_trade_data_has_focus_param(self):
        """get_cn_trade_data should accept focus parameter."""
        params = get_cn_trade_data.args_schema.model_json_schema()
        self.assertIn("focus", params.get("properties", {}))


if __name__ == "__main__":
    unittest.main()
