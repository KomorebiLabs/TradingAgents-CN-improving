from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from tradingagents.screener.config import SCREENER_CONFIG, SCREENER_THRESHOLDS
from tradingagents.screener.models import SignalCard
from tradingagents.ui.screener_console import console


POLICY_SELECTION_TAGS = {
    "policy_top_stock",
    "policy_core_member",
    "policy_cross_hit_candidate",
    "policy_focus_aligned",  # P5-focus
    "policy_keyword_fallback",
}

CAPITAL_QUALITY_TAGS = {
    "capital_quality_high",
    "capital_quality_persistent",
    "capital_quality_mixed",
    "capital_quality_speculative",
}

TECHNICAL_RISK_FLAGS = {
    "trend_structure_extended",
    "trend_consistency_weak",
    "lost_ma20_support",
    "volume_exhaustion_risk",
    "price_volume_divergence",
}


# H5 FIX: DEFAULT_CONFLICT_PRIORITY now sources its defaults from SCREENER_CONFIG,
# so that updating config.py automatically propagates to the merger without hardcoded duplication.
DEFAULT_CONFLICT_PRIORITY: Dict[str, Any] = dict(SCREENER_CONFIG.get("conflict_priority", {}))


def _find_signal_metrics(card: SignalCard, strategy: str | None = None) -> Dict[str, Any]:
    best: Dict[str, Any] = {}
    best_score = float("-inf")
    for evidence in card.signal_breakdown:
        if strategy is None or evidence.strategy == strategy:
            if evidence.score > best_score:
                best_score = evidence.score
                best = evidence.raw_metrics or {}
    return best


def _pick_policy_selection_tag(card: SignalCard) -> str:
    for tag in card.concept_tags:
        if tag in POLICY_SELECTION_TAGS:
            return tag
    for tag in card.sector_tags:
        if tag in POLICY_SELECTION_TAGS:
            return tag
    metrics = _find_signal_metrics(card, "policy")
    return str(metrics.get("stock_selection_tag", "") or "")


def _pick_capital_quality_tag(card: SignalCard) -> str:
    for tag in card.concept_tags:
        if tag in CAPITAL_QUALITY_TAGS:
            return tag
    for tag in card.sector_tags:
        if tag in CAPITAL_QUALITY_TAGS:
            return tag
    metrics = _find_signal_metrics(card, "smart_money")
    return str(metrics.get("capital_quality_tag", "") or "")


def _pick_capital_quality_summary(card: SignalCard) -> str:
    metrics = _find_signal_metrics(card, "smart_money")
    summary = metrics.get("capital_quality_summary")
    if summary:
        return str(summary)
    tag = _pick_capital_quality_tag(card)
    if tag == "capital_quality_high":
        return "high-quality persistent capital flow"
    if tag == "capital_quality_persistent":
        return "persistent multi-day capital flow"
    if tag == "capital_quality_speculative":
        return "high-heat low-quality speculative capital flow"
    if tag == "capital_quality_mixed":
        return "mixed capital-quality profile"
    return "no explicit capital-quality summary"


def _pick_technical_metrics(card: SignalCard) -> Dict[str, Any]:
    return _find_signal_metrics(card, "technical")


def _strategy_score_map(card: SignalCard) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for evidence in card.signal_breakdown:
        scores[evidence.strategy] = float(evidence.score)
    return scores


