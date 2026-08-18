"""Merger shared constants (split from merger.py — refactor/merger-pipeline).

Keep this module free of function dependencies: every other merger module
imports from here, never the other way around.
"""

from typing import Any, Dict

from tradingagents.screener.config import SCREENER_CONFIG


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
