"""Integration tests for historical context injection (P4 Memory)."""
import json
import tempfile
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest


class TestReflectorConclusionSummary:
    """Test Reflector.generate_conclusion_summary()."""

    def _make_mock_state(
        self,
        ticker="300750",
        trade_date="2026-05-20",
        final_decision="买入",
        judge_decision="看多，政策驱动，建议买入",
        risk_judge="风险可控，回报可期",
        bull_history="看好新能源赛道，政策支持强劲",
        signal_card=None,
    ):
        """Build a minimal mock AgentState for testing."""
        if signal_card is None:
            signal_card = {
                "policy_signal_score": 0.82,
                "technical_signal_score": 0.75,
                "smart_money_signal_score": 0.68,
            }
        return {
            "company_of_interest": ticker,
            "trade_date": trade_date,
            "decision_blocks": {
                "investment_plan": "看好政策驱动型股票",
                "trader_plan": "逢低买入，止损设在95%",
                "final_trade_decision": final_decision,
            },
            "investment_debate_state": {
                "judge_decision": judge_decision,
                "bull_history": bull_history,
                "bear_history": "看空：估值过高",
            },
            "risk_debate_state": {
                "judge_decision": risk_judge,
            },
            "screener_context": {
                "route_decision": {
                    "signal_card": signal_card,
                },
            },
        }

    def test_extracts_ticker_and_trade_date(self):
        from tradingagents.graph.reflection import Reflector

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="政策驱动，看多")

        reflector = Reflector(mock_llm)
        state = self._make_mock_state(ticker="600519", trade_date="2026-05-18")

        result = reflector.generate_conclusion_summary(state)

        assert result["ticker"] == "600519"
        assert result["trade_date"] == "2026-05-18"

    def test_confidence_high_for_buy_decision(self):
        from tradingagents.graph.reflection import Reflector

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="建议买入")

        reflector = Reflector(mock_llm)
        state = self._make_mock_state(final_decision="强烈建议买入")

        result = reflector.generate_conclusion_summary(state)
        assert result["confidence"] == "高"

    def test_confidence_low_for_sell_decision(self):
        from tradingagents.graph.reflection import Reflector

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="不建议操作")

        reflector = Reflector(mock_llm)
        state = self._make_mock_state(final_decision="建议卖出，控制风险")

        result = reflector.generate_conclusion_summary(state)
        assert result["confidence"] == "低"

    def test_confidence_medium_by_default(self):
        from tradingagents.graph.reflection import Reflector

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="观望")

        reflector = Reflector(mock_llm)
        state = self._make_mock_state(final_decision="暂无明确方向")

        result = reflector.generate_conclusion_summary(state)
        assert result["confidence"] == "中"

    def test_dimensions_extracted_from_signal_card(self):
        from tradingagents.graph.reflection import Reflector

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="技术突破")

        reflector = Reflector(mock_llm)
        state = self._make_mock_state(
            signal_card={
                "policy_signal_score": 0.90,
                "technical_signal_score": 0.60,
                "smart_money_signal_score": 0.70,
            }
        )

        result = reflector.generate_conclusion_summary(state)
        assert result["dimensions"]["policy"] == 0.90
        assert result["dimensions"]["technical"] == 0.60
        assert result["dimensions"]["smart_money"] == 0.70

    def test_llm_called_for_summary(self):
        from tradingagents.graph.reflection import Reflector

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="政策+技术双驱动")

        reflector = Reflector(mock_llm)
        state = self._make_mock_state()

        result = reflector.generate_conclusion_summary(state)

        mock_llm.invoke.assert_called_once()
        call_arg = mock_llm.invoke.call_args[0][0]
        assert isinstance(call_arg, list)
        assert call_arg[0]["role"] == "user"
        assert "300750" in call_arg[0]["content"]

    def test_llm_failure_falls_back_to_template(self):
        from tradingagents.graph.reflection import Reflector

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("LLM unavailable")

        reflector = Reflector(mock_llm)
        state = self._make_mock_state(final_decision="买入")

        result = reflector.generate_conclusion_summary(state)

        assert "买入" in result["summary"]
        assert result["ticker"] == "300750"

    def test_key_reasons_from_bull_and_judge(self):
        from tradingagents.graph.reflection import Reflector

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="ok")

        reflector = Reflector(mock_llm)
        state = self._make_mock_state()

        result = reflector.generate_conclusion_summary(state)
        assert len(result["key_reasons"]) >= 1
        assert any("看好新能源赛道" in r for r in result["key_reasons"])

    def test_risks_from_risk_judge(self):
        from tradingagents.graph.reflection import Reflector

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="ok")

        reflector = Reflector(mock_llm)
        # risk_judge must be > 10 chars to pass the len() gate
        state = self._make_mock_state(risk_judge="风险可控，回报可期，建议适度配置仓位")

        result = reflector.generate_conclusion_summary(state)
        assert len(result["risks"]) >= 1

    def test_returns_complete_dict_structure(self):
        from tradingagents.graph.reflection import Reflector

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="分析完成")

        reflector = Reflector(mock_llm)
        state = self._make_mock_state()

        result = reflector.generate_conclusion_summary(state)

        assert set(result.keys()) == {
            "ticker",
            "trade_date",
            "summary",
            "dimensions",
            "final_decision",
            "confidence",
            "key_reasons",
            "risks",
        }


