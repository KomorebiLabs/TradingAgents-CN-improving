"""Cross-strategy conflict rules & technical structure analysis
(split from merger.py — refactor/merger-pipeline).

Pure decision functions over SignalCard: severity, penalty, rule resolution.
Depends only on selectors + constants.
"""

from typing import Any, Dict, List

from tradingagents.screener.models import SignalCard

from .constants import DEFAULT_CONFLICT_PRIORITY, TECHNICAL_RISK_FLAGS
from .selectors import (
    _as_float,
    _find_signal_metrics,
    _pick_capital_quality_tag,
    _pick_policy_selection_tag,
    _pick_technical_metrics,
    _strategy_score_map,
)


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
