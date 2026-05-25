"""tradingagents/harness/skills/mapping.py"""
from __future__ import annotations

from typing import Dict, List

from .types import DecisionType


# Decision type → Skill name whitelist
DECISION_SKILL_MAPPING: Dict[DecisionType, List[str]] = {
    DecisionType.OFFENSIVE: [
        "breakout-recognition",
        "trend-patterns",
        "volume-analysis",
        "indicator-library",
        "event-catalyst",
    ],
    DecisionType.DEFENSIVE: [
        "fraud-detection",
        "risk-constraint",
        "crowd-behavior",
        "volume-analysis",
    ],
    DecisionType.VALUATION: [
        "valuation-methods",
        "growth-quality",
        "fraud-detection",
        "risk-constraint",
    ],
    DecisionType.CATALYST: [
        "event-catalyst",
        "policy-impact",
        "sector-rotation",
        "crowd-behavior",
    ],
    DecisionType.SENTIMENT: [
        "sentiment-scoring",
        "crowd-behavior",
    ],
}

# Extra skills injected during counter-round (bull counters bear, etc.)
COUNTER_ROUND_EXTRA: Dict[str, List[str]] = {
    "bull": ["fraud-detection", "risk-constraint"],
    "bear": ["breakout-recognition", "trend-patterns"],
}


class DecisionSkillMapper:
    """Maps a decision type + debate round to a list of skill names to inject."""

    def __init__(self, mapping: Dict[DecisionType, List[str]] | None = None) -> None:
        self._mapping = mapping or DECISION_SKILL_MAPPING

    def get_skill_names(
        self,
        decision_type: DecisionType,
        node_name: str | None = None,
        debate_round: int = 1,
        is_counter_round: bool = False,
    ) -> List[str]:
        base = list(self._mapping.get(decision_type, []))
        if is_counter_round and node_name and node_name.lower() in COUNTER_ROUND_EXTRA:
            base.extend(COUNTER_ROUND_EXTRA[node_name.lower()])
        return list(dict.fromkeys(base))

    def get_injection_strategy(
        self,
        debate_round: int,
        is_adjudication: bool = False,
    ) -> Dict[str, bool]:
        if is_adjudication or debate_round >= 10:
            return {"include_references": True, "skill_strategy": "valuation_focused"}
        if debate_round == 1:
            return {"include_references": False, "skill_strategy": "full"}
        return {"include_references": True, "skill_strategy": "full_plus_counter"}
