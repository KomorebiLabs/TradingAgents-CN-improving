"""Evidence freshness aggregation and recommendation qualification."""

from __future__ import annotations

from datetime import datetime

from tradingagents.screener.models import SignalCard


EVIDENCE_REQUIREMENTS = {
    "technical": {"required": {"hist_fetch", "fund_flow"}, "optional": set()},
    "policy": {"required": {"concept_list"}, "optional": {"news"}},
    "smart_money": {
        "required": {"hist_fetch"},
        "optional": {"fund_flow", "tick_data", "valuation_auxiliary", "dragon_tiger_auxiliary"},
    },
}


def apply_evidence_qualification(card: SignalCard) -> SignalCard:
    target = datetime.strptime(card.trade_date, "%Y-%m-%d").date()
    verified: set[str] = set()
    missing_required: set[str] = set()
    degraded: set[str] = set()
    stale_required: set[str] = set()
    required_dates = []
    verified_strategies = 0

    for evidence in card.signal_breakdown:
        rules = EVIDENCE_REQUIREMENTS[evidence.strategy]
        records = {item.source: item for item in evidence.freshness}
        strategy_complete = True
        for module in rules["required"]:
            record = records.get(module)
            if record is None or record.status in {"missing", "estimated"}:
                missing_required.add(module)
                strategy_complete = False
                continue
            if record.trade_date:
                actual = datetime.strptime(record.trade_date, "%Y-%m-%d").date()
                required_dates.append(actual)
                if actual < target or record.status == "stale":
                    stale_required.add(module)
                    strategy_complete = False
                else:
                    verified.add(module)
            else:
                missing_required.add(module)
                strategy_complete = False
        for module in rules["optional"]:
            record = records.get(module)
            if record is not None and record.status == "fresh":
                verified.add(module)
            elif record is not None:
                degraded.add(module)
        if strategy_complete:
            verified_strategies += 1

    oldest = min(required_dates) if required_dates else None
    card.verified_modules = sorted(verified)
    card.missing_required_modules = sorted(missing_required)
    card.degraded_modules = sorted(degraded)
    card.verified_strategy_count = verified_strategies
    card.latest_required_data_date = oldest.isoformat() if oldest else None
    card.max_required_data_lag_days = (target - oldest).days if oldest else None
    card.stale_required_sources = sorted(stale_required)
    card.recommendation_eligible = verified_strategies > 0
    card.data_source_verified = card.recommendation_eligible
    return card
