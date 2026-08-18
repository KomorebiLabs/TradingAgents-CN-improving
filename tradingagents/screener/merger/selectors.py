"""Signal extraction / tag selection helpers (split from merger.py — refactor/merger-pipeline).

Pure readers over SignalCard: pick evidence metrics, strategy tags, sector.
Depends only on constants + models.
"""

from typing import Any, Dict, List

from tradingagents.screener.models import SignalCard

from .constants import CAPITAL_QUALITY_TAGS, POLICY_SELECTION_TAGS


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
