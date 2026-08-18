"""Financial situation memory using BM25 for lexical similarity matching.

Uses BM25 (Best Matching 25) algorithm for retrieval - no API calls,
no token limits, works offline with any LLM provider.
"""

try:  # pragma: no cover - optional retrieval dependency
    from rank_bm25 import BM25Okapi
except Exception:  # pragma: no cover
    BM25Okapi = None
from typing import List, Tuple, Dict, Any, Optional
from typing_extensions import TypedDict, NotRequired
import re
import json
from datetime import datetime


class OrchestrationMemoryEntry(TypedDict, total=False):
    """Structure化编排记忆条目 schema.

    定义存储在 StructuredMemory 中的编排记忆的结构化字段，
    支持结构化查询和过滤。
    """

    # ===== 核心内容 =====
    situation: str                          # 情境描述（原文）
    recommendation: str                    # 建议/洞察（原文）

    # ===== 编排上下文 - 结构化字段 =====
    stage_sequence: List[str]               # 阶段序列: ["analyst", "research", "trader", "risk"]
    phase_sequence: List[str]               # 相位序列: ["analyst_market", "analyst_news", ...]
    compression_phases: List[str]           # 触发压缩的阶段
    compression_rate: float                 # 压缩比率 (0.0 - 1.0)

    # ===== 工具/上下文 =====
    segment: str                            # 板块: "cn_main_board" | "cn_chinext" | "cn_star" | "cn_bse"
    style_bucket: str                       # 风格: "dividend" | "growth" | "value" | "momentum"
    selected_analysts: List[str]           # 启用的分析师
    skills: List[str]                        # 启用的技能

    # ===== 路由结果 =====
    final_route: str                        # 最终路由: "direct" | "compression_handoff" | "portfolio_handoff"
    final_reason: str                       # 路由选择原因
    route_category: str                     # 路由类别: "normal" | "mixed" | "complex"

    # ===== 事件轨迹统计 =====
    total_events: int                       # 总事件数
    unique_stages: List[str]               # 访问的唯一阶段列表
    bottleneck_stages: List[str]           # 瓶颈阶段（重复访问）

    # ===== 标的 =====
    ticker: str                             # 股票代码
    company_name: str                       # 公司名称

    # ===== 时间戳 =====
    trade_date: str                         # 交易日期 (yyyy-mm-dd)
    created_at: str                         # 创建时间 (ISO format)

    # ===== 结果评估（事后填入）=====
    actual_return: NotRequired[float]           # 实际收益率
    decision_quality: NotRequired[str]         # 决策质量: "good" | "neutral" | "poor"

    # ===== 额外上下文 =====
    sector_tools_used: NotRequired[List[str]]  # 使用的行业工具
    macro_tools_used: NotRequired[List[str]]   # 使用的宏观工具
    event_tools_used: NotRequired[List[str]]    # 使用的事件工具


