"""Merger package (split from merger.py — refactor/merger-pipeline).

Public entry point: `merge_signal_cards`.  Internal modules:

    constants     shared tag sets + DEFAULT_CONFLICT_PRIORITY
    selectors     evidence extraction / tag picking / sector picking
    conflicts     cross-strategy conflict rules + technical structure analysis
    semantic      semantic priority scoring + retained/dropped summaries
    explanations  reason payload builders
    filters       hard-filter drop decision
    aggregation   same-ticker card merge
    pipeline      main merge_signal_cards flow

Dependency direction (imports only point right):
    constants -> selectors -> conflicts -> semantic -> explanations
                          |-> filters -> pipeline
                          |-> aggregation -> pipeline
"""

from .pipeline import merge_signal_cards

__all__ = ["merge_signal_cards"]
