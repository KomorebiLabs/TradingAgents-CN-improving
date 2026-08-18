"""Merger main pipeline (split from merger.py — refactor/merger-pipeline).

`merge_signal_cards` is the public entry: group by ticker -> merge -> sort ->
hard filters -> sector diversification -> output cap -> rank annotation.
"""

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from tradingagents.screener.config import SCREENER_CONFIG, SCREENER_THRESHOLDS
from tradingagents.screener.models import SignalCard
from tradingagents.ui.screener_console import console

from .aggregation import _merge_card_group
from .conflicts import (
    _cross_strategy_conflict,
    _pick_technical_structure_summary,
    _policy_strength,
    _resolve_conflict_rule,
    _technical_structure_severity,
)
from .constants import DEFAULT_CONFLICT_PRIORITY
from .explanations import _build_semantic_reason_payload
from .filters import _should_drop_card
from .selectors import (
    _pick_capital_quality_summary,
    _pick_capital_quality_tag,
    _pick_policy_selection_tag,
    _pick_sector,
)
from .semantic import _build_dropped_semantic_summary, _build_retained_semantic_summary, _semantic_priority


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