def _derive_technical_risk_flags(metrics: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    structure_risk = _as_float(metrics.get("structure_risk_score"))
    consistency = _as_float(metrics.get("trend_consistency_score"))
    volume_divergence = _as_float(metrics.get("volume_price_divergence_score"))
    volume_spike = _as_float(metrics.get("volume_spike_ratio"))
    extension = _as_float(metrics.get("recent_extension_pct"))
    if structure_risk is not None and structure_risk <= 45:
        flags.append("trend_structure_extended")
    if consistency is not None and consistency <= 48:
        flags.append("trend_consistency_weak")
    if volume_divergence is not None and volume_divergence <= 42:
        flags.append("price_volume_divergence")
    if volume_spike is not None and extension is not None and volume_spike >= 1.8 and extension >= 8:
        flags.append("volume_exhaustion_risk")
    if not metrics.get("close_above_ma20", True):
        flags.append("lost_ma20_support")
    return flags


def _technical_structure_penalty(card: SignalCard) -> int:
    metrics = _pick_technical_metrics(card)
    if not metrics:
        return 0

    penalty = 0
    structure_risk = _as_float(metrics.get("structure_risk_score"))
    consistency = _as_float(metrics.get("trend_consistency_score"))
    extension = _as_float(metrics.get("recent_extension_pct"))
    volume_confirmation = _as_float(metrics.get("volume_confirmation_score"))
    breakout_quality = _as_float(metrics.get("breakout_quality_score"))
    volume_divergence = _as_float(metrics.get("volume_price_divergence_score"))
    volume_spike = _as_float(metrics.get("volume_spike_ratio"))

    if structure_risk is not None and structure_risk <= 45:
        penalty += 2
    if structure_risk is not None and structure_risk <= 35:
        penalty += 2
    if consistency is not None and consistency <= 48:
        penalty += 1
    if not metrics.get("close_above_ma20", True):
        penalty += 1
    if not metrics.get("close_above_ma60", True):
        penalty += 1
    if extension is not None and extension > 8:
        penalty += 1
    if volume_confirmation is not None and volume_confirmation <= 45:
        penalty += 1
    if breakout_quality is not None and breakout_quality <= 48:
        penalty += 1
    if volume_divergence is not None and volume_divergence <= 42:
        penalty += 1
    if volume_spike is not None and extension is not None and volume_spike >= 1.8 and extension >= 8:
        penalty += 1
    return penalty


def _technical_structure_severity(card: SignalCard) -> int:
    metrics = _pick_technical_metrics(card)
    if not metrics:
        return 0

    severity = 0
    structure_risk = _as_float(metrics.get("structure_risk_score"))
    consistency = _as_float(metrics.get("trend_consistency_score"))
    extension = _as_float(metrics.get("recent_extension_pct"))
    volume_confirmation = _as_float(metrics.get("volume_confirmation_score"))
    breakout_quality = _as_float(metrics.get("breakout_quality_score"))
    volume_divergence = _as_float(metrics.get("volume_price_divergence_score"))
    volume_spike = _as_float(metrics.get("volume_spike_ratio"))
    if structure_risk is not None and structure_risk <= 45:
        severity += 1
    if structure_risk is not None and structure_risk <= 35:
        severity += 1
    if consistency is not None and consistency <= 48:
        severity += 1
    if consistency is not None and consistency <= 40:
        severity += 1
    if not metrics.get("close_above_ma20", True):
        severity += 1
    if not metrics.get("close_above_ma60", True):
        severity += 1
    if extension is not None and extension > 8:
        severity += 1
    if volume_confirmation is not None and volume_confirmation <= 45:
        severity += 1
    if breakout_quality is not None and breakout_quality <= 48:
        severity += 1
    if volume_divergence is not None and volume_divergence <= 42:
        severity += 1
    if volume_spike is not None and extension is not None and volume_spike >= 1.8 and extension >= 8:
        severity += 1
    return severity


def _capital_quality_severity(card: SignalCard) -> int:
    capital_tag = _pick_capital_quality_tag(card)
    metrics = _find_signal_metrics(card, "smart_money")
    heat_quality_gap = _as_float(metrics.get("heat_quality_gap_score"))
    if capital_tag == "capital_quality_speculative":
        return 3 if heat_quality_gap is not None and heat_quality_gap >= 28 else 2
    if capital_tag == "capital_quality_mixed":
        return 1
    return 0


def _policy_semantic_bonus(card: SignalCard) -> int:
    metrics = _find_signal_metrics(card, "policy")
    primary_score = _as_float(metrics.get("primary_concept_score")) or 0.0
    competition_score = _as_float(metrics.get("concept_competition_score")) or 0.0
    overlap_count = int(metrics.get("multi_concept_overlap_count", 0) or 0)
    bonus = 0
    if primary_score >= 75:
        bonus += 1
    if competition_score >= 78:
        bonus += 1
    if overlap_count >= 2:
        bonus += 1
    return bonus


def _resolve_conflict_rule(card: SignalCard, conflict_priority: Dict[str, Any] | None = None) -> Dict[str, Any]:
    cp = {**DEFAULT_CONFLICT_PRIORITY, **(conflict_priority or {})}
    policy_strength = _policy_strength(card)
    technical_severity = _technical_structure_severity(card)
    capital_tag = _pick_capital_quality_tag(card)
    cross_conflict = _cross_strategy_conflict(card, cp)

    if policy_strength >= 2 and capital_tag == "capital_quality_speculative" and technical_severity >= int(cp["technical_veto_min_severity"]):
        return {
            "rule": "technical_veto_overrides_semantic",
            "bias": int(cp["technical_veto_bias"]),
            "resolution": "policy_vs_technical",
        }
    if policy_strength >= 2 and capital_tag in {"capital_quality_high", "capital_quality_persistent"} and technical_severity <= 1:
        return {
            "rule": "semantic_consensus_priority",
            "bias": int(cp["semantic_consensus_bias"]),
            "resolution": "semantic_consensus",
        }
    if policy_strength == 0 and technical_severity >= int(cp["weak_policy_stress_min_severity"]):
        return {
            "rule": "weak_policy_discount_under_technical_stress",
            "bias": int(cp["weak_policy_stress_bias"]),
            "resolution": "policy_vs_technical",
        }
    if capital_tag == "capital_quality_speculative" and technical_severity >= int(cp["speculative_technical_min_severity"]):
        return {
            "rule": "speculative_flow_discount",
            "bias": int(cp["speculative_flow_bias"]),
            "resolution": "capital_vs_technical",
        }
    if cross_conflict["tier"] == "aligned":
        return {
            "rule": "aligned_multi_strategy_support",
            "bias": int(cp["aligned_support_bias"]),
            "resolution": "aligned",
        }
    if cross_conflict["tier"] == "severe":
        return {
            "rule": "severe_conflict_penalty",
            "bias": int(cp["severe_conflict_bias"]),
            "resolution": "cross_strategy_conflict",
        }
    return {
        "rule": "balanced_composite",
        "bias": 0,
        "resolution": "none",
    }


def _cross_strategy_conflict(card: SignalCard, conflict_priority: Dict[str, Any] | None = None) -> Dict[str, Any]:
    cp = {**DEFAULT_CONFLICT_PRIORITY, **(conflict_priority or {})}
    score_map = _strategy_score_map(card)
    if not score_map:
        return {
            "spread": 0.0,
            "tier": "none",
            "dominant_strategy": "",
            "weakest_strategy": "",
            "alignment_bonus": 0,
            "conflict_penalty": 0,
        }

    ordered = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
    dominant_strategy, dominant_score = ordered[0]
    weakest_strategy, weakest_score = ordered[-1]
    spread = round(dominant_score - weakest_score, 2)

    # A2: tier bonus/penalty integers now from config
    aligned_bonus_int = int(cp.get("aligned_bonus_int", 2))
    moderate_penalty_int = int(cp.get("moderate_penalty_int", 1))
    high_penalty_int = int(cp.get("high_penalty_int", 2))
    severe_penalty_int = int(cp.get("severe_penalty_int", 3))
    conflict_penalty = 0
    alignment_bonus = 0
    if spread <= float(cp["aligned_spread_max"]):
        tier = "aligned"
        alignment_bonus = aligned_bonus_int
    elif spread <= float(cp["moderate_spread_max"]):
        tier = "moderate"
        alignment_bonus = 0
        conflict_penalty = moderate_penalty_int
    elif spread <= float(cp["high_spread_max"]):
        tier = "high"
        conflict_penalty = high_penalty_int
    else:
        tier = "severe"
        conflict_penalty = severe_penalty_int

    policy_strength = _policy_strength(card)
    technical_severity = _technical_structure_severity(card)
    capital_severity = _capital_quality_severity(card)

    if policy_strength >= 2 and technical_severity >= 4:
        conflict_penalty += 1
    if policy_strength == 0 and technical_severity >= 3:
        conflict_penalty += 1
    if capital_severity >= 2 and policy_strength <= 1:
        conflict_penalty += 1
    if capital_severity >= 2 and technical_severity >= 3:
        conflict_penalty += 1
    if policy_strength >= 2 and capital_severity == 0 and technical_severity <= 1:
        alignment_bonus += 1

    return {
        "spread": spread,
        "tier": tier,
        "dominant_strategy": dominant_strategy,
        "weakest_strategy": weakest_strategy,
        "alignment_bonus": alignment_bonus,
        "conflict_penalty": conflict_penalty,
    }


def _policy_strength(card: SignalCard) -> int:
    policy_tag = _pick_policy_selection_tag(card)
    if policy_tag == "policy_top_stock":
        return 3
    if policy_tag == "policy_core_member":
        return 2
    if policy_tag == "policy_cross_hit_candidate":
        return 1
    # P5-focus: focus-aligned fallback is semantically better than keyword fallback
    if policy_tag == "policy_focus_aligned":
        return 1
    if policy_tag == "policy_keyword_fallback":
        return 0
    return 0


def _pick_technical_structure_summary(card: SignalCard) -> str:
    metrics = _pick_technical_metrics(card)
    if not metrics:
        return "no explicit technical structure summary"

    structure_risk = metrics.get("structure_risk_score", "N/A")
    consistency = metrics.get("trend_consistency_score", "N/A")
    extension = metrics.get("recent_extension_pct", "N/A")
    positive_days = metrics.get("positive_days_ratio_pct", "N/A")
    volume_confirmation = metrics.get("volume_confirmation_score", "N/A")
    breakout_quality = metrics.get("breakout_quality_score", "N/A")
    volume_divergence = metrics.get("volume_price_divergence_score", "N/A")
    flags = [flag for flag in card.risk_flags if flag in TECHNICAL_RISK_FLAGS]
    if not flags:
        flags = _derive_technical_risk_flags(metrics)
    flag_text = ",".join(flags) if flags else "none"
    return (
        f"technical_structure: structure_risk={structure_risk} | "
        f"consistency={consistency} | extension={extension} | "
        f"positive_days={positive_days} | volume_confirmation={volume_confirmation} | "
        f"breakout_quality={breakout_quality} | volume_divergence={volume_divergence} | flags={flag_text}"
    )


def _build_policy_reason_payload(card: SignalCard) -> Dict[str, Any]:
    metrics = _find_signal_metrics(card, "policy")
    tech_metrics = _find_signal_metrics(card, "technical")  # pe_ttm lives in technical evidence
    policy_tag = _pick_policy_selection_tag(card) or "none"
    threshold_snapshot = dict(metrics.get("threshold_snapshot", {}) or {})
    threshold_triggers: List[str] = []
    threshold_trigger_details: List[Dict[str, Any]] = []
    if "concept_conviction_low" in card.risk_flags:
        threshold_triggers.append("concept_conviction_low")
        threshold_trigger_details.append(
            {
                "field": "concept_conviction_score",
                "observed": metrics.get("concept_conviction_score", "N/A"),
                "threshold": threshold_snapshot.get("concept_conviction_low", "N/A"),
                "comparator": "lte",
            }
        )
    if "pe_unavailable" in card.risk_flags:
        threshold_triggers.append("pe_unavailable")
        pe_ttm = tech_metrics.get("pe_ttm") or tech_metrics.get("pe")
        threshold_trigger_details.append(
            {
                "field": "pe_ttm",
                "observed": pe_ttm if pe_ttm is not None else "N/A",
                "threshold": "required",
                "comparator": "unavailable",
            }
        )
    return {
        "policy_selection_tag": policy_tag,
        "policy_strength": _policy_strength(card),
        "primary_concept_score": metrics.get("primary_concept_score", "N/A"),
        "concept_competition_score": metrics.get("concept_competition_score", "N/A"),
        "multi_concept_overlap_count": metrics.get("multi_concept_overlap_count", "N/A"),
        "primary_concept_selection_summary": metrics.get("primary_concept_selection_summary", ""),
        "threshold_snapshot": threshold_snapshot,
        "threshold_triggers": threshold_triggers,
        "threshold_trigger_details": threshold_trigger_details,
    }


def _build_capital_reason_payload(card: SignalCard) -> Dict[str, Any]:
    metrics = _find_signal_metrics(card, "smart_money")
    capital_tag = _pick_capital_quality_tag(card) or "none"
    threshold_snapshot = dict(metrics.get("threshold_snapshot", {}) or {})
    threshold_triggers: List[str] = []
    threshold_trigger_details: List[Dict[str, Any]] = []
    if "quality_stability_low" in card.risk_flags:
        threshold_triggers.append("quality_stability_low")
        threshold_trigger_details.append(
            {
                "field": "quality_stability_index",
                "observed": metrics.get("quality_stability_index", "N/A"),
                "threshold": threshold_snapshot.get("quality_stability_low", "N/A"),
                "comparator": "lte",
            }
        )
    return {
        "capital_quality_tag": capital_tag,
        "capital_quality_summary": _pick_capital_quality_summary(card),
        "heat_quality_gap_score": metrics.get("heat_quality_gap_score", "N/A"),
        "capital_quality_weight": metrics.get("capital_quality_weight", "N/A"),
        "risk_constraint_score": metrics.get("risk_constraint_score", "N/A"),
        "continuity_score": metrics.get("continuity_score", "N/A"),
        "threshold_snapshot": threshold_snapshot,
        "threshold_triggers": threshold_triggers,
        "threshold_trigger_details": threshold_trigger_details,
    }


def _build_technical_reason_payload(card: SignalCard) -> Dict[str, Any]:
    metrics = _pick_technical_metrics(card)
    threshold_snapshot = dict(metrics.get("threshold_snapshot", {}) or {})
    threshold_triggers: List[str] = []
    threshold_trigger_details: List[Dict[str, Any]] = []
    if "signal_consistency_low" in card.risk_flags:
        threshold_triggers.append("signal_consistency_low")
        threshold_trigger_details.append(
            {
                "field": "signal_consistency_index",
                "observed": metrics.get("signal_consistency_index", "N/A"),
                "threshold": threshold_snapshot.get("signal_consistency_low", "N/A"),
                "comparator": "lte",
            }
        )
    return {
        "technical_structure_summary": _pick_technical_structure_summary(card),
        "structure_risk_score": metrics.get("structure_risk_score", "N/A"),
        "trend_consistency_score": metrics.get("trend_consistency_score", "N/A"),
        "recent_extension_pct": metrics.get("recent_extension_pct", "N/A"),
        "volume_confirmation_score": metrics.get("volume_confirmation_score", "N/A"),
        "breakout_quality_score": metrics.get("breakout_quality_score", "N/A"),
        "volume_price_divergence_score": metrics.get("volume_price_divergence_score", "N/A"),
        "threshold_snapshot": threshold_snapshot,
        "threshold_triggers": threshold_triggers,
        "threshold_trigger_details": threshold_trigger_details,
    }


def _build_semantic_reason_payload(
    card: SignalCard,
    decision: str,
    summary: str,
    reasons: List[str] | None = None,
    conflict_priority: Dict[str, Any] | None = None,
    # P5-4: Funnel context parameters
    funnel_stage: str | None = None,
    stagea_reason_ref: str | None = None,
) -> Dict[str, Any]:
    cross_conflict = _cross_strategy_conflict(card, conflict_priority)
    conflict_rule = _resolve_conflict_rule(card, conflict_priority)
    payload = {
        "decision": decision,
        "summary": summary,
        "reasons": list(reasons or []),
        "semantic_priority": _semantic_priority(card, conflict_priority),
        "policy": _build_policy_reason_payload(card),
        "capital": _build_capital_reason_payload(card),
        "technical": _build_technical_reason_payload(card),
        "cross_strategy_conflict": cross_conflict,
        "conflict_resolution": conflict_rule["resolution"],
        "conflict_resolution_rule": conflict_rule["rule"],
        "conflict_priority_bias": conflict_rule["bias"],
    }
    # P5-4: Add funnel context if provided
    if funnel_stage:
        payload["funnel_stage"] = funnel_stage
    if stagea_reason_ref:
        payload["stagea_reason_ref"] = stagea_reason_ref
    return payload


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


def _merge_card_group(cards: List[SignalCard], conflict_priority: Dict[str, Any] | None = None, merger_thresholds: Dict[str, Any] | None = None) -> SignalCard:
    cp = {**DEFAULT_CONFLICT_PRIORITY, **(conflict_priority or {})}
    # A2: merger scoring multipliers from config (defaulting to SCREENER_CONFIG["merger_thresholds"])
    mt = {**SCREENER_CONFIG.get("merger_thresholds", {}), **(merger_thresholds or {})}
    resonance_mult = int(mt.get("resonance_bonus_per_source", 5))
    confidence_mult = float(mt.get("confidence_all_verified_bonus", 5))
    risk_flag_mult = int(mt.get("risk_flag_penalty_mult", 3))
    semantic_bonus_mult = float(mt.get("semantic_bonus_mult", 1.5))
    conflict_penalty_mult = float(mt.get("conflict_penalty_mult", 1.5))
    score_confidence_mult = float(mt.get("score_confidence_mult", 0.85))

    base = cards[0].model_copy(deep=True)
    base.strategy_sources = sorted({source for card in cards for source in card.strategy_sources})
    base.signal_breakdown = [evidence for card in cards for evidence in card.signal_breakdown]
    base.sector_tags = sorted({tag for card in cards for tag in card.sector_tags})
    base.concept_tags = sorted({tag for card in cards for tag in card.concept_tags})
    base.risk_flags = sorted({flag for card in cards for flag in card.risk_flags})
    base.evidence_snapshot = {
        "merged_from": [card.ticker for card in cards],
        "source_scores": {card.ticker: card.screening_score for card in cards},
    }

    source_count = len(base.strategy_sources)
    resonance_bonus = max(0, (source_count - 1) * resonance_mult)
    weighted_score = sum(card.screening_score for card in cards) / max(len(cards), 1)
    penalty = len(base.risk_flags) * risk_flag_mult
    confidence_bonus = confidence_mult if all(card.data_source_verified for card in cards) else 0
    cross_conflict = _cross_strategy_conflict(base, cp)
    conflict_rule = _resolve_conflict_rule(base, cp)
    semantic_bonus = _semantic_priority(base, cp) * semantic_bonus_mult + int(cross_conflict["alignment_bonus"]) * 0.75

    base.screening_score = min(100.0, max(0.0, weighted_score + resonance_bonus + semantic_bonus))
    base.initial_confidence = min(
        100.0,
        base.screening_score * score_confidence_mult + confidence_bonus - penalty + semantic_bonus - int(cross_conflict["conflict_penalty"]) * conflict_penalty_mult,
    )
    base.data_source_verified = all(card.data_source_verified for card in cards)
    base.trigger_reason = " + ".join(sorted({card.trigger_reason for card in cards}))
    base.evidence_snapshot["policy_selection_tag"] = _pick_policy_selection_tag(base) or "none"
    base.evidence_snapshot["capital_quality_tag"] = _pick_capital_quality_tag(base) or "none"
    base.evidence_snapshot["capital_quality_summary"] = _pick_capital_quality_summary(base)
    base.evidence_snapshot["technical_structure_summary"] = _pick_technical_structure_summary(base)
    base.evidence_snapshot["cross_strategy_conflict"] = cross_conflict
    base.evidence_snapshot["conflict_priority_bias"] = conflict_rule["bias"]
    base.evidence_snapshot["conflict_resolution_rule"] = conflict_rule["rule"]
    base.evidence_snapshot["semantic_priority"] = _semantic_priority(base, cp)
    base.evidence_snapshot["semantic_decision_summary"] = _build_retained_semantic_summary(base, cp)
    base.evidence_snapshot["semantic_reason_payload"] = _build_semantic_reason_payload(
        base,
        decision="retained",
        summary=base.evidence_snapshot["semantic_decision_summary"],
        conflict_priority=cp,
    )
    # A2: include threshold_snapshot in merged evidence_snapshot
    base.evidence_snapshot["merger_threshold_snapshot"] = {
        "source": "merger",
        "merger_thresholds": dict(mt),
        "screener_thresholds": dict(SCREENER_THRESHOLDS),
        "conflict_priority_overrides": {
            k: v for k, v in cp.items() if k not in DEFAULT_CONFLICT_PRIORITY
        },
    }
    return base


def _is_st_name(card: SignalCard) -> bool:
    """Detect ST/*ST status from multiple sources.

    Checks company_name (if real), sector_tags, and concept_tags.
    A card is flagged as ST if ANY source indicates ST status.
    """
    name = (card.company_name or "").upper()
    name_is_st = name.startswith("ST") or name.startswith("*ST") or " ST" in name

    # Also check sector_tags which are more reliable when name is a placeholder
    tag_is_st = any(
        tag.upper().startswith(("ST", "*ST")) or " ST" in tag.upper()
        for tag in (card.sector_tags or [])
    )

    return name_is_st or tag_is_st


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _pick_sector(card: SignalCard) -> str:
    policy_tag = _pick_policy_selection_tag(card)
    if policy_tag in {"policy_top_stock", "policy_core_member"}:
        for tag in card.concept_tags:
            if tag not in POLICY_SELECTION_TAGS and tag not in CAPITAL_QUALITY_TAGS:
                return tag
    if card.sector_tags:
        return card.sector_tags[0]
    if card.concept_tags:
        return card.concept_tags[0]
    return "unknown"


def _should_drop_card(
    card: SignalCard,
    thresholds: Dict[str, Any],
    conflict_priority: Dict[str, Any] | None = None,
) -> Tuple[bool, List[str]]:
    cp = {**DEFAULT_CONFLICT_PRIORITY, **(conflict_priority or {})}
    reasons: List[str] = []
    metrics = _find_signal_metrics(card)
    policy_tag = _pick_policy_selection_tag(card)
    capital_tag = _pick_capital_quality_tag(card)
    technical_severity = _technical_structure_severity(card)
    policy_strength = _policy_strength(card)

    if _is_st_name(card):
        reasons.append("st_flagged")

    change_pct = _as_float(metrics.get("change_pct") or metrics.get("changepercent"))
    if change_pct is not None and change_pct <= float(thresholds.get("near_limit_down_pct", -9.9)):
        reasons.append("near_limit_down")

    turnover = _as_float(metrics.get("turnover_rate") or metrics.get("turnover"))
    if turnover is not None and turnover < float(thresholds.get("low_turnover_rate", 2.0)):
        reasons.append("low_turnover")

    float_market_cap_billion = _as_float(metrics.get("float_market_cap_billion"))
    if float_market_cap_billion is not None and float_market_cap_billion < float(
        thresholds.get("low_float_market_cap_billion", 30.0)
    ):
        reasons.append("low_float_market_cap")

    pe_ttm = _as_float(metrics.get("pe_ttm") or metrics.get("pe"))
    if pe_ttm is not None:
        if pe_ttm < 0:
            reasons.append("negative_pe")
        elif pe_ttm > float(thresholds.get("extreme_pe_upper", 150.0)):
            reasons.append("extreme_pe")
    elif "pe_unavailable" not in card.risk_flags:
        card.risk_flags.append("pe_unavailable")

    if (
        capital_tag == "capital_quality_speculative"
        and policy_tag not in {"policy_top_stock", "policy_core_member"}
        and card.screening_score < float(thresholds.get("drop_speculative_score_floor", 78.0))
    ):
        reasons.append("speculative_capital_flow")
    smart_metrics = _find_signal_metrics(card, "smart_money")
    heat_quality_gap = _as_float(smart_metrics.get("heat_quality_gap_score"))
    if (
        heat_quality_gap is not None
        and heat_quality_gap >= 28
        and capital_tag in {"capital_quality_speculative", "capital_quality_mixed"}
        and policy_tag != "policy_top_stock"
    ):
        reasons.append("heat_quality_gap_exclusion")

    if (
        policy_tag == "policy_keyword_fallback"
        and capital_tag == "capital_quality_speculative"
        and card.initial_confidence < float(thresholds.get("drop_weak_policy_confidence_floor", 70.0))
    ):
        reasons.append("low_semantic_conviction")
    technical_metrics = _pick_technical_metrics(card)
    if technical_metrics:
        structure_risk = _as_float(technical_metrics.get("structure_risk_score"))
        consistency = _as_float(technical_metrics.get("trend_consistency_score"))
        if (
            structure_risk is not None
            and consistency is not None
            and structure_risk <= 35
            and consistency <= 45
            and card.screening_score < float(thresholds.get("drop_speculative_score_floor", 78.0))
        ):
            reasons.append("technical_structure_risk")
    if (
        policy_strength >= 2
        and capital_tag == "capital_quality_speculative"
        and technical_severity >= int(cp["technical_veto_min_severity"])
        and card.screening_score < float(thresholds.get("drop_policy_speculative_floor", 82.0))
    ):
        reasons.append("conflict_policy_capital_vs_technical")
    if (
        policy_strength == 0
        and capital_tag in {"capital_quality_mixed", "capital_quality_speculative"}
        and technical_severity >= int(cp["weak_policy_stress_min_severity"])
        and card.initial_confidence < float(thresholds.get("drop_weak_policy_floor", 72.0))
    ):
        reasons.append("conflict_policy_capital_vs_technical")
    conflict_rule = _resolve_conflict_rule(card, cp)
    if conflict_rule["rule"] == "weak_policy_discount_under_technical_stress" and card.initial_confidence < float(thresholds.get("drop_weak_policy_stress_floor", 74.0)):
        reasons.append("weak_policy_under_technical_stress")
    if conflict_rule["rule"] == "technical_veto_overrides_semantic" and card.screening_score < float(thresholds.get("drop_technical_veto_floor", 84.0)):
        reasons.append("technical_veto")

    return bool(reasons), reasons


def merge_signal_cards(
    cards: List[SignalCard],
    mode: str = "MVP",
    config: Dict[str, Any] | None = None,
) -> Tuple[List[SignalCard], List[Dict[str, Any]]]:
    if not cards:
        return [], []

    console.print(f"[cyan]>> Merger[/cyan]  [dim]mode={mode}  {len(cards)} cards...[/dim]", end="\r")

    config = config or SCREENER_CONFIG
    thresholds = config.get("thresholds", SCREENER_THRESHOLDS) if isinstance(config, dict) else SCREENER_THRESHOLDS
    conflict_priority = (
        config.get("conflict_priority", DEFAULT_CONFLICT_PRIORITY)
        if isinstance(config, dict)
        else DEFAULT_CONFLICT_PRIORITY
    )
    # A2: ensure merger_thresholds come from SCREENER_CONFIG when config is minimal
    merger_thresholds = dict(SCREENER_CONFIG.get("merger_thresholds", {}))
    grouped: Dict[str, List[SignalCard]] = defaultdict(list)
    for card in cards:
        grouped[card.ticker].append(card)

    console.print(f"[cyan]  Merging and sorting...[/cyan]", end="\r")
    merged_cards = [_merge_card_group(group, conflict_priority, merger_thresholds) for group in grouped.values()]
    merged_cards.sort(
        key=lambda card: (
            _semantic_priority(card, conflict_priority),
            _resolve_conflict_rule(card, conflict_priority)["bias"],
            _policy_strength(card),
            -_technical_structure_severity(card),
            card.screening_score,
            card.initial_confidence,
        ),
        reverse=True,
    )

    same_sector_limit = config.get("candidates", {}).get("same_sector_limit", 2)
    limited: List[SignalCard] = []
    sector_counts: Dict[str, int] = defaultdict(int)
    dropped: List[Dict[str, Any]] = []

    for card in merged_cards:
        should_drop, reasons = _should_drop_card(card, thresholds, conflict_priority)
        if should_drop:
            policy_tag = _pick_policy_selection_tag(card)
            capital_tag = _pick_capital_quality_tag(card)
            # P5-4: Build stagea_reason_ref for funnel audit
            stagea_ref = f"stagea_pass:{card.ticker}" if card.ticker else "stagea_unknown"

            dropped.append(
                {
                    "ticker": card.ticker,
                    "company_name": card.company_name,
                    "reasons": reasons,
                    # P5-4: funnel_stage indicates where in the funnel the drop occurred
                    "funnel_stage": "stageb_hard_filter",
                    "stagea_reason_ref": stagea_ref,
                    "policy_selection_tag": policy_tag or "none",
                    "capital_quality_tag": capital_tag or "none",
                    "capital_quality_summary": _pick_capital_quality_summary(card),
                    "technical_structure_summary": _pick_technical_structure_summary(card),
                    "conflict_resolution": _resolve_conflict_rule(card, conflict_priority)["resolution"],
                    "conflict_resolution_rule": _resolve_conflict_rule(card, conflict_priority)["rule"],
                    "conflict_priority_bias": _resolve_conflict_rule(card, conflict_priority)["bias"],
                    "semantic_decision_summary": _build_dropped_semantic_summary(
                        card=card,
                        reasons=reasons,
                        policy_tag=policy_tag,
                        capital_tag=capital_tag,
                        conflict_priority=conflict_priority,
                    ),
                    "semantic_reason_payload": _build_semantic_reason_payload(
                        card,
                        decision="dropped",
                        summary=_build_dropped_semantic_summary(
                            card=card,
                            reasons=reasons,
                            policy_tag=policy_tag,
                            capital_tag=capital_tag,
                            conflict_priority=conflict_priority,
                        ),
                        reasons=reasons,
                        conflict_priority=conflict_priority,
                        # P5-4: Include funnel context
                        funnel_stage="stageb_hard_filter",
                        stagea_reason_ref=stagea_ref,
                    ),
                }
            )
            continue

        sector = _pick_sector(card)
        if sector_counts[sector] >= same_sector_limit:
            policy_tag = _pick_policy_selection_tag(card)
            capital_tag = _pick_capital_quality_tag(card)
            stagea_ref = f"stagea_pass:{card.ticker}" if card.ticker else "stagea_unknown"

            dropped.append(
                {
                    "ticker": card.ticker,
                    "company_name": card.company_name,
                    "reasons": ["same_sector_limit"],
                    # P5-4: funnel_stage for diversification drops
                    "funnel_stage": "stageb_diversification",
                    "stagea_reason_ref": stagea_ref,
                    "sector": sector,
                    "policy_selection_tag": policy_tag or "none",
                    "capital_quality_tag": capital_tag or "none",
                    "capital_quality_summary": _pick_capital_quality_summary(card),
                    "technical_structure_summary": _pick_technical_structure_summary(card),
                    "conflict_resolution": _resolve_conflict_rule(card, conflict_priority)["resolution"],
                    "conflict_resolution_rule": _resolve_conflict_rule(card, conflict_priority)["rule"],
                    "conflict_priority_bias": _resolve_conflict_rule(card, conflict_priority)["bias"],
                    "semantic_decision_summary": _build_dropped_semantic_summary(
                        card=card,
                        reasons=["same_sector_limit"],
                        policy_tag=policy_tag,
                        capital_tag=capital_tag,
                        conflict_priority=conflict_priority,
                    ),
                    "semantic_reason_payload": _build_semantic_reason_payload(
                        card,
                        decision="dropped",
                        summary=_build_dropped_semantic_summary(
                            card=card,
                            reasons=["same_sector_limit"],
                            policy_tag=policy_tag,
                            capital_tag=capital_tag,
                            conflict_priority=conflict_priority,
                        ),
                        reasons=["same_sector_limit"],
                        conflict_priority=conflict_priority,
                        # P5-4: Include funnel context
                        funnel_stage="stageb_diversification",
                        stagea_reason_ref=stagea_ref,
                    ),
                }
            )
            continue
        sector_counts[sector] += 1
        limited.append(card)

    max_output = config.get("candidates", {}).get(
        "max_output_extended" if mode == "EXTENDED" else "max_output",
        3,
    )
    limited = limited[:max_output]

    for idx, card in enumerate(limited, 1):
        card.screening_rank = idx
        card.evidence_snapshot["semantic_decision"] = "retained"
        card.evidence_snapshot["technical_structure_summary"] = _pick_technical_structure_summary(card)
        card.evidence_snapshot["cross_strategy_conflict"] = _cross_strategy_conflict(card, conflict_priority)
        card.evidence_snapshot["conflict_resolution"] = _resolve_conflict_rule(card, conflict_priority)["resolution"]
        card.evidence_snapshot["conflict_resolution_rule"] = _resolve_conflict_rule(card, conflict_priority)["rule"]
        card.evidence_snapshot["conflict_priority_bias"] = _resolve_conflict_rule(card, conflict_priority)["bias"]
        card.evidence_snapshot["semantic_decision_summary"] = _build_retained_semantic_summary(card, conflict_priority)
        card.evidence_snapshot["semantic_reason_payload"] = _build_semantic_reason_payload(
            card,
            decision="retained",
            summary=card.evidence_snapshot["semantic_decision_summary"],
            conflict_priority=conflict_priority,
        )

    console.print(f"[green][OK] Merger done[/green]  [cyan]{len(limited)}[/cyan] retained  [red]{len(dropped)}[/red] dropped  [dim]mode={mode}[/dim]")
    return limited, dropped
