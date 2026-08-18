"""Same-ticker card aggregation (split from merger.py — refactor/merger-pipeline).

`_merge_card_group` merges all SignalCards of one ticker into a single card,
recomputing screening_score / initial_confidence and filling evidence_snapshot.
"""

from typing import Any, Dict, List

from tradingagents.screener.config import SCREENER_CONFIG, SCREENER_THRESHOLDS
from tradingagents.screener.models import SignalCard

from .conflicts import (
    _cross_strategy_conflict,
    _pick_technical_structure_summary,
    _resolve_conflict_rule,
)
from .constants import DEFAULT_CONFLICT_PRIORITY
from .explanations import _build_semantic_reason_payload
from .selectors import (
    _pick_capital_quality_summary,
    _pick_capital_quality_tag,
    _pick_policy_selection_tag,
)
from .semantic import _build_retained_semantic_summary, _semantic_priority


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
