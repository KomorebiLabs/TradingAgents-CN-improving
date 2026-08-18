"""Legacy vs new memory implementation parity tests.

Both `StructuredMemory` / `FinancialSituationMemory` implementations are fed
identical inputs and must produce byte-identical outputs.  Equivalence
evidence for the memory.py split (refactor/merger-pipeline).

When memory_legacy.py is eventually deleted, delete this file too.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Tuple

from tradingagents.agents.utils.memory import FinancialSituationMemory as NewFSM
from tradingagents.agents.utils.memory import StructuredMemory as NewStructured
from tradingagents.agents.utils.memory_legacy import FinancialSituationMemory as LegacyFSM
from tradingagents.agents.utils.memory_legacy import StructuredMemory as LegacyStructured

# rank_bm25 availability shifts which get_memories branch runs; parity must
# hold on the SAME availability for both implementations (it does — same env).
try:  # pragma: no cover
    from rank_bm25 import BM25Okapi  # noqa: F401
    BM25_AVAILABLE = True
except Exception:  # pragma: no cover
    BM25_AVAILABLE = False


def sample_route_metadata() -> List[Dict[str, Any]]:
    return [
        {"segment": "cn_main_board_equity", "style_bucket": "growth_style_candidate", "final_route": "direct", "route_category": "normal", "compression_triggered": False, "compression_rate": 0.0, "trade_date": "2026-08-10", "decision_quality": "good", "bottleneck_stages": [], "skills": ["technical"]},
        {"segment": "cn_main_board_equity", "style_bucket": "growth_style_candidate", "final_route": "compression_handoff", "route_category": "mixed", "compression_triggered": True, "compression_rate": 0.4, "trade_date": "2026-08-11", "decision_quality": "good", "bottleneck_stages": ["research_phase"], "skills": ["valuation"]},
        {"segment": "cn_star", "style_bucket": "momentum_style_candidate", "final_route": "direct", "route_category": "normal", "compression_triggered": False, "compression_rate": 0.0, "trade_date": "2026-08-12", "decision_quality": "poor", "bottleneck_stages": [], "skills": ["technical"]},
        {"segment": "cn_chinext", "style_bucket": "value_style_candidate", "final_route": "compression_handoff", "route_category": "complex", "compression_triggered": True, "compression_rate": 0.7, "trade_date": "2026-08-13", "decision_quality": "neutral", "bottleneck_stages": ["research_phase", "risk_phase"], "skills": ["macro"]},
        {"segment": "cn_main_board_equity", "style_bucket": "growth_style_candidate", "final_route": "portfolio_handoff", "route_category": "mixed", "compression_triggered": True, "compression_rate": 0.3, "trade_date": "2026-08-14", "decision_quality": "good", "bottleneck_stages": [], "skills": ["technical"]},
    ]


def sample_situations() -> List[Tuple[str, str]]:
    return [
        ("High inflation with rising rates and declining consumer spending", "Defensive sectors and duration review"),
        ("Tech sector high volatility with institutional selling", "Reduce high-growth tech, seek value"),
        ("Strong dollar affecting emerging markets with forex volatility", "Hedge currency exposure"),
        ("Sector rotation with rising yields", "Rebalance to target allocations"),
        ("Growth stock momentum with policy tailwind", "Momentum-following long bias"),
    ]


def build_pair() -> Tuple[LegacyStructured, NewStructured]:
    legacy = LegacyStructured("legacy", {})
    new = NewStructured("new", {})
    meta = copy.deepcopy(sample_route_metadata())
    legacy.add_situations(copy.deepcopy(sample_situations()), copy.deepcopy(meta))
    new.add_situations(copy.deepcopy(sample_situations()), copy.deepcopy(meta))
    return legacy, new


# ---------------------------------------------------------------------------
# storage / export
# ---------------------------------------------------------------------------


def test_parity_export_after_add():
    legacy, new = build_pair()
    assert legacy.export_memories() == new.export_memories()


def test_parity_import_roundtrip_and_clear():
    memories = [
        {"situation": s, "recommendation": r, "metadata": m}
        for (s, r), m in zip(sample_situations(), sample_route_metadata())
    ]
    legacy, new = LegacyStructured("l", {}), NewStructured("n", {})
    legacy.import_memories(copy.deepcopy(memories))
    new.import_memories(copy.deepcopy(memories))
    assert legacy.export_memories() == new.export_memories()
    legacy.clear()
    new.clear()
    assert legacy.export_memories() == new.export_memories() == []


# ---------------------------------------------------------------------------
# retrieval
# ---------------------------------------------------------------------------


def test_parity_get_memories_no_filter():
    legacy, new = build_pair()
    assert legacy.get_memories("tech momentum valuation", n_matches=3) == new.get_memories("tech momentum valuation", n_matches=3)


def test_parity_get_memories_exact_filter():
    legacy, new = build_pair()
    args = {"current_situation": "inflation rates consumer", "n_matches": 2, "filters": {"segment": "cn_main_board_equity"}}
    assert legacy.get_memories(**copy.deepcopy(args)) == new.get_memories(**copy.deepcopy(args))


def test_parity_get_memories_list_or_filter():
    legacy, new = build_pair()
    args = {"current_situation": "sector rotation yields", "n_matches": 5, "filters": {"segment": ["cn_star", "cn_chinext"]}}
    assert legacy.get_memories(**copy.deepcopy(args)) == new.get_memories(**copy.deepcopy(args))


def test_parity_get_memories_range_filters():
    legacy, new = build_pair()
    args = {"current_situation": "route analysis", "n_matches": 5, "filters": {"compression_rate_min": 0.3, "compression_rate_max": 0.8}}
    assert legacy.get_memories(**copy.deepcopy(args)) == new.get_memories(**copy.deepcopy(args))


def test_parity_get_memories_date_filter():
    legacy, new = build_pair()
    args = {"current_situation": "market", "n_matches": 5, "filters": {"trade_date_after": "2026-08-12"}}
    assert legacy.get_memories(**copy.deepcopy(args)) == new.get_memories(**copy.deepcopy(args))


def test_parity_get_memories_list_contains_filter():
    legacy, new = build_pair()
    args = {"current_situation": "market", "n_matches": 5, "filters": {"skills": "technical"}}
    assert legacy.get_memories(**copy.deepcopy(args)) == new.get_memories(**copy.deepcopy(args))


def test_parity_get_memories_no_metadata_flag():
    legacy, new = build_pair()
    a = legacy.get_memories("market", n_matches=2, include_metadata=False)
    b = new.get_memories("market", n_matches=2, include_metadata=False)
    assert a == b


def test_parity_get_memories_empty():
    assert LegacyStructured("l", {}).get_memories("x") == NewStructured("n", {}).get_memories("x") == []


def test_parity_field_and_segment_and_route_lookups():
    legacy, new = build_pair()
    assert legacy.get_memories_by_field("final_route", "direct") == new.get_memories_by_field("final_route", "direct")
    assert legacy.get_all_by_segment("cn_star") == new.get_all_by_segment("cn_star")
    assert legacy.get_all_by_route("compression_handoff") == new.get_all_by_route("compression_handoff")


def test_parity_recent_and_high_performing():
    legacy, new = build_pair()
    assert legacy.get_recent_memories(2) == new.get_recent_memories(2)
    assert legacy.get_recent_memories(3, segment="cn_main_board_equity") == new.get_recent_memories(3, segment="cn_main_board_equity")
    assert legacy.get_high_performing_routes() == new.get_high_performing_routes()
    assert legacy.get_high_performing_routes(min_quality="neutral", segment="cn_star") == new.get_high_performing_routes(min_quality="neutral", segment="cn_star")


def test_parity_filter_predicates_and_candidates():
    legacy, new = build_pair()
    for f in ({"segment": "cn_star"}, {"segment": ["cn_star", "cn_chinext"]}, {"compression_rate_max": 0.5}, {"trade_date_after": "2026-08-11"}, {"skills": "technical"}):
        assert legacy._match_filters(legacy.metadata[0], f) == new._match_filters(new.metadata[0], f)
        assert legacy._get_candidates_from_indexes(f) == new._get_candidates_from_indexes(f)


def test_parity_structured_index_internal():
    legacy, new = build_pair()
    assert legacy._structured_index == new._structured_index


# ---------------------------------------------------------------------------
# analytics
# ---------------------------------------------------------------------------


def test_parity_analytics_all():
    legacy, new = build_pair()
    assert legacy.get_route_statistics() == new.get_route_statistics()
    assert legacy.get_route_statistics_by_segment() == new.get_route_statistics_by_segment()
    assert legacy.get_route_statistics_by_segment(segment="cn_main_board_equity") == new.get_route_statistics_by_segment(segment="cn_main_board_equity")
    for pt in ("compression_handoff", "direct", "high_compression", "low_compression", "unknown"):
        assert legacy.get_pattern_outcome_correlation(pt) == new.get_pattern_outcome_correlation(pt)
    assert legacy.get_route_efficiency_trends() == new.get_route_efficiency_trends()
    assert legacy.get_route_efficiency_trends(segment="cn_main_board_equity") == new.get_route_efficiency_trends(segment="cn_main_board_equity")
    assert legacy.get_route_efficiency_trends(date_range=("2026-08-11", "2026-08-14")) == new.get_route_efficiency_trends(date_range=("2026-08-11", "2026-08-14"))


def test_parity_analytics_empty():
    assert LegacyStructured("l", {}).get_route_statistics() == NewStructured("n", {}).get_route_statistics()
    assert LegacyStructured("l", {}).get_route_efficiency_trends() == NewStructured("n", {}).get_route_efficiency_trends()


# ---------------------------------------------------------------------------
# FinancialSituationMemory
# ---------------------------------------------------------------------------


def test_parity_fsm_add_and_get():
    legacy = LegacyFSM("l")
    new = NewFSM("n")
    legacy.add_situations(copy.deepcopy(sample_situations()))
    new.add_situations(copy.deepcopy(sample_situations()))
    assert legacy.get_memories("tech volatility selling", n_matches=2) == new.get_memories("tech volatility selling", n_matches=2)
    assert legacy.get_memories("nonexistent query zzz", n_matches=2) == new.get_memories("nonexistent query zzz", n_matches=2)


def test_parity_fsm_clear_and_empty():
    legacy, new = LegacyFSM("l"), NewFSM("n")
    assert legacy.get_memories("x") == new.get_memories("x") == []
    legacy.clear()
    new.clear()
    assert legacy.get_memories("x") == new.get_memories("x")
