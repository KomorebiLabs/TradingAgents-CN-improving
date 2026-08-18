"""Legacy vs new merger implementation parity tests.

Both implementations are fed identical (deep-copied) inputs and must produce
byte-identical outputs.  This is the strongest equivalence evidence for the
merger.py split (refactor/merger-pipeline).

NOTE: `_should_drop_card` mutates card.risk_flags (appends "pe_unavailable"),
so every run uses fresh deep copies of the factory output.

When merger_legacy.py is eventually deleted, delete this file too.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from tradingagents.screener.merger import merge_signal_cards as new_merge
from tradingagents.screener.merger_legacy import merge_signal_cards as legacy_merge
from tradingagents.screener.models import SignalCard, SignalEvidence


def make_evidence(strategy: str, score: float, raw_metrics: Dict[str, Any]) -> SignalEvidence:
    return SignalEvidence(strategy=strategy, score=score, reason="parity", raw_metrics=dict(raw_metrics))


def make_card(
    ticker: str,
    score: float,
    strategy_sources: List[str],
    evidence: List[SignalEvidence],
    *,
    concept_tags: List[str] | None = None,
    sector_tags: List[str] | None = None,
    company_name: str = "TestCo",
) -> SignalCard:
    return SignalCard(
        ticker=ticker,
        raw_code=ticker,
        exchange="SH",
        company_name=company_name,
        trade_date="2026-08-16",
        sector_tags=list(sector_tags or []),
        concept_tags=list(concept_tags or []),
        strategy_sources=list(strategy_sources),
        signal_breakdown=evidence,
        trigger_reason="test",
        initial_confidence=70.0,
        risk_flags=[],
        screening_score=score,
        data_source_verified=True,
    )


def assert_parity(factory: Callable[[], List[SignalCard]], mode: str = "MVP", config: Dict[str, Any] | None = None) -> None:
    legacy_cards = [c.model_copy(deep=True) for c in factory()]
    new_cards = [c.model_copy(deep=True) for c in factory()]
    legacy_retained, legacy_dropped = legacy_merge(legacy_cards, mode=mode, config=config)
    new_retained, new_dropped = new_merge(new_cards, mode=mode, config=config)
    assert [c.model_dump() for c in legacy_retained] == [c.model_dump() for c in new_retained]
    assert legacy_dropped == new_dropped


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------


def test_parity_empty_input():
    assert_parity(lambda: [])


def test_parity_single_card():
    def factory():
        return [
            make_card(
                "600001",
                85.0,
                ["technical"],
                [make_evidence("technical", 85.0, {"pe_ttm": 20.0, "turnover_rate": 5.0, "float_market_cap_billion": 60.0})],
            )
        ]

    assert_parity(factory)


def test_parity_multi_strategy_merge():
    def factory():
        return [
            make_card(
                "600519",
                80.0,
                ["technical", "policy", "smart_money"],
                [
                    make_evidence("technical", 70.0, {"structure_risk_score": 60.0, "trend_consistency_score": 60.0, "pe_ttm": 20.0, "turnover_rate": 5.0, "float_market_cap_billion": 60.0}),
                    make_evidence("policy", 90.0, {"stock_selection_tag": "policy_top_stock", "primary_concept_score": 80.0, "concept_competition_score": 80.0, "multi_concept_overlap_count": 2}),
                    make_evidence("smart_money", 85.0, {"capital_quality_tag": "capital_quality_high", "capital_quality_summary": "high-quality persistent capital flow", "heat_quality_gap_score": 5.0}),
                ],
                concept_tags=["policy_top_stock"],
            )
        ]

    assert_parity(factory)


def test_parity_severe_conflict_and_veto():
    def factory():
        return [
            make_card(
                "600003",
                85.0,
                ["technical", "policy", "smart_money"],
                [
                    make_evidence("technical", 40.0, {"structure_risk_score": 30.0, "trend_consistency_score": 40.0, "volume_price_divergence_score": 40.0, "volume_confirmation_score": 40.0, "breakout_quality_score": 40.0, "recent_extension_pct": 10.0, "volume_spike_ratio": 2.0, "close_above_ma20": False, "close_above_ma60": False, "pe_ttm": 20.0, "turnover_rate": 5.0, "float_market_cap_billion": 60.0}),
                    make_evidence("policy", 90.0, {"stock_selection_tag": "policy_core_member"}),
                    make_evidence("smart_money", 85.0, {"capital_quality_tag": "capital_quality_speculative", "heat_quality_gap_score": 30.0}),
                ],
                concept_tags=["policy_core_member"],
            )
        ]

    assert_parity(factory)


def test_parity_hard_filters_mixed():
    def factory():
        return [
            make_card("600010", 90.0, ["technical"], [make_evidence("technical", 90.0, {"pe_ttm": 25.0, "turnover_rate": 5.0, "float_market_cap_billion": 50.0})], company_name="ST Broken"),
            make_card("600011", 80.0, ["technical"], [make_evidence("technical", 80.0, {"pe_ttm": -3.0, "turnover_rate": 5.0, "float_market_cap_billion": 50.0, "change_pct": 1.0})]),
            make_card("600012", 80.0, ["technical"], [make_evidence("technical", 80.0, {"pe_ttm": 20.0, "turnover_rate": 0.5, "float_market_cap_billion": 60.0})]),
            make_card("600013", 80.0, ["technical"], [make_evidence("technical", 80.0, {"pe_ttm": 20.0, "turnover_rate": 5.0, "float_market_cap_billion": 15.0})]),
            make_card("600014", 80.0, ["technical"], [make_evidence("technical", 80.0, {"pe_ttm": 500.0, "turnover_rate": 5.0, "float_market_cap_billion": 60.0})]),
            make_card("600015", 80.0, ["technical"], [make_evidence("technical", 80.0, {"pe_ttm": 20.0, "turnover_rate": 5.0, "float_market_cap_billion": 60.0, "change_pct": -10.0})]),
        ]

    assert_parity(factory)


def test_parity_sector_diversification():
    def factory():
        cards = []
        for i in range(3):
            cards.append(
                make_card(
                    f"60020{i}",
                    88.0 - i,
                    ["technical"],
                    [make_evidence("technical", 88.0 - i, {"structure_risk_score": 70.0, "trend_consistency_score": 70.0, "pe_ttm": 20.0, "turnover_rate": 5.0, "float_market_cap_billion": 60.0})],
                    sector_tags=["半导体"],
                )
            )
        return cards

    assert_parity(factory)


def test_parity_output_cap_and_ranking():
    def factory():
        cards = []
        for i in range(5):
            cards.append(
                make_card(
                    f"60030{i}",
                    90.0 - i,
                    ["technical"],
                    [make_evidence("technical", 90.0 - i, {"structure_risk_score": 70.0, "trend_consistency_score": 70.0, "pe_ttm": 20.0, "turnover_rate": 5.0, "float_market_cap_billion": 60.0})],
                    sector_tags=[f"s{i}"],
                )
            )
        return cards

    assert_parity(factory)


def test_parity_custom_config_overrides():
    def factory():
        return [
            make_card(
                "600001",
                85.0,
                ["technical"],
                [make_evidence("technical", 85.0, {"pe_ttm": 20.0, "turnover_rate": 5.0, "float_market_cap_billion": 60.0})],
            )
        ]

    config = {
        "thresholds": {"low_turnover_rate": 8.0, "extreme_pe_upper": 60.0},
        "conflict_priority": {"aligned_spread_max": 3.0, "aligned_support_bias": 5},
        "candidates": {"same_sector_limit": 1, "max_output": 2},
    }
    assert_parity(factory, mode="EXTENDED", config=config)
