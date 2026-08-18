"""Semantic priority scoring & retained/dropped decision summaries
(split from merger.py — refactor/merger-pipeline).

Depends on conflicts + selectors + constants (no dependency on explanations).
"""

from typing import Any, Dict, List

from tradingagents.screener.models import SignalCard

from .conflicts import (
    _capital_quality_severity,
    _cross_strategy_conflict,
    _pick_technical_structure_summary,
    _policy_semantic_bonus,
    _policy_strength,
    _resolve_conflict_rule,
    _technical_structure_penalty,
    _technical_structure_severity,
)
from .constants import DEFAULT_CONFLICT_PRIORITY
from .selectors import (
    _find_signal_metrics,
    _pick_capital_quality_summary,
    _pick_capital_quality_tag,
    _pick_policy_selection_tag,
)


def _semantic_priority(card: SignalCard, conflict_priority: Dict[str, Any] | None = None) -> int:
    cp = {**DEFAULT_CONFLICT_PRIORITY, **(conflict_priority or {})}
    policy_strength = _policy_strength(card)
    capital_tag = _pick_capital_quality_tag(card)
    technical_penalty = _technical_structure_penalty(card)
    conflict_penalty = _technical_structure_severity(card)
    cross_conflict = _cross_strategy_conflict(card, cp)
    conflict_rule = _resolve_conflict_rule(card, cp)

    score = 0
    if policy_strength == 3:
        score += 4
    elif policy_strength == 2:
        score += 2
    elif policy_strength == 1:
        score += 1
    else:
        score -= 1
    score += _policy_semantic_bonus(card)

    if capital_tag == "capital_quality_high":
        score += 4
    elif capital_tag == "capital_quality_persistent":
        score += 2
    elif capital_tag == "capital_quality_mixed":
        score += 0
    elif capital_tag == "capital_quality_speculative":
        score -= 4

    score -= technical_penalty
    if policy_strength >= 2 and conflict_penalty >= int(cp["technical_veto_min_severity"]):
        score -= 2
    if policy_strength == 0 and conflict_penalty >= int(cp["weak_policy_stress_min_severity"]):
        score -= 2
    if _capital_quality_severity(card) >= 2 and conflict_penalty >= int(cp["speculative_technical_min_severity"]):
        score -= 1
    score += int(cross_conflict["alignment_bonus"])
    score -= int(cross_conflict["conflict_penalty"])
    score += int(conflict_rule["bias"])
    return score


def _build_retained_semantic_summary(card: SignalCard, conflict_priority: Dict[str, Any] | None = None) -> str:
    cp = {**DEFAULT_CONFLICT_PRIORITY, **(conflict_priority or {})}
    policy_tag = _pick_policy_selection_tag(card)
    capital_tag = _pick_capital_quality_tag(card)
    parts: List[str] = []
    policy_strength = _policy_strength(card)
    technical_severity = _technical_structure_severity(card)
    cross_conflict = _cross_strategy_conflict(card, cp)
    conflict_rule = _resolve_conflict_rule(card, cp)
    policy_metrics = _find_signal_metrics(card, "policy")
    smart_metrics = _find_signal_metrics(card, "smart_money")

    if policy_tag == "policy_top_stock":
        parts.append("retained_priority: concept top-stock gained priority")
    elif policy_tag == "policy_core_member":
        parts.append("retained_priority: concept core member kept as strong board constituent")
    elif policy_tag == "policy_cross_hit_candidate":
        parts.append("retained_priority: concept cross-hit candidate remained eligible")

    if capital_tag == "capital_quality_high":
        parts.append("retained_priority: high-quality persistent capital flow")
    elif capital_tag == "capital_quality_persistent":
        parts.append("retained_priority: persistent multi-day capital flow")
    elif capital_tag == "capital_quality_mixed":
        parts.append("retained_priority: mixed capital quality, retained on composite score")
    elif capital_tag == "capital_quality_speculative" and _semantic_priority(card) >= 1:
        parts.append("retained_priority: speculative capital retained only because other semantics outranked the risk")
    if policy_metrics:
        parts.append(
            "policy_competition: "
            f"primary={policy_metrics.get('primary_concept_score', 'N/A')} | "
            f"competition={policy_metrics.get('concept_competition_score', 'N/A')} | "
            f"overlap={policy_metrics.get('multi_concept_overlap_count', 'N/A')}"
        )
    if smart_metrics:
        parts.append(
            "capital_quality_detail: "
            f"heat_gap={smart_metrics.get('heat_quality_gap_score', 'N/A')} | "
            f"tag={smart_metrics.get('capital_quality_tag', 'N/A')}"
        )

    technical_summary = _pick_technical_structure_summary(card)
    if technical_summary != "no explicit technical structure summary":
        parts.append(technical_summary)
    if cross_conflict["tier"] != "none":
        parts.append(
            "cross_strategy_conflict: "
            f"tier={cross_conflict['tier']} | spread={cross_conflict['spread']} | "
            f"dominant={cross_conflict['dominant_strategy']} | weakest={cross_conflict['weakest_strategy']}"
        )
    if policy_strength >= 2 and technical_severity >= 4:
        parts.append("conflict_rule: strong policy/strong structure conflict resolved by technical downgrade")
    elif policy_strength == 0 and technical_severity >= 3:
        parts.append("conflict_rule: weak policy could not fully offset technical risk")
    if conflict_rule["rule"] != "balanced_composite":
        parts.append(
            f"conflict_priority: rule={conflict_rule['rule']} | bias={conflict_rule['bias']} | resolution={conflict_rule['resolution']}"
        )

    if not parts:
        parts.append("retained_priority: composite score and diversification passed")
    parts.append(f"capital_quality_summary: {_pick_capital_quality_summary(card)}")
    return "; ".join(parts)


