"""Merger golden fixtures (characterization tests).

Freezes the current observable behavior of `merge_signal_cards` so the
merger.py split (task A, refactor/merger-pipeline) can be verified as
behavior-preserving.  These tests MUST pass unchanged before the split
(against tradingagents.screener.merger) and after it (against the new
merger/ package).

Rules:
- No network, no LLM.
- Every assertion pins real observable output (scores, orders, reason
  strings, payload keys) — not implementation details.
- Do NOT "fix" anything found here; report suspicious logic instead.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from tradingagents.screener.merger import merge_signal_cards
from tradingagents.screener.models import SignalCard, SignalEvidence


# ---------------------------------------------------------------------------
# fixture helpers
# ---------------------------------------------------------------------------


def make_evidence(
    strategy: str,
    score: float,
    raw_metrics: Optional[Dict[str, Any]] = None,
    reason: str = "test-evidence",
) -> SignalEvidence:
    return SignalEvidence(
        strategy=strategy,  # type: ignore[arg-type]
        score=score,
        reason=reason,
        raw_metrics=dict(raw_metrics or {}),
    )


def make_card(
    ticker: str,
    *,
    score: float = 80.0,
    strategy_sources: Optional[List[str]] = None,
    concept_tags: Optional[List[str]] = None,
    sector_tags: Optional[List[str]] = None,
    risk_flags: Optional[List[str]] = None,
    data_source_verified: bool = True,
    company_name: str = "TestCo",
    evidence: Optional[List[SignalEvidence]] = None,
) -> SignalCard:
    return SignalCard(
        ticker=ticker,
        raw_code=ticker,
        exchange="SH",
        company_name=company_name,
        trade_date="2026-08-16",
        sector_tags=list(sector_tags or []),
        concept_tags=list(concept_tags or []),
        strategy_sources=list(strategy_sources or []),
        signal_breakdown=evidence or [make_evidence("technical", score)],
        trigger_reason="test",
        initial_confidence=70.0,
        risk_flags=list(risk_flags or []),
        screening_score=score,
        data_source_verified=data_source_verified,
    )


def summarize_retained(cards: List[SignalCard]) -> List[Dict[str, Any]]:
    """Normalized view of retained cards (rank, score, key snapshot fields)."""
    out = []
    for card in cards:
        snap = card.evidence_snapshot or {}
        out.append(
            {
                "ticker": card.ticker,
                "rank": card.screening_rank,
                "score": round(card.screening_score, 4),
                "confidence": round(card.initial_confidence, 4),
                "sources": sorted(card.strategy_sources),
                "semantic_decision": snap.get("semantic_decision"),
                "conflict_rule": snap.get("conflict_resolution_rule"),
                "conflict_bias": snap.get("conflict_priority_bias"),
                "semantic_priority": snap.get("semantic_priority"),
            }
        )
    return out


def summarize_dropped(dropped: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "ticker": d.get("ticker"),
            "reasons": sorted(d.get("reasons", [])),
            "funnel_stage": d.get("funnel_stage"),
            "stagea_reason_ref": d.get("stagea_reason_ref"),
        }
        for d in dropped
    ]


# ---------------------------------------------------------------------------
# 1. edge cases
# ---------------------------------------------------------------------------


def test_empty_input_returns_empty():
    retained, dropped = merge_signal_cards([])
    assert retained == []
    assert dropped == []


# ---------------------------------------------------------------------------
# 2. single card retention + snapshot shape
# ---------------------------------------------------------------------------


def test_single_card_retained_with_rank_and_snapshot():
    card = make_card("600001", score=85.0, strategy_sources=["technical"])
    retained, dropped = merge_signal_cards([card], mode="MVP")

    assert dropped == []
    assert [c.ticker for c in retained] == ["600001"]
    kept = retained[0]
    assert kept.screening_rank == 1
    # single card, no policy/capital tags, single-strategy aligned:
    # semantic_priority = -1 (no policy) + 2 (aligned bonus) + 1 (rule bias) = 2
    # semantic_bonus = 2*1.5 + 2*0.75 = 4.5 ->
    # screening_score = 85 + 0 (resonance) + 4.5 = 89.5 (characterized)
    assert kept.screening_score == pytest.approx(89.5)
    snap = kept.evidence_snapshot
    assert snap.get("semantic_decision") == "retained"
    assert snap.get("merged_from") == ["600001"]
    assert snap.get("source_scores") == {"600001": 85.0}
    # conflict machinery on a single card
    assert snap.get("conflict_resolution_rule") in {
        "aligned_multi_strategy_support",
        "balanced_composite",
    }
    assert "semantic_reason_payload" in snap
    assert "merger_threshold_snapshot" in snap


# ---------------------------------------------------------------------------
# 3. aggregation of same-ticker cards from multiple strategies
# ---------------------------------------------------------------------------


def test_multi_strategy_merge_resonance_and_sources():
    tech = make_evidence(
        "technical",
        70.0,
        {"structure_risk_score": 60.0, "trend_consistency_score": 60.0},
    )
    policy = make_evidence(
        "policy",
        90.0,
        {
            "stock_selection_tag": "policy_core_member",
            "primary_concept_score": 80.0,
            "concept_competition_score": 80.0,
            "multi_concept_overlap_count": 2,
        },
    )
    smart = make_evidence(
        "smart_money",
        85.0,
        {
            "capital_quality_tag": "capital_quality_high",
            "capital_quality_summary": "high-quality persistent capital flow",
            "heat_quality_gap_score": 10.0,
        },
    )
    card = make_card(
        "600519",
        score=80.0,
        strategy_sources=["technical", "policy", "smart_money"],
        concept_tags=["policy_core_member"],
        evidence=[tech, policy, smart],
    )
    retained, _ = merge_signal_cards([card], mode="MVP")
    assert len(retained) == 1
    merged = retained[0]
    assert sorted(merged.strategy_sources) == ["policy", "smart_money", "technical"]
    assert len(merged.signal_breakdown) == 3
    assert merged.screening_rank == 1
    # resonance_bonus = (3-1)*5 = 10 ; semantic_bonus = priority*1.5 + align*0.75
    # policy_strength=2 (core_member) -> +2; capital high -> +4; semantic bonus +3;
    # aligned cross-conflict bonus +2 -> priority = 11 -> bonus = 16.5
    # screening_score = min(100, 80 + 10 + 16.5) -> clamped at 100 (characterized)
    assert merged.screening_score == pytest.approx(
        min(100.0, 80.0 + 10.0 + merged.evidence_snapshot["semantic_priority"] * 1.5 + 0.75 * 0)
    )
    snap = merged.evidence_snapshot
    assert snap.get("policy_selection_tag") == "policy_core_member"
    assert snap.get("capital_quality_tag") == "capital_quality_high"
    assert "semantic_decision_summary" in snap
    assert "retained_priority" in snap["semantic_decision_summary"]


# ---------------------------------------------------------------------------
# 4. conflict tiers
# ---------------------------------------------------------------------------


def test_conflict_tier_aligned():
    tech = make_evidence("technical", 82.0, {"structure_risk_score": 60.0, "trend_consistency_score": 60.0})
    policy = make_evidence("policy", 85.0, {"stock_selection_tag": "policy_core_member"})
    card = make_card(
        "600001",
        score=83.0,
        strategy_sources=["technical", "policy"],
        concept_tags=["policy_core_member"],
        evidence=[tech, policy],
    )
    retained, _ = merge_signal_cards([card])
    snap = retained[0].evidence_snapshot
    assert snap["cross_strategy_conflict"]["tier"] == "aligned"
    assert snap["conflict_resolution_rule"] == "aligned_multi_strategy_support"
    assert snap["conflict_priority_bias"] == 1


def test_conflict_tier_severe():
    tech = make_evidence("technical", 40.0, {"structure_risk_score": 60.0, "trend_consistency_score": 60.0})
    policy = make_evidence("policy", 90.0, {"stock_selection_tag": "policy_top_stock"})
    card = make_card(
        "600002",
        score=65.0,
        strategy_sources=["technical", "policy"],
        concept_tags=["policy_top_stock"],
        evidence=[tech, policy],
    )
    retained, _ = merge_signal_cards([card])
    snap = retained[0].evidence_snapshot
    assert snap["cross_strategy_conflict"]["tier"] == "severe"
    assert snap["cross_strategy_conflict"]["spread"] == pytest.approx(50.0)
    assert snap["conflict_resolution_rule"] == "severe_conflict_penalty"
    assert snap["conflict_priority_bias"] == -2


# ---------------------------------------------------------------------------
# 5. conflict resolution rules (retained path)
# ---------------------------------------------------------------------------


def test_technical_veto_overrides_semantic():
    tech = make_evidence(
        "technical",
        70.0,
        {
            "structure_risk_score": 30.0,
            "trend_consistency_score": 40.0,
            "volume_price_divergence_score": 40.0,
            "volume_confirmation_score": 40.0,
            "breakout_quality_score": 40.0,
            "recent_extension_pct": 10.0,
            "volume_spike_ratio": 2.0,
            "close_above_ma20": False,
            "close_above_ma60": False,
        },
    )
    policy = make_evidence("policy", 90.0, {"stock_selection_tag": "policy_core_member"})
    smart = make_evidence(
        "smart_money",
        85.0,
        {"capital_quality_tag": "capital_quality_speculative", "heat_quality_gap_score": 30.0},
    )
    card = make_card(
        "600003",
        score=85.0,
        strategy_sources=["technical", "policy", "smart_money"],
        concept_tags=["policy_core_member"],
        evidence=[tech, policy, smart],
    )
    retained, dropped = merge_signal_cards([card])
    if retained:
        snap = retained[0].evidence_snapshot
        assert snap["conflict_resolution_rule"] == "technical_veto_overrides_semantic"
        assert snap["conflict_priority_bias"] == -4
    else:
        # dropped path must carry the veto reason
        assert "technical_veto" in dropped[0]["reasons"] or "conflict_policy_capital_vs_technical" in dropped[0]["reasons"]


def test_semantic_consensus_priority():
    tech = make_evidence("technical", 80.0, {"structure_risk_score": 70.0, "trend_consistency_score": 70.0})
    policy = make_evidence("policy", 88.0, {"stock_selection_tag": "policy_core_member"})
    smart = make_evidence(
        "smart_money",
        86.0,
        {"capital_quality_tag": "capital_quality_high", "heat_quality_gap_score": 5.0},
    )
    card = make_card(
        "600004",
        score=84.0,
        strategy_sources=["technical", "policy", "smart_money"],
        concept_tags=["policy_core_member"],
        evidence=[tech, policy, smart],
    )
    retained, _ = merge_signal_cards([card])
    snap = retained[0].evidence_snapshot
    assert snap["conflict_resolution_rule"] == "semantic_consensus_priority"
    assert snap["conflict_priority_bias"] == 3


def test_weak_policy_discount_under_technical_stress():
    tech = make_evidence(
        "technical",
        55.0,
        {
            "structure_risk_score": 30.0,
            "trend_consistency_score": 40.0,
            "volume_price_divergence_score": 40.0,
            "volume_confirmation_score": 40.0,
            "breakout_quality_score": 40.0,
            "recent_extension_pct": 10.0,
            "volume_spike_ratio": 2.0,
            "close_above_ma20": False,
            "close_above_ma60": False,
        },
    )
    policy = make_evidence("policy", 60.0, {"stock_selection_tag": "policy_keyword_fallback"})
    card = make_card(
        "600005",
        score=58.0,
        strategy_sources=["technical", "policy"],
        concept_tags=["policy_keyword_fallback"],
        evidence=[tech, policy],
    )
    retained, dropped = merge_signal_cards([card])
    if retained:
        snap = retained[0].evidence_snapshot
        assert snap["conflict_resolution_rule"] == "weak_policy_discount_under_technical_stress"
        assert snap["conflict_priority_bias"] == -3
    else:
        assert "weak_policy_under_technical_stress" in dropped[0]["reasons"]


# ---------------------------------------------------------------------------
# 6. hard filters
# ---------------------------------------------------------------------------


def test_st_and_negative_pe_dropped():
    st_card = make_card(
        "600010",
        score=90.0,
        strategy_sources=["technical"],
        company_name="ST Ruined",
        evidence=[make_evidence("technical", 90.0, {"pe_ttm": 25.0, "turnover_rate": 5.0, "float_market_cap_billion": 50.0})],
    )
    neg_pe_card = make_card(
        "600011",
        score=80.0,
        strategy_sources=["technical"],
        evidence=[make_evidence("technical", 80.0, {"pe_ttm": -3.0, "turnover_rate": 5.0, "float_market_cap_billion": 50.0, "change_pct": 1.0})],
    )
    retained, dropped = merge_signal_cards([st_card, neg_pe_card], mode="MVP")
    assert retained == []
    reasons_by_ticker = {d["ticker"]: sorted(d["reasons"]) for d in dropped}
    assert reasons_by_ticker["600010"] == ["st_flagged"]
    assert reasons_by_ticker["600011"] == ["negative_pe"]
    assert dropped[0]["funnel_stage"] == "stageb_hard_filter"


def test_liquidity_and_float_cap_dropped():
    low_turnover = make_card(
        "600020",
        score=80.0,
        strategy_sources=["technical"],
        evidence=[make_evidence("technical", 80.0, {"pe_ttm": 20.0, "turnover_rate": 1.0, "float_market_cap_billion": 60.0})],
    )
    low_cap = make_card(
        "600021",
        score=80.0,
        strategy_sources=["technical"],
        evidence=[make_evidence("technical", 80.0, {"pe_ttm": 20.0, "turnover_rate": 5.0, "float_market_cap_billion": 20.0})],
    )
    retained, dropped = merge_signal_cards([low_turnover, low_cap], mode="MVP")
    assert retained == []
    reasons_by_ticker = {d["ticker"]: sorted(d["reasons"]) for d in dropped}
    assert reasons_by_ticker["600020"] == ["low_turnover"]
    assert reasons_by_ticker["600021"] == ["low_float_market_cap"]


def test_near_limit_down_and_extreme_pe_dropped():
    limit_down = make_card(
        "600030",
        score=85.0,
        strategy_sources=["technical"],
        evidence=[make_evidence("technical", 85.0, {"pe_ttm": 20.0, "turnover_rate": 5.0, "float_market_cap_billion": 60.0, "change_pct": -10.5})],
    )
    extreme_pe = make_card(
        "600031",
        score=85.0,
        strategy_sources=["technical"],
        evidence=[make_evidence("technical", 85.0, {"pe_ttm": 500.0, "turnover_rate": 5.0, "float_market_cap_billion": 60.0})],
    )
    retained, dropped = merge_signal_cards([limit_down, extreme_pe], mode="MVP")
    assert retained == []
    reasons_by_ticker = {d["ticker"]: sorted(d["reasons"]) for d in dropped}
    assert reasons_by_ticker["600030"] == ["near_limit_down"]
    assert reasons_by_ticker["600031"] == ["extreme_pe"]


def test_speculative_capital_flow_dropped():
    tech = make_evidence("technical", 90.0, {"pe_ttm": 20.0, "turnover_rate": 8.0, "float_market_cap_billion": 60.0, "structure_risk_score": 60.0, "trend_consistency_score": 60.0})
    smart = make_evidence(
        "smart_money",
        88.0,
        {"capital_quality_tag": "capital_quality_speculative", "heat_quality_gap_score": 30.0},
    )
    card = make_card(
        "600040",
        score=75.0,
        strategy_sources=["technical", "smart_money"],
        concept_tags=[],
        evidence=[tech, smart],
    )
    retained, dropped = merge_signal_cards([card], mode="MVP")
    assert retained == []
    assert sorted(dropped[0]["reasons"]) == ["heat_quality_gap_exclusion", "speculative_capital_flow"]
    assert dropped[0]["funnel_stage"] == "stageb_hard_filter"


def test_technical_structure_risk_dropped():
    tech = make_evidence(
        "technical",
        70.0,
        {
            "pe_ttm": 20.0,
            "turnover_rate": 5.0,
            "float_market_cap_billion": 60.0,
            "structure_risk_score": 30.0,
            "trend_consistency_score": 40.0,
        },
    )
    card = make_card(
        "600050",
        score=75.0,
        strategy_sources=["technical"],
        evidence=[tech],
    )
    retained, dropped = merge_signal_cards([card], mode="MVP")
    assert retained == []
    assert "technical_structure_risk" in dropped[0]["reasons"]


# ---------------------------------------------------------------------------
# 7. ranking, diversification, output cap
# ---------------------------------------------------------------------------


def test_ranking_order_matches_sort_key():
    # higher semantic priority / policy strength must rank first
    top = make_card(
        "600100",
        score=85.0,
        strategy_sources=["policy"],
        concept_tags=["policy_top_stock"],
        evidence=[make_evidence("policy", 95.0, {"stock_selection_tag": "policy_top_stock"})],
    )
    plain = make_card(
        "600101",
        score=90.0,
        strategy_sources=["technical"],
        evidence=[make_evidence("technical", 90.0, {"structure_risk_score": 70.0, "trend_consistency_score": 70.0})],
    )
    retained, _ = merge_signal_cards([plain, top], mode="MVP")
    assert [c.ticker for c in retained] == ["600100", "600101"]
    assert [c.screening_rank for c in retained] == [1, 2]


def test_sector_diversification_limit_drops_third_same_sector():
    def same_sector_card(ticker: str, score: float) -> SignalCard:
        return make_card(
            ticker,
            score=score,
            strategy_sources=["technical"],
            sector_tags=["半导体"],
            evidence=[make_evidence("technical", score, {"structure_risk_score": 70.0, "trend_consistency_score": 70.0})],
        )

    cards = [same_sector_card("600200", 88.0), same_sector_card("600201", 87.0), same_sector_card("600202", 86.0)]
    retained, dropped = merge_signal_cards(cards, mode="MVP")
    assert [c.ticker for c in retained] == ["600200", "600201"]
    assert dropped[0]["ticker"] == "600202"
    assert dropped[0]["reasons"] == ["same_sector_limit"]
    assert dropped[0]["funnel_stage"] == "stageb_diversification"
    assert dropped[0]["stagea_reason_ref"] == "stagea_pass:600202"
    assert dropped[0]["sector"] == "半导体"


def test_max_output_cap_mvp_keeps_three():
    cards = [
        make_card(
            f"60030{i}",
            score=90.0 - i,
            strategy_sources=["technical"],
            sector_tags=[f"s{i}"],
            evidence=[make_evidence("technical", 90.0 - i, {"structure_risk_score": 70.0, "trend_consistency_score": 70.0})],
        )
        for i in range(4)
    ]
    retained, _ = merge_signal_cards(cards, mode="MVP")
    assert len(retained) == 3
    assert [c.screening_rank for c in retained] == [1, 2, 3]


# ---------------------------------------------------------------------------
# 8. dropped payload shape (funnel fields, semantic payload)
# ---------------------------------------------------------------------------


def test_dropped_payload_shape_complete():
    card = make_card(
        "600400",
        score=70.0,
        strategy_sources=["technical", "smart_money"],
        concept_tags=[],
        evidence=[
            make_evidence("technical", 70.0, {"pe_ttm": 20.0, "turnover_rate": 5.0, "float_market_cap_billion": 60.0, "structure_risk_score": 70.0, "trend_consistency_score": 70.0}),
            make_evidence("smart_money", 68.0, {"capital_quality_tag": "capital_quality_speculative", "heat_quality_gap_score": 30.0}),
        ],
    )
    _, dropped = merge_signal_cards([card], mode="MVP")
    assert len(dropped) == 1
    d = dropped[0]
    assert set(d.keys()) >= {
        "ticker",
        "company_name",
        "reasons",
        "funnel_stage",
        "stagea_reason_ref",
        "policy_selection_tag",
        "capital_quality_tag",
        "capital_quality_summary",
        "technical_structure_summary",
        "conflict_resolution",
        "conflict_resolution_rule",
        "conflict_priority_bias",
        "semantic_decision_summary",
        "semantic_reason_payload",
    }
    payload = d["semantic_reason_payload"]
    assert payload["decision"] == "dropped"
    assert set(payload.keys()) >= {
        "summary",
        "reasons",
        "semantic_priority",
        "policy",
        "capital",
        "technical",
        "cross_strategy_conflict",
        "conflict_resolution",
        "conflict_resolution_rule",
        "conflict_priority_bias",
        "funnel_stage",
        "stagea_reason_ref",
    }
    assert payload["funnel_stage"] == "stageb_hard_filter"
    assert d["stagea_reason_ref"] == "stagea_pass:600400"
    assert "dropped_reason" in d["semantic_decision_summary"]
