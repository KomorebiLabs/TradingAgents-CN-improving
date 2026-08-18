"""Memory retrieval mixin (split from memory.py — refactor/merger-pipeline style).

`RetrievalMixin` provides the query surface of `StructuredMemory` (BM25
matching, filter predicates, field/segment/route lookups).  Relies on state
and `_tokenize` from StoreMixin via MRO — no imports between mixins.
"""

from typing import Any, Dict, List, Optional, Set


class RetrievalMixin:
    """Query/retrieval methods (assumes StoreMixin state)."""

    def get_memories(
        self,
        current_situation: str,
        n_matches: int = 1,
        filters: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
    ) -> List[Dict[str, Any]]:
        """Find matching recommendations with optional structured filtering.

        Supports advanced filter operators:
        - Exact match: {"segment": "cn_star"}
        - List values (OR): {"segment": ["cn_star", "cn_chinext"]}
        - Numeric comparisons: {"compression_rate_min": 0.3, "compression_rate_max": 0.7}
        - Date range: {"trade_date_after": "2025-01-01", "trade_date_before": "2025-12-31"}
        - List field contains: {"skills": "cn_macro_news"}

        Args:
            current_situation: The current financial situation to match against
            n_matches: Number of top matches to return
            filters: Optional dict of field -> value filters to apply
            include_metadata: Whether to include metadata in results

        Returns:
            List of dicts with matched_situation, recommendation, and metadata
        """
        if not self.documents:
            return []

        if self.bm25 is None:
            results = []
            for idx in range(min(n_matches, len(self.documents))):
                if filters and not self._match_filters(self.metadata[idx], filters):
                    continue
                result = {
                    "matched_situation": self.documents[idx],
                    "recommendation": self.recommendations[idx],
                    "similarity_score": 0.0,
                }
                if include_metadata:
                    result["metadata"] = self.metadata[idx]
                results.append(result)
            return results

        query_tokens = self._tokenize(current_situation)
        scores = self.bm25.get_scores(query_tokens)

        results = []
        max_score = float(scores.max()) if len(scores) > 0 and scores.max() > 0 else 1.0

        indexed_results = []
        for idx in range(len(self.documents)):
            normalized_score = scores[idx] / max_score if max_score > 0 else 0
            indexed_results.append((idx, normalized_score, scores[idx]))

        indexed_results.sort(key=lambda x: x[1], reverse=True)

        for idx, normalized_score, raw_score in indexed_results:
            if filters:
                if not self._match_filters(self.metadata[idx], filters):
                    continue

            result = {
                "matched_situation": self.documents[idx],
                "recommendation": self.recommendations[idx],
                "similarity_score": normalized_score,
            }

            if include_metadata:
                result["metadata"] = self.metadata[idx]

            results.append(result)

            if len(results) >= n_matches:
                break

        return results

    def _match_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if metadata matches all filter criteria.

        Args:
            metadata: The metadata dict to check
            filters: The filter criteria

        Returns:
            True if all filters match, False otherwise
        """
        for key, value in filters.items():
            meta_value = metadata.get(key)

            # Handle list values (OR match)
            if isinstance(value, list):
                if meta_value is None:
                    return False
                # If metadata value is also a list, check for intersection
                if isinstance(meta_value, list):
                    if not any(v in meta_value for v in value):
                        return False
                elif meta_value not in value:
                    return False

            # Handle numeric range filters
            elif key.endswith("_min"):
                base_field = key[:-4]
                meta_value = metadata.get(base_field)
                if meta_value is None or not isinstance(meta_value, (int, float)):
                    return False
                if meta_value < value:
                    return False
            elif key.endswith("_max"):
                base_field = key[:-4]
                meta_value = metadata.get(base_field)
                if meta_value is None or not isinstance(meta_value, (int, float)):
                    return False
                if meta_value > value:
                    return False

            # Handle date range filters
            elif key.endswith("_after"):
                base_field = key[:-6]
                meta_value = metadata.get(base_field)
                if meta_value is None or not isinstance(meta_value, str):
                    return False
                if meta_value < value:
                    return False
            elif key.endswith("_before"):
                base_field = key[:-7]
                meta_value = metadata.get(base_field)
                if meta_value is None or not isinstance(meta_value, str):
                    return False
                if meta_value > value:
                    return False

            # Handle list field contains (AND match)
            elif isinstance(meta_value, list):
                if value not in meta_value:
                    return False

            # Exact match
            else:
                if meta_value != value:
                    return False

        return True

    def _get_candidates_from_indexes(self, filters: Dict[str, Any]) -> Optional[Set[int]]:
        """Get candidate document IDs from structured indexes for efficiency.

        Uses the pre-built inverted indexes to quickly find candidates
        matching the filter criteria, then falls back to full scan if needed.

        Args:
            filters: The filter criteria

        Returns:
            Set of candidate doc_ids, or None if indexes can't be used
        """
        candidate_sets: List[Set[int]] = []

        for key, value in filters.items():
            # Skip numeric/date range filters - can't use index
            if key.endswith(("_min", "_max", "_after", "_before")):
                return None

            # Skip list field contains checks - can't use index efficiently
            if isinstance(value, str):
                meta_value = None
                for doc_id, meta in enumerate(self.metadata[:1]):
                    if key in meta:
                        meta_value = meta[key]
                        break
                if meta_value is not None and isinstance(meta_value, list):
                    return None

            # Try to use index
            if key in self._structured_index:
                if isinstance(value, list):
                    # OR match - union of sets
                    doc_ids = set()
                    for v in value:
                        str_v = str(v)
                        if str_v in self._structured_index[key]:
                            doc_ids.update(self._structured_index[key][str_v])
                    if doc_ids:
                        candidate_sets.append(doc_ids)
                else:
                    # Exact match
                    str_v = str(value)
                    if str_v in self._structured_index[key]:
                        candidate_sets.append(set(self._structured_index[key][str_v]))
            else:
                # Field not indexed, need full scan
                return None

        if not candidate_sets:
            return set(range(len(self.documents)))

        # Intersection of all candidate sets
        result = candidate_sets[0]
        for s in candidate_sets[1:]:
            result = result.intersection(s)

        return result

    def get_memories_by_field(
        self,
        field: str,
        value: Any,
        n_matches: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get all memories where a specific field matches the value.

        Args:
            field: The metadata field to filter on
            value: The value to match
            n_matches: Maximum number of matches to return

        Returns:
            List of matching memories
        """
        results = []
        for idx, meta in enumerate(self.metadata):
            if meta.get(field) == value:
                results.append({
                    "matched_situation": self.documents[idx],
                    "recommendation": self.recommendations[idx],
                    "metadata": meta,
                })
                if len(results) >= n_matches:
                    break
        return results

    def get_all_by_segment(self, segment: str, n_matches: int = 10) -> List[Dict[str, Any]]:
        """Get all memories for a specific segment.

        Args:
            segment: The segment to filter on (e.g., "cn_main_board_equity")
            n_matches: Maximum number of matches

        Returns:
            List of memories for the segment
        """
        return self.get_memories_by_field("segment", segment, n_matches)

    def get_all_by_route(self, final_route: str, n_matches: int = 10) -> List[Dict[str, Any]]:
        """Get all memories for a specific final route.

        Args:
            final_route: The final route to filter on (e.g., "portfolio_handoff")
            n_matches: Maximum number of matches

        Returns:
            List of memories for the route
        """
        return self.get_memories_by_field("final_route", final_route, n_matches)

    def get_recent_memories(
        self,
        n: int = 10,
        segment: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get the most recent memories, optionally filtered by segment.

        Assumes memories are stored in chronological order.

        Args:
            n: Number of recent memories to return
            segment: Optional segment filter

        Returns:
            List of recent memories
        """
        results = []
        # Iterate in reverse order (most recent first)
        for idx in range(len(self.documents) - 1, -1, -1):
            if segment and self.metadata[idx].get("segment") != segment:
                continue

            results.append({
                "matched_situation": self.documents[idx],
                "recommendation": self.recommendations[idx],
                "metadata": self.metadata[idx],
            })

            if len(results) >= n:
                break

        return results

    def get_high_performing_routes(
        self,
        min_quality: str = "good",
        segment: Optional[str] = None,
        n: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get routes that led to high-quality decisions.

        Args:
            min_quality: Minimum quality threshold ("good", "neutral")
            segment: Optional segment filter
            n: Maximum number of results

        Returns:
            List of high-performing route memories
        """
        quality_rank = {"good": 2, "neutral": 1, "poor": 0}
        min_rank = quality_rank.get(min_quality, 0)

        results = []
        for idx, meta in enumerate(self.metadata):
            quality = meta.get("decision_quality", "unknown")
            if quality_rank.get(quality, 0) < min_rank:
                continue
            if segment and meta.get("segment") != segment:
                continue

            results.append({
                "matched_situation": self.documents[idx],
                "recommendation": self.recommendations[idx],
                "metadata": meta,
                "decision_quality": quality,
            })

        # Sort by decision quality
        results.sort(key=lambda x: quality_rank.get(x.get("decision_quality", "unknown"), 0), reverse=True)
        return results[:n]
