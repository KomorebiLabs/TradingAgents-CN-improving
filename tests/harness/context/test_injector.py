"""Tests for ScreenerContextInjector."""
import pytest
from tradingagents.screener.models import SignalCard, SignalEvidence
from tradingagents.harness.context.injector import ScreenerContextInjector


def test_build_context_includes_ticker_and_score():
    card = SignalCard(
        ticker="600519.SH",
        raw_code="600519",
        exchange="SH",
        company_name="Kweichow Moutai",
        trade_date="2025-01-10",
        sector_tags=["Baijiu"],
        concept_tags=["Policy Leader", "capital_quality_high"],
        strategy_sources=["technical", "policy"],
        signal_breakdown=[],
        trigger_reason="policy_top_stock",
        initial_confidence=82.5,
        risk_flags=["trend_structure_extended"],
        screening_score=88.0,
    )
    injector = ScreenerContextInjector()
    ctx = injector.build_context(card)
    assert "600519.SH" in ctx
    assert "88.0" in ctx or "88." in ctx
    assert "trend_structure_extended" in ctx


def test_build_context_includes_technical_metrics():
    card = SignalCard(
        ticker="000001.SZ",
        raw_code="000001",
        exchange="SZ",
        company_name="Ping An Bank",
        trade_date="2025-01-10",
        sector_tags=["Banking"],
        concept_tags=["Valuation Recovery"],
        strategy_sources=["technical"],
        signal_breakdown=[
            SignalEvidence(
                strategy="technical",
                score=75.0,
                reason="",
                raw_metrics={"rsi": 65, "macd_signal": "golden_cross", "bollinger_position": 0.55},
            )
        ],
        trigger_reason="technical_breakout",
        initial_confidence=70.0,
        risk_flags=[],
        screening_score=75.0,
    )
    injector = ScreenerContextInjector()
    ctx = injector.build_context(card)
    assert "rsi" in ctx
    assert "65" in ctx
    assert "golden_cross" in ctx


def test_build_context_includes_capital_quality():
    card = SignalCard(
        ticker="300750.SZ",
        raw_code="300750",
        exchange="SZ",
        company_name="CATL",
        trade_date="2025-01-10",
        sector_tags=["New Energy"],
        concept_tags=["Power Battery"],
        strategy_sources=["smart_money"],
        signal_breakdown=[
            SignalEvidence(
                strategy="smart_money",
                score=80.0,
                reason="",
                raw_metrics={
                    "capital_quality_tag": "capital_quality_high",
                    "heat_quality_gap_score": 15,
                    "capital_quality_weight": 0.85,
                },
            )
        ],
        evidence_snapshot={"capital_quality_tag": "capital_quality_high"},
        trigger_reason="smart_money_signal",
        initial_confidence=78.0,
        risk_flags=[],
        screening_score=80.0,
    )
    injector = ScreenerContextInjector()
    ctx = injector.build_context(card)
    assert "Capital Quality" in ctx
    assert "capital_quality_high" in ctx
    assert "heat_quality_gap_score" in ctx


def test_build_context_empty_for_card_with_no_metrics():
    card = SignalCard(
        ticker="999999.SZ",
        raw_code="999999",
        exchange="SZ",
        company_name="Test Stock",
        trade_date="2025-01-10",
        sector_tags=[],
        concept_tags=[],
        strategy_sources=[],
        signal_breakdown=[],
        trigger_reason="test",
        initial_confidence=50.0,
        risk_flags=[],
        screening_score=50.0,
    )
    injector = ScreenerContextInjector()
    ctx = injector.build_context(card)
    assert "Screener Scan Results" in ctx
    assert "999999" in ctx


def test_extract_metrics_returns_empty_dict_when_no_match():
    card = SignalCard(
        ticker="000001.SZ",
        raw_code="000001",
        exchange="SZ",
        company_name="Ping An Bank",
        trade_date="2025-01-10",
        sector_tags=["Banking"],
        concept_tags=[],
        strategy_sources=["technical"],
        signal_breakdown=[
            SignalEvidence(strategy="technical", score=75.0, reason="", raw_metrics={"rsi": 65})
        ],
        trigger_reason="test",
        initial_confidence=70.0,
        risk_flags=[],
        screening_score=75.0,
    )
    injector = ScreenerContextInjector()
    metrics = injector._extract_metrics(card, "smart_money")
    assert metrics == {}
