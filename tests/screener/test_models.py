"""Tests for screener model schemas."""
import pytest
from tradingagents.screener.models import DeepAnalysisResult, SignalCard


def test_deep_analysis_result_has_token_usage_field():
    """Verify token_usage field exists with correct default."""
    card = SignalCard(
        ticker="600519.SH",
        raw_code="600519",
        exchange="SH",
        company_name="贵州茅台",
        trade_date="2025-01-10",
        sector_tags=["白酒"],
        concept_tags=["policy_top_stock"],
        strategy_sources=["technical"],
        signal_breakdown=[],
        trigger_reason="test",
        initial_confidence=75.0,
        risk_flags=[],
        screening_score=80.0,
    )
    result = DeepAnalysisResult(
        signal_card=card,
        success=True,
        elapsed_seconds=12.5,
    )
    assert result.token_usage == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def test_deep_analysis_result_token_usage_can_be_set():
    """Verify token_usage can be set after creation."""
    card = SignalCard(
        ticker="000001.SZ",
        raw_code="000001",
        exchange="SZ",
        company_name="平安银行",
        trade_date="2025-01-10",
        sector_tags=["银行"],
        concept_tags=["估值修复"],
        strategy_sources=["technical"],
        signal_breakdown=[],
        trigger_reason="test",
        initial_confidence=70.0,
        risk_flags=[],
        screening_score=75.0,
    )
    result = DeepAnalysisResult(
        signal_card=card,
        success=True,
        elapsed_seconds=15.0,
        token_usage={"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500},
    )
    assert result.token_usage["input_tokens"] == 1000
    assert result.token_usage["output_tokens"] == 500
    assert result.token_usage["total_tokens"] == 1500
