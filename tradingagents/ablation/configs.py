"""Ablation configuration matrix (R4).

Each entry varies exactly one aspect of the pipeline:
- ``selected_analysts``: single-market vs all four (analyst ablation);
- ``research_depth``: 0 (no debate) / 1 (default) / 3 (deep) (debate ablation).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

ANALYST_ORDER = ("market", "social", "news", "fundamentals")

DEFAULT_TICKERS = ["600519", "000001", "300750"]


@dataclass(frozen=True)
class AblationConfig:
    name: str
    description: str
    selected_analysts: Tuple[str, ...]
    research_depth: int


def build_matrix(provider: Optional[str] = None) -> List[AblationConfig]:
    """Return the ablation matrix (provider not used yet by the runner)."""
    _ = provider
    return [
        AblationConfig(
            name="single_market",
            description="single Market analyst (no team, no debate)",
            selected_analysts=("market",),
            research_depth=1,
        ),
        AblationConfig(
            name="multi_debate_off",
            description="all four analysts, debate disabled (depth=0)",
            selected_analysts=ANALYST_ORDER,
            research_depth=0,
        ),
        AblationConfig(
            name="multi_debate_1",
            description="baseline: all four analysts, 1 debate round",
            selected_analysts=ANALYST_ORDER,
            research_depth=1,
        ),
        AblationConfig(
            name="multi_debate_3",
            description="all four analysts, 3 debate rounds (deep)",
            selected_analysts=ANALYST_ORDER,
            research_depth=3,
        ),
    ]
