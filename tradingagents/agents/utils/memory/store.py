"""Memory storage + index mixin (split from memory.py — refactor/merger-pipeline style).

`StoreMixin` owns all state fields and storage/index lifecycle methods of
`StructuredMemory`.  The concrete `StructuredMemory` class composes
StoreMixin + RetrievalMixin (retrieval.py) + AnalyticsMixin (analytics.py);
MRO order means retrieval/analytics methods can use `self` state and
`self._tokenize` freely.

NOTE (behavior fossil, kept verbatim): `_structured_index` literal contains
the duplicated key "route_category" — dict semantics keep only the last one,
so it is harmless.  Recorded, not fixed.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:  # pragma: no cover - optional retrieval dependency
    from rank_bm25 import BM25Okapi
except Exception:  # pragma: no cover
    BM25Okapi = None

from .analytics import AnalyticsMixin
from .retrieval import RetrievalMixin


class StoreMixin:
    """Storage, BM25 index, structured inverted indexes, lifecycle."""

    def __init__(self, name: str, config: dict = None):
        """Initialize the structured memory system.

        Args:
            name: Name identifier for this memory instance
            config: Configuration dict
        """
        self.name = name
        self.config = config or {}

        self.documents: List[str] = []
        self.recommendations: List[str] = []
        self.metadata: List[Dict[str, Any]] = []
        self.bm25 = None

        self._index_field = self.config.get("structured_memory_index_field", "combined_text")

        # Structured indexes for fast filtered queries
        self._structured_index: Dict[str, Dict[Any, List[int]]] = {
            "segment": {},          # segment -> list of doc_ids
            "style_bucket": {},     # style_bucket -> list of doc_ids
            "route_category": {},   # route_category -> list of doc_ids
            "final_route": {},      # final_route -> list of doc_ids
            "trade_date": {},       # trade_date -> list of doc_ids
            "decision_quality": {}, # decision_quality -> list of doc_ids
            "route_category": {},   # route_category -> list of doc_ids
        }

        # Index build configuration
        self._index_fields = self.config.get("index_fields", [
            "segment", "style_bucket", "route_category", "final_route",
            "trade_date", "decision_quality"
        ])

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25 indexing."""
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens

    def _get_index_text(self, metadata: Dict[str, Any], document: str) -> str:
        """Get the text used for BM25 indexing.

        Can be configured to use different fields for indexing.
        """
        if self._index_field == "combined_text":
            parts = [document]
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    parts.append(f"{key}: {value}")
            return " | ".join(parts)
        elif self._index_field == "document_only":
            return document
        else:
            return metadata.get(self._index_field, document)

    def _rebuild_index(self):
        """Rebuild the BM25 index after adding documents."""
        if self.documents:
            index_texts = [
                self._get_index_text(meta, doc)
                for meta, doc in zip(self.metadata, self.documents)
            ]
            tokenized_docs = [self._tokenize(text) for text in index_texts]
            self.bm25 = BM25Okapi(tokenized_docs) if BM25Okapi is not None else None
        else:
            self.bm25 = None

    def _update_structured_index(self, doc_id: int, metadata: Dict[str, Any]):
        """Update structured indexes when a new document is added.

        Args:
            doc_id: The document ID to index
            metadata: The metadata dict to index
        """
        for field in self._index_fields:
            value = metadata.get(field)
            if value is not None:
                # Handle list values (e.g., selected_analysts, skills)
                if isinstance(value, list):
                    for item in value:
                        if item not in self._structured_index[field]:
                            self._structured_index[field][item] = []
                        if doc_id not in self._structured_index[field][item]:
                            self._structured_index[field][item].append(doc_id)
                else:
                    # Handle scalar values
                    str_value = str(value)
                    if str_value not in self._structured_index[field]:
                        self._structured_index[field][str_value] = []
                    if doc_id not in self._structured_index[field][str_value]:
                        self._structured_index[field][str_value].append(doc_id)

    def _rebuild_structured_indexes(self):
        """Rebuild all structured indexes from scratch."""
        # Reset all indexes
        for field in self._structured_index:
            self._structured_index[field] = {}

        # Rebuild from metadata
        for doc_id, meta in enumerate(self.metadata):
            self._update_structured_index(doc_id, meta)

    def add_situations(
        self,
        situations_and_advice: List[Tuple[str, str]],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ):
        """Add financial situations with optional structured metadata.

        Args:
            situations_and_advice: List of tuples (situation, recommendation)
            metadata: Optional list of metadata dicts for each situation.
                     If provided, must have same length as situations_and_advice.
        """
        for i, (situation, recommendation) in enumerate(situations_and_advice):
            doc_id = len(self.documents)
            self.documents.append(situation)
            self.recommendations.append(recommendation)

            if metadata and i < len(metadata):
                meta = metadata[i]
            else:
                meta = {}

            self.metadata.append(meta)
            self._update_structured_index(doc_id, meta)

        self._rebuild_index()

    def add_situation(
        self,
        situation: str,
        recommendation: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Add a single situation with structured metadata.

        Args:
            situation: The situation text
            recommendation: The recommendation/advice
            metadata: Optional metadata dict with structured fields
        """
        self.add_situations([(situation, recommendation)], [metadata] if metadata else None)

    def export_memories(self) -> List[Dict[str, Any]]:
        """Export all memories as a list of dicts.

        Returns:
            List of all memories with situation, recommendation, and metadata
        """
        return [
            {
                "situation": self.documents[i],
                "recommendation": self.recommendations[i],
                "metadata": self.metadata[i],
            }
            for i in range(len(self.documents))
        ]

    def import_memories(self, memories: List[Dict[str, Any]]):
        """Import memories from a list of dicts.

        Args:
            memories: List of dicts with situation, recommendation, and metadata
        """
        self.clear()
        for mem in memories:
            self.add_situation(
                situation=mem.get("situation", ""),
                recommendation=mem.get("recommendation", ""),
                metadata=mem.get("metadata"),
            )

    def clear(self):
        """Clear all stored memories including structured indexes."""
        self.documents = []
        self.recommendations = []
        self.metadata = []
        self.bm25 = None

        # Clear structured indexes
        for field in self._structured_index:
            self._structured_index[field] = {}


class StructuredMemory(StoreMixin, RetrievalMixin, AnalyticsMixin):
    """Enhanced memory system that supports structured fields in addition to text.

    Extends FinancialSituationMemory with structured metadata that can be
    used for filtering and structured retrieval. Supports fast lookups by
    segment, style_bucket, route_category, trade_date, and other fields
    via pre-built inverted indexes.

    Composes StoreMixin (state + storage) + RetrievalMixin (queries) +
    AnalyticsMixin (statistics/trends).  Method set and behavior are
    identical to the pre-split single-file class.
    """
