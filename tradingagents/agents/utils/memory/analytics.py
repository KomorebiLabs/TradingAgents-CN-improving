"""Memory analytics mixin (split from memory.py — refactor/merger-pipeline style).

`AnalyticsMixin` provides statistics and trend analysis over stored route
memories.  Read-only over StoreMixin state; no inter-mixin imports.
"""

from typing import Any, Dict, List, Optional, Tuple


class AnalyticsMixin:
    """Statistics/trend methods (assumes StoreMixin state)."""

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