class StructuredMemory:
    """Enhanced memory system that supports structured fields in addition to text.

    Extends FinancialSituationMemory with structured metadata that can be
    used for filtering and structured retrieval. Supports fast lookups by
    segment, style_bucket, route_category, trade_date, and other fields
    via pre-built inverted indexes.
    """

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

    def _get_candidates_from_indexes(self, filters: Dict[str, Any]) -> Optional[set]:
        """Get candidate document IDs from structured indexes for efficiency.

        Uses the pre-built inverted indexes to quickly find candidates
        matching the filter criteria, then falls back to full scan if needed.

        Args:
            filters: The filter criteria

        Returns:
            Set of candidate doc_ids, or None if indexes can't be used
        """
        candidate_sets: List[set] = []

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

    def get_route_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored route patterns.

        Returns:
            Dict with route distribution and segment distribution
        """
        route_counts: Dict[str, int] = {}
        segment_counts: Dict[str, int] = {}
        compression_counts = {"with_compression": 0, "without_compression": 0}
        route_category_counts: Dict[str, int] = {}
        decision_quality_counts: Dict[str, int] = {}

        for meta in self.metadata:
            route = meta.get("final_route", "unknown")
            segment = meta.get("segment", "unknown")
            compression_triggered = meta.get("compression_triggered", False)
            route_category = meta.get("route_category", "unknown")
            decision_quality = meta.get("decision_quality", "unknown")

            route_counts[route] = route_counts.get(route, 0) + 1
            segment_counts[segment] = segment_counts.get(segment, 0) + 1
            route_category_counts[route_category] = route_category_counts.get(route_category, 0) + 1
            decision_quality_counts[decision_quality] = decision_quality_counts.get(decision_quality, 0) + 1

            if compression_triggered:
                compression_counts["with_compression"] += 1
            else:
                compression_counts["without_compression"] += 1

        # Calculate average compression rate
        total_compression_rate = 0
        compression_rate_count = 0
        for meta in self.metadata:
            if "compression_rate" in meta:
                total_compression_rate += meta["compression_rate"]
                compression_rate_count += 1

        avg_compression_rate = total_compression_rate / compression_rate_count if compression_rate_count > 0 else 0

        return {
            "total_memories": len(self.documents),
            "route_distribution": route_counts,
            "segment_distribution": segment_counts,
            "route_category_distribution": route_category_counts,
            "decision_quality_distribution": decision_quality_counts,
            "compression_stats": compression_counts,
            "avg_compression_rate": avg_compression_rate,
        }

    def get_route_statistics_by_segment(
        self,
        segment: Optional[str] = None,
        style_bucket: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get detailed route statistics filtered by segment/style.

        Args:
            segment: Optional segment to filter on
            style_bucket: Optional style bucket to filter on

        Returns:
            Dict with filtered route statistics
        """
        filtered_meta = []
        for meta in self.metadata:
            if segment and meta.get("segment") != segment:
                continue
            if style_bucket and meta.get("style_bucket") != style_bucket:
                continue
            filtered_meta.append(meta)

        if not filtered_meta:
            return {
                "total_memories": 0,
                "segment": segment or "all",
                "style_bucket": style_bucket or "all",
            }

        route_counts: Dict[str, int] = {}
        compression_rates = []
        decision_quality_counts: Dict[str, int] = {"good": 0, "neutral": 0, "poor": 0}

        for meta in filtered_meta:
            route = meta.get("final_route", "unknown")
            route_counts[route] = route_counts.get(route, 0) + 1

            if "compression_rate" in meta:
                compression_rates.append(meta["compression_rate"])

            quality = meta.get("decision_quality", "unknown")
            if quality in decision_quality_counts:
                decision_quality_counts[quality] += 1

        return {
            "total_memories": len(filtered_meta),
            "segment": segment or "all",
            "style_bucket": style_bucket or "all",
            "route_distribution": route_counts,
            "decision_quality_distribution": decision_quality_counts,
            "avg_compression_rate": sum(compression_rates) / len(compression_rates) if compression_rates else 0,
            "compression_rate_min": min(compression_rates) if compression_rates else 0,
            "compression_rate_max": max(compression_rates) if compression_rates else 0,
        }

    def get_pattern_outcome_correlation(
        self,
        pattern_type: str,
    ) -> Dict[str, Any]:
        """Get outcome correlation for a specific pattern type.

        Analyzes which outcomes (decision_quality) are associated with
        a specific route pattern type.

        Args:
            pattern_type: The pattern type to analyze:
                - "compression_handoff": Routes with compression
                - "direct": Routes without compression
                - "high_compression": compression_rate >= 0.5
                - "low_compression": compression_rate < 0.3

        Returns:
            Dict with pattern analysis and outcome correlation
        """
        pattern_memories = []
        for meta in self.metadata:
            if pattern_type == "compression_handoff":
                if meta.get("compression_triggered", False):
                    pattern_memories.append(meta)
            elif pattern_type == "direct":
                if not meta.get("compression_triggered", False):
                    pattern_memories.append(meta)
            elif pattern_type == "high_compression":
                if meta.get("compression_rate", 0) >= 0.5:
                    pattern_memories.append(meta)
            elif pattern_type == "low_compression":
                if 0 < meta.get("compression_rate", 1) < 0.3:
                    pattern_memories.append(meta)

        if not pattern_memories:
            return {
                "pattern_type": pattern_type,
                "count": 0,
                "outcome_distribution": {},
                "correlation": "No data available",
            }

        outcome_counts: Dict[str, int] = {"good": 0, "neutral": 0, "poor": 0}
        for mem in pattern_memories:
            quality = mem.get("decision_quality", "unknown")
            if quality in outcome_counts:
                outcome_counts[quality] += 1

        total = len(pattern_memories)
        outcome_percentages = {k: v / total * 100 for k, v in outcome_counts.items()}

        # Determine correlation
        if outcome_counts["good"] > outcome_counts["poor"] * 1.5:
            correlation = "Positive - This pattern tends to produce good outcomes"
        elif outcome_counts["poor"] > outcome_counts["good"] * 1.5:
            correlation = "Negative - This pattern tends to produce poor outcomes"
        else:
            correlation = "Neutral - No significant correlation"

        return {
            "pattern_type": pattern_type,
            "count": total,
            "outcome_distribution": outcome_counts,
            "outcome_percentages": outcome_percentages,
            "correlation": correlation,
        }

    def get_route_efficiency_trends(
        self,
        segment: Optional[str] = None,
        style_bucket: Optional[str] = None,
        date_range: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """Analyze route efficiency trends over time.

        Calculates efficiency metrics and trends based on stored route memories.
        Efficiency score is computed from compression_rate and bottleneck_stages.

        Args:
            segment: Optional segment filter (e.g., "cn_main_board_equity")
            style_bucket: Optional style bucket filter (e.g., "growth_style_candidate")
            date_range: Optional tuple of (trade_date_after, trade_date_before)

        Returns:
            Dictionary containing:
            {
                "total_memories": int,
                "avg_efficiency_score": float,
                "efficiency_by_route": Dict[str, float],
                "efficiency_by_route_category": Dict[str, float],
                "efficiency_by_segment": Dict[str, float],
                "avg_compression_rate": float,
                "avg_bottleneck_count": float,
                "trend": str,  # "improving" | "stable" | "declining" | "insufficient_data"
                "has_sufficient_data": bool,
                "insights": List[str],
            }
        """
        if not self.metadata:
            return {
                "total_memories": 0,
                "avg_efficiency_score": 0.0,
                "efficiency_by_route": {},
                "efficiency_by_route_category": {},
                "efficiency_by_segment": {},
                "avg_compression_rate": 0.0,
                "avg_bottleneck_count": 0.0,
                "trend": "insufficient_data",
                "has_sufficient_data": False,
                "insights": ["No route memories available for analysis"],
            }

        # Filter memories by criteria
        filtered_indices = []
        for idx, meta in enumerate(self.metadata):
            # Segment filter
            if segment and meta.get("segment") != segment:
                continue

            # Style bucket filter
            if style_bucket and meta.get("style_bucket") != style_bucket:
                continue

            # Date range filter
            if date_range:
                trade_date = meta.get("trade_date", "")
                if trade_date:
                    after_date, before_date = date_range
                    if after_date and trade_date < after_date:
                        continue
                    if before_date and trade_date > before_date:
                        continue

            filtered_indices.append(idx)

        if not filtered_indices:
            return {
                "total_memories": 0,
                "avg_efficiency_score": 0.0,
                "efficiency_by_route": {},
                "efficiency_by_route_category": {},
                "efficiency_by_segment": {},
                "avg_compression_rate": 0.0,
                "avg_bottleneck_count": 0.0,
                "trend": "insufficient_data",
                "has_sufficient_data": False,
                "insights": ["No memories match the specified filters"],
            }

        # Calculate efficiency scores for each memory
        efficiency_scores = []
        compression_rates = []
        bottleneck_counts = []
        route_efficiencies: Dict[str, List[float]] = {}
        category_efficiencies: Dict[str, List[float]] = {}
        segment_efficiencies: Dict[str, List[float]] = {}

        for idx in filtered_indices:
            meta = self.metadata[idx]

            # Calculate efficiency score (same formula as in reflection.py)
            compression_rate = meta.get("compression_rate", 0.0)
            bottleneck_stages = meta.get("bottleneck_stages", [])
            revisit_ratio = meta.get("revisit_ratio", 1.0)
            has_early_handoff = meta.get("has_early_handoff", False)

            efficiency = 1.0
            efficiency -= len(bottleneck_stages) * 0.1
            efficiency -= compression_rate * 0.5
            if revisit_ratio > 1.0:
                efficiency -= (revisit_ratio - 1.0) * 0.05
            if has_early_handoff:
                efficiency -= 0.05
            efficiency = max(0.1, min(1.0, efficiency))

            efficiency_scores.append(efficiency)
            compression_rates.append(compression_rate)
            bottleneck_counts.append(len(bottleneck_stages))

            # Group by route
            final_route = meta.get("final_route", "unknown")
            if final_route not in route_efficiencies:
                route_efficiencies[final_route] = []
            route_efficiencies[final_route].append(efficiency)

            # Group by route category
            route_category = meta.get("route_category", "unknown")
            if route_category not in category_efficiencies:
                category_efficiencies[route_category] = []
            category_efficiencies[route_category].append(efficiency)

            # Group by segment
            mem_segment = meta.get("segment", "unknown")
            if mem_segment not in segment_efficiencies:
                segment_efficiencies[mem_segment] = []
            segment_efficiencies[mem_segment].append(efficiency)

        # Calculate averages
        avg_efficiency = sum(efficiency_scores) / len(efficiency_scores) if efficiency_scores else 0.0
        avg_compression = sum(compression_rates) / len(compression_rates) if compression_rates else 0.0
        avg_bottleneck = sum(bottleneck_counts) / len(bottleneck_counts) if bottleneck_counts else 0.0

        # Calculate efficiency by route/category/segment
        efficiency_by_route = {
            route: sum(scores) / len(scores)
            for route, scores in route_efficiencies.items()
        }
        efficiency_by_category = {
            cat: sum(scores) / len(scores)
            for cat, scores in category_efficiencies.items()
        }
        efficiency_by_segment = {
            seg: sum(scores) / len(scores)
            for seg, scores in segment_efficiencies.items()
        }

        # Determine trend (need at least 5 memories for meaningful trend)
        trend = "insufficient_data"
        has_sufficient_data = len(efficiency_scores) >= 5

        if has_sufficient_data:
            # Sort by trade_date to calculate trend
            dated_scores: List[Tuple[str, float]] = []
            for idx in filtered_indices:
                trade_date = self.metadata[idx].get("trade_date", "")
                if trade_date:
                    dated_scores.append((trade_date, efficiency_scores[filtered_indices.index(idx)]))
            dated_scores.sort(key=lambda x: x[0])

            if len(dated_scores) >= 5:
                # Compare first half vs second half
                mid = len(dated_scores) // 2
                first_half_avg = sum(s for _, s in dated_scores[:mid]) / mid
                second_half_avg = sum(s for _, s in dated_scores[mid:]) / (len(dated_scores) - mid)

                if second_half_avg - first_half_avg > 0.05:
                    trend = "improving"
                elif first_half_avg - second_half_avg > 0.05:
                    trend = "declining"
                else:
                    trend = "stable"

        # Generate insights
        insights: List[str] = []

        # Best and worst routes
        if efficiency_by_route:
            best_route = max(efficiency_by_route.items(), key=lambda x: x[1])
            worst_route = min(efficiency_by_route.items(), key=lambda x: x[1])
            insights.append(f"最有效率的路由: {best_route[0]} (得分: {best_route[1]:.2f})")
            insights.append(f"效率最低的路由: {worst_route[0]} (得分: {worst_route[1]:.2f})")

        # Compression impact
        no_compression = [e for i, e in enumerate(efficiency_scores)
                         if filtered_indices[i] < len(self.metadata) and
                         not self.metadata[filtered_indices[i]].get("compression_triggered", False)]
        with_compression = [e for i, e in enumerate(efficiency_scores)
                           if filtered_indices[i] < len(self.metadata) and
                           self.metadata[filtered_indices[i]].get("compression_triggered", False)]

        if no_compression and with_compression:
            avg_no_comp = sum(no_compression) / len(no_compression)
            avg_with_comp = sum(with_compression) / len(with_compression)
            if avg_no_comp > avg_with_comp:
                insights.append(f"无压缩路径平均效率 ({avg_no_comp:.2f}) 高于有压缩路径 ({avg_with_comp:.2f})")
            else:
                insights.append(f"有压缩路径平均效率 ({avg_with_comp:.2f}) 高于无压缩路径 ({avg_no_comp:.2f})")

        # Trend insight
        if trend == "improving":
            insights.append("路由效率呈改善趋势")
        elif trend == "declining":
            insights.append("警告: 路由效率呈下降趋势，需要关注")
        elif trend == "stable":
            insights.append("路由效率保持稳定")

        return {
            "total_memories": len(filtered_indices),
            "avg_efficiency_score": round(avg_efficiency, 3),
            "efficiency_by_route": {k: round(v, 3) for k, v in efficiency_by_route.items()},
            "efficiency_by_route_category": {k: round(v, 3) for k, v in efficiency_by_category.items()},
            "efficiency_by_segment": {k: round(v, 3) for k, v in efficiency_by_segment.items()},
            "avg_compression_rate": round(avg_compression, 3),
            "avg_bottleneck_count": round(avg_bottleneck, 2),
            "trend": trend,
            "has_sufficient_data": has_sufficient_data,
            "insights": insights,
        }

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


class FinancialSituationMemory:
    """Memory system for storing and retrieving financial situations using BM25."""

    def __init__(self, name: str, config: dict = None):
        """Initialize the memory system.

        Args:
            name: Name identifier for this memory instance
            config: Configuration dict (kept for API compatibility, not used for BM25)
        """
        self.name = name
        self.documents: List[str] = []
        self.recommendations: List[str] = []
        self.bm25 = None

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25 indexing.

        Simple whitespace + punctuation tokenization with lowercasing.
        """
        # Lowercase and split on non-alphanumeric characters
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens

    def _rebuild_index(self):
        """Rebuild the BM25 index after adding documents."""
        if self.documents:
            tokenized_docs = [self._tokenize(doc) for doc in self.documents]
            self.bm25 = BM25Okapi(tokenized_docs) if BM25Okapi is not None else None
        else:
            self.bm25 = None

    def add_situations(self, situations_and_advice: List[Tuple[str, str]]):
        """Add financial situations and their corresponding advice.

        Args:
            situations_and_advice: List of tuples (situation, recommendation)
        """
        for situation, recommendation in situations_and_advice:
            self.documents.append(situation)
            self.recommendations.append(recommendation)

        # Rebuild BM25 index with new documents
        self._rebuild_index()

    def get_memories(self, current_situation: str, n_matches: int = 1) -> List[dict]:
        """Find matching recommendations using BM25 similarity.

        Args:
            current_situation: The current financial situation to match against
            n_matches: Number of top matches to return

        Returns:
            List of dicts with matched_situation, recommendation, and similarity_score
        """
        if not self.documents:
            return []
        if self.bm25 is None:
            return [
                {
                    "matched_situation": self.documents[idx],
                    "recommendation": self.recommendations[idx],
                    "similarity_score": 0.0,
                }
                for idx in range(min(n_matches, len(self.documents)))
            ]

        # Tokenize query
        query_tokens = self._tokenize(current_situation)

        # Get BM25 scores for all documents
        scores = self.bm25.get_scores(query_tokens)

        # Get top-n indices sorted by score (descending)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n_matches]

        # Build results
        results = []
        max_score = float(scores.max()) if len(scores) > 0 and scores.max() > 0 else 1.0

        for idx in top_indices:
            # Normalize score to 0-1 range for consistency
            normalized_score = scores[idx] / max_score if max_score > 0 else 0
            results.append({
                "matched_situation": self.documents[idx],
                "recommendation": self.recommendations[idx],
                "similarity_score": normalized_score,
            })

        return results

    def clear(self):
        """Clear all stored memories."""
        self.documents = []
        self.recommendations = []
        self.bm25 = None


if __name__ == "__main__":
    # Example usage
    matcher = FinancialSituationMemory("test_memory")

    # Example data
    example_data = [
        (
            "High inflation rate with rising interest rates and declining consumer spending",
            "Consider defensive sectors like consumer staples and utilities. Review fixed-income portfolio duration.",
        ),
        (
            "Tech sector showing high volatility with increasing institutional selling pressure",
            "Reduce exposure to high-growth tech stocks. Look for value opportunities in established tech companies with strong cash flows.",
        ),
        (
            "Strong dollar affecting emerging markets with increasing forex volatility",
            "Hedge currency exposure in international positions. Consider reducing allocation to emerging market debt.",
        ),
        (
            "Market showing signs of sector rotation with rising yields",
            "Rebalance portfolio to maintain target allocations. Consider increasing exposure to sectors benefiting from higher rates.",
        ),
    ]

    # Add the example situations and recommendations
    matcher.add_situations(example_data)

    # Example query
    current_situation = """
    Market showing increased volatility in tech sector, with institutional investors
    reducing positions and rising interest rates affecting growth stock valuations
    """

    try:
        recommendations = matcher.get_memories(current_situation, n_matches=2)

        for i, rec in enumerate(recommendations, 1):
            print(f"\nMatch {i}:")
            print(f"Similarity Score: {rec['similarity_score']:.2f}")
            print(f"Matched Situation: {rec['matched_situation']}")
            print(f"Recommendation: {rec['recommendation']}")

    except Exception as e:
        print(f"Error during recommendation: {str(e)}")
