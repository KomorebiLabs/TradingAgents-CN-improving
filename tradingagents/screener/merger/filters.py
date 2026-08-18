"""Hard-filter drop decision (split from merger.py — refactor/merger-pipeline).

`_should_drop_card` decides whether a merged card is excluded, returning the
drop reason codes.  NOTE: it mutates `card.risk_flags` (appends
"pe_unavailable") — preserved verbatim from the original implementation.
"""

from typing import Any, Dict, List, Tuple

from tradingagents.screener.models import SignalCard

from .conflicts import (
    _policy_strength,
    _resolve_conflict_rule,
    _technical_structure_severity,
)
from .constants import DEFAULT_CONFLICT_PRIORITY
from .selectors import (
    _as_float,
    _find_signal_metrics,
    _is_st_name,
    _pick_capital_quality_tag,
    _pick_policy_selection_tag,
    _pick_technical_metrics,
)


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
