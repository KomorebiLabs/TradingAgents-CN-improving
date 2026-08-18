"""Memory package (split from memory.py — refactor/merger-pipeline style).

Public entries: `StructuredMemory`, `FinancialSituationMemory`,
`OrchestrationMemoryEntry` (same contract as the old single-file module).

    types      OrchestrationMemoryEntry TypedDict schema
    basic      FinancialSituationMemory (simple BM25 memory)
    store      StoreMixin (state + index + lifecycle) + StructuredMemory composition
    retrieval  RetrievalMixin (query surface)
    analytics  AnalyticsMixin (statistics / trends)

`StructuredMemory` = StoreMixin + RetrievalMixin + AnalyticsMixin (behavior
identical to the pre-split class).
"""

from .basic import FinancialSituationMemory
from .store import StructuredMemory
from .types import OrchestrationMemoryEntry

__all__ = ["StructuredMemory", "FinancialSituationMemory", "OrchestrationMemoryEntry"]