def _build_dropped_semantic_summary(
    card: SignalCard | None = None,
    reasons: List[str] | None = None,
    policy_tag: str = "",
    capital_tag: str = "",
    conflict_priority: Dict[str, Any] | None = None,
) -> str:
    cp = {**DEFAULT_CONFLICT_PRIORITY, **(conflict_priority or {})}
    reasons = reasons or []
    policy_tag = policy_tag or (_pick_policy_selection_tag(card) if card is not None else "")
    capital_tag = capital_tag or (_pick_capital_quality_tag(card) if card is not None else "")
    policy_strength = _policy_strength(card) if card is not None else 0
    technical_severity = _technical_structure_severity(card) if card is not None else 0
    cross_conflict = _cross_strategy_conflict(card, cp) if card is not None else {"tier": "none"}
    conflict_rule = _resolve_conflict_rule(card, cp) if card is not None else {"rule": "balanced_composite", "bias": 0, "resolution": "none"}

    readable: List[str] = []
    if "speculative_capital_flow" in reasons:
        readable.append("dropped_reason: speculative_flow_dominant triggered exclusion")
    if "heat_quality_gap_exclusion" in reasons:
        readable.append("dropped_reason: heat outran quality and continuity")
    if "low_semantic_conviction" in reasons:
        readable.append("dropped_reason: low semantic conviction under keyword fallback")
    if "same_sector_limit" in reasons and policy_tag == "policy_core_member":
        readable.append("dropped_reason: concept core member lost to stronger same-board candidate")
    elif "same_sector_limit" in reasons and policy_tag == "policy_keyword_fallback":
        readable.append("dropped_reason: weaker concept fallback candidate removed by diversification")
    elif "same_sector_limit" in reasons:
        readable.append("dropped_reason: diversification limit reached")
    if "st_flagged" in reasons:
        readable.append("dropped_reason: ST risk hard filter")
    if "near_limit_down" in reasons:
        readable.append("dropped_reason: near limit-down hard filter")
    if "low_turnover" in reasons:
        readable.append("dropped_reason: liquidity below turnover threshold")
    if "low_float_market_cap" in reasons:
        readable.append("dropped_reason: float market cap below threshold")
    if "negative_pe" in reasons or "extreme_pe" in reasons:
        readable.append("dropped_reason: valuation hard filter")
    if capital_tag == "capital_quality_speculative" and "speculative_capital_flow" not in reasons:
        readable.append("dropped_reason: high-heat low-quality capital profile")
    technical_summary = _pick_technical_structure_summary(card) if card is not None else ""
    if "technical_structure_risk" in reasons:
        readable.append("dropped_reason: weak technical structure risk")
        if "conflict_policy_capital_vs_technical" in reasons:
            readable.append("dropped_reason: strong semantic conflict resolved against weak structure")
    elif "conflict_policy_capital_vs_technical" in reasons:
        readable.append("dropped_reason: strong semantic conflict resolved against weak structure")
    elif technical_summary and technical_summary != "no explicit technical structure summary":
        readable.append(technical_summary)
    if cross_conflict.get("tier", "none") != "none":
        readable.append(
            "cross_strategy_conflict: "
            f"tier={cross_conflict['tier']} | spread={cross_conflict['spread']} | "
            f"dominant={cross_conflict.get('dominant_strategy', '')} | weakest={cross_conflict.get('weakest_strategy', '')}"
        )
    if policy_strength >= 2 and technical_severity >= 4 and "technical_structure_risk" not in reasons:
        readable.append("conflict_rule: strong policy could not override severe technical risk")
    if conflict_rule.get("rule") != "balanced_composite":
        readable.append(
            f"conflict_priority: rule={conflict_rule['rule']} | bias={conflict_rule['bias']} | resolution={conflict_rule['resolution']}"
        )

    if not readable:
        readable.append("dropped_reason: rule-based merger filter")
    return "; ".join(readable)
