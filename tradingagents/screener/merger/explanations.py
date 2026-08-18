"""Human-readable reason payload builders (split from merger.py — refactor/merger-pipeline).

Builds the `semantic_reason_payload` dicts (policy/capital/technical sections,
conflict context, funnel fields).  Depends on conflicts + semantic + selectors.
"""

from typing import Any, Dict, List

from tradingagents.screener.models import SignalCard

from .conflicts import (
    _cross_strategy_conflict,
    _pick_technical_structure_summary,
    _policy_strength,
    _resolve_conflict_rule,
)
from .selectors import (
    _find_signal_metrics,
    _pick_capital_quality_summary,
    _pick_capital_quality_tag,
    _pick_policy_selection_tag,
    _pick_technical_metrics,
)
from .semantic import _semantic_priority


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