class TestEndToEndMemoryFlow:
    """Test the full save→load→inject flow."""

    def test_save_and_load_integration(self, tmp_path):
        from tradingagents.agents.utils.memory_manager import (
            save_conclusion_summary,
            load_historical_conclusion,
        )

        ticker = "TEST_TICKER"
        trade_date = (date.today() - timedelta(days=2)).isoformat()
        summary = {
            "ticker": ticker,
            "trade_date": trade_date,
            "summary": "政策驱动，看多",
            "dimensions": {"policy": 0.82, "technical": 0.75, "smart_money": 0.68},
            "final_decision": "买入",
            "confidence": "高",
            "key_reasons": ["政策支持"],
            "risks": [],
        }

        save_conclusion_summary(ticker, trade_date, summary, memory_dir=tmp_path)
        loaded = load_historical_conclusion(ticker, memory_dir=tmp_path)

        assert loaded is not None
        assert loaded["summary"] == "政策驱动，看多"
        assert loaded["confidence"] == "高"
        assert loaded["dimensions"]["policy"] == 0.82

    def test_summary_json_roundtrip_via_reflector(self, tmp_path):
        from tradingagents.graph.reflection import Reflector
        from tradingagents.agents.utils.memory_manager import (
            save_conclusion_summary,
            load_historical_conclusion,
        )

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="技术突破，量价齐升")

        reflector = Reflector(mock_llm)
        state = {
            "company_of_interest": "TECH_STOCK",
            "trade_date": "2026-05-15",
            "decision_blocks": {
                "investment_plan": "技术突破型股票",
                "trader_plan": "追涨入场",
                "final_trade_decision": "买入",
            },
            "investment_debate_state": {
                "judge_decision": "技术面强劲",
                "bull_history": "量价齐升",
                "bear_history": "",
            },
            "risk_debate_state": {
                "judge_decision": "风险可控",
            },
            "screener_context": {
                "route_decision": {
                    "signal_card": {
                        "policy_signal_score": 0.5,
                        "technical_signal_score": 0.9,
                        "smart_money_signal_score": 0.6,
                    },
                },
            },
        }

        summary = reflector.generate_conclusion_summary(state)
        # Use a trade_date within the 7-day TTL (DEFAULT_TTL_DAYS)
        recent_trade_date = (date.today() - timedelta(days=5)).isoformat()
        save_conclusion_summary("TECH_STOCK", recent_trade_date, summary, memory_dir=tmp_path)
        loaded = load_historical_conclusion("TECH_STOCK", memory_dir=tmp_path)

        assert loaded is not None
        assert loaded["ticker"] == "TECH_STOCK"
        assert loaded["dimensions"]["technical"] == 0.9
        assert loaded["confidence"] == "高"
