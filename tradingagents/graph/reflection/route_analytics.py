"""Route analytics (split from reflection.py — refactor/merger-pipeline style).

Pure functions over the event trail / current state: efficiency analysis,
pattern identification, historical comparison, route summary.  No LLM calls
(including `_generate_llm_route_insight`, which despite its name is a plain
template formatter — recorded as a naming fossil, kept verbatim).
"""

from typing import Any, Dict, List, Optional

from .extraction import (
    _extract_event_trail,
    _extract_route_decision,
    _extract_semantic_trigger_audit,
)


def _analyze_route_patterns(event_trail: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze patterns in the route taken.

    Args:
        event_trail: List of orchestration events

    Returns:
        Dictionary with route pattern analysis
    """
    if not event_trail:
        return {
            "total_events": 0,
            "compression_count": 0,
            "phases_visited": [],
            "handoff_occurred": False,
            "avg_context_per_phase": {},
        }

    compression_events = [e for e in event_trail if e.get("compression_triggered")]
    phases = [e.get("phase", "") for e in event_trail if e.get("phase")]

    phase_contexts: Dict[str, List[int]] = {}
    for event in event_trail:
        phase = event.get("phase", "")
        if phase:
            phase_contexts.setdefault(phase, []).append(event.get("context_estimate", 0))

    avg_context: Dict[str, float] = {}
    for phase, contexts in phase_contexts.items():
        if contexts:
            avg_context[phase] = sum(contexts) / len(contexts)

    return {
        "total_events": len(event_trail),
        "compression_count": len(compression_events),
        "phases_visited": list(dict.fromkeys(phases)),
        "handoff_occurred": any("_handoff" in e.get("node", "") for e in event_trail),
        "avg_context_per_phase": avg_context,
        "compression_rate": len(compression_events) / len(event_trail) if event_trail else 0,
    }


def analyze_route_efficiency(event_trail: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze route efficiency from event trail.

    Quantifies how efficient the execution route was based on:
    - Compression rate (higher compression = lower efficiency)
    - Bottleneck stages (repeated visits = lower efficiency)
    - Context estimate distribution

    Args:
        event_trail: List of orchestration events

    Returns:
        Dictionary containing efficiency metrics:
        {
            "total_events": int,
            "unique_stages": List[str],
            "stage_counts": Dict[str, int],
            "compression_count": int,
            "compression_rate": float,
            "efficiency_score": float,  # 0-1, higher is better
            "bottleneck_stages": List[str],
            "avg_context_per_event": float,
            "has_early_handoff": bool,
            "revisit_ratio": float,  # total_events / unique_stages
        }
    """
    if not event_trail:
        return {
            "total_events": 0,
            "unique_stages": [],
            "stage_counts": {},
            "compression_count": 0,
            "compression_rate": 0.0,
            "efficiency_score": 1.0,
            "bottleneck_stages": [],
            "avg_context_per_event": 0.0,
            "has_early_handoff": False,
            "revisit_ratio": 0.0,
        }

    # Extract stage sequence
    stage_sequence = [e.get("stage", "") for e in event_trail if e.get("stage")]
    unique_stages = list(dict.fromkeys(stage_sequence))

    # Count stage visits
    stage_counts: Dict[str, int] = {}
    for stage in stage_sequence:
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    # Compression statistics
    compression_count = sum(1 for e in event_trail if e.get("compression_triggered"))
    compression_rate = compression_count / len(event_trail) if event_trail else 0.0

    # Identify bottleneck stages (visited 2+ times)
    bottleneck_stages = [s for s, count in stage_counts.items() if count >= 2]

    # Calculate average context estimate
    context_estimates = [e.get("context_estimate", 0) for e in event_trail]
    avg_context = sum(context_estimates) / len(context_estimates) if context_estimates else 0.0

    # Check for early handoff (compression in first 3 events)
    has_early_handoff = any(
        e.get("compression_triggered", False)
        for i, e in enumerate(event_trail[:3])
    )

    # Calculate revisit ratio
    revisit_ratio = len(event_trail) / len(unique_stages) if unique_stages else 0.0

    # Calculate efficiency score (0-1, higher is better)
    # Base score of 1.0, with penalties
    efficiency_score = 1.0

    # Penalty for bottleneck stages (each bottleneck stage reduces score by 0.1)
    efficiency_score -= len(bottleneck_stages) * 0.1

    # Penalty for high compression rate (each 10% compression reduces score by 0.05)
    efficiency_score -= compression_rate * 0.5

    # Penalty for high revisit ratio (each extra visit reduces score by 0.05)
    if revisit_ratio > 1.0:
        efficiency_score -= (revisit_ratio - 1.0) * 0.05

    # Penalty for early handoff
    if has_early_handoff:
        efficiency_score -= 0.05

    # Clamp to [0.1, 1.0] range
    efficiency_score = max(0.1, min(1.0, efficiency_score))

    return {
        "total_events": len(event_trail),
        "unique_stages": unique_stages,
        "stage_counts": stage_counts,
        "compression_count": compression_count,
        "compression_rate": compression_rate,
        "efficiency_score": round(efficiency_score, 3),
        "bottleneck_stages": bottleneck_stages,
        "avg_context_per_event": round(avg_context, 2),
        "has_early_handoff": has_early_handoff,
        "revisit_ratio": round(revisit_ratio, 2),
    }


def identify_route_patterns(event_trail: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identify common route patterns from event trail.

    Recognizes patterns like:
    - "all_direct": No compression at all
    - "early_compression": Compression triggered in first third of events
    - "late_compression": Compression triggered in last third of events
    - "interleaved": Compression and non-compression events alternate
    - "high_compression": High compression rate (>= 0.5)
    - "bottleneck_loop": Repeated visits to same stage

    Args:
        event_trail: List of orchestration events

    Returns:
        List of pattern dictionaries:
        [{
            "pattern_type": str,
            "description": str,
            "characteristics": List[str],
            "is_efficient": bool,
        }]
    """
    if not event_trail:
        return []

    patterns: List[Dict[str, Any]] = []
    compression_events = [e for e in event_trail if e.get("compression_triggered")]
    compression_rate = len(compression_events) / len(event_trail) if event_trail else 0.0

    # Extract stage sequence for bottleneck detection
    stage_sequence = [e.get("stage", "") for e in event_trail]
    stage_counts: Dict[str, int] = {}
    for stage in stage_sequence:
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
    bottleneck_stages = [s for s, count in stage_counts.items() if count >= 2]

    # Pattern: all_direct
    if compression_rate == 0:
        patterns.append({
            "pattern_type": "all_direct",
            "description": "全程无压缩，直接传递上下文",
            "characteristics": [
                f"总事件数: {len(event_trail)}",
                "无压缩触发",
                "上下文完整传递",
            ],
            "is_efficient": True,
        })

    # Pattern: high_compression
    if compression_rate >= 0.5:
        patterns.append({
            "pattern_type": "high_compression",
            "description": "高压缩率路径（≥50%的事件触发压缩）",
            "characteristics": [
                f"压缩率: {compression_rate:.1%}",
                f"压缩事件数: {len(compression_events)}/{len(event_trail)}",
                "可能导致信息丢失",
            ],
            "is_efficient": False,
        })

    # Pattern: bottleneck_loop
    if bottleneck_stages:
        patterns.append({
            "pattern_type": "bottleneck_loop",
            "description": "存在重复访问的瓶颈阶段",
            "characteristics": [
                f"瓶颈阶段: {', '.join(bottleneck_stages)}",
                f"访问次数: {[(s, stage_counts[s]) for s in bottleneck_stages]}",
                "可能需要优化流程或缓存",
            ],
            "is_efficient": False,
        })

    # Helper: get position of event in trail
    def get_event_position(e: Dict[str, Any]) -> int:
        """Get the position of an event in the original trail."""
        for i, te in enumerate(event_trail):
            if te is e:
                return i
        return -1

    # Pattern: early_compression
    if compression_events and len(event_trail) >= 3:
        early_threshold = len(event_trail) // 3
        # Check if ALL compression events are in the early third of the trail
        early_compressions = [
            e for e in compression_events
            if get_event_position(e) < early_threshold
        ]
        # All compressions must be early, and there must be at least one
        if len(early_compressions) == len(compression_events) and len(early_compressions) >= 1:
            patterns.append({
                "pattern_type": "early_compression",
                "description": "早期压缩后直行",
                "characteristics": [
                    f"全部 {len(compression_events)} 个压缩事件都在前 {early_threshold} 个事件中",
                    "后续无额外压缩",
                    "可能存在上下文过长问题",
                ],
                "is_efficient": False,
            })

    # Pattern: late_compression
    if compression_events and len(event_trail) >= 3:
        late_threshold = (2 * len(event_trail)) // 3
        # Check if ALL compression events are in the late third of the trail
        late_compressions = [
            e for e in compression_events
            if get_event_position(e) >= late_threshold
        ]
        # All compressions must be late, and there must be at least one
        if len(late_compressions) == len(compression_events) and len(late_compressions) >= 1:
            patterns.append({
                "pattern_type": "late_compression",
                "description": "后期才触发压缩",
                "characteristics": [
                    f"全部 {len(compression_events)} 个压缩事件都在后 {len(event_trail) - late_threshold} 个事件中",
                    "早期阶段上下文完整",
                    "后期可能遇到上下文限制",
                ],
                "is_efficient": True,
            })

    # Pattern: interleaved
    if len(compression_events) >= 2 and compression_rate > 0 and compression_rate < 1:
        # Check if compression and non-compression events alternate
        is_interleaved = False
        for i in range(len(event_trail) - 1):
            curr_compressed = event_trail[i].get("compression_triggered", False)
            next_compressed = event_trail[i + 1].get("compression_triggered", False)
            if curr_compressed != next_compressed:
                is_interleaved = True
                break

        if is_interleaved:
            patterns.append({
                "pattern_type": "interleaved",
                "description": "压缩与非压缩事件交替出现",
                "characteristics": [
                    "上下文长度波动",
                    "决策路径不稳定",
                    "可能需要统一压缩策略",
                ],
                "is_efficient": False,
            })

    # Pattern: mixed (if has both compressed and non-compressed events but not caught by early/late)
    if compression_events and len(compression_events) < len(event_trail):
        # Check if already caught by early or late compression patterns
        pattern_types = [p["pattern_type"] for p in patterns]
        if "early_compression" not in pattern_types and "late_compression" not in pattern_types:
            # Determine compression timing
            first_compression_pos = min(
                get_event_position(e) for e in compression_events
            )
            total_events = len(event_trail)
            timing_description = (
                "前期压缩" if first_compression_pos < total_events // 3
                else "中期压缩" if first_compression_pos < 2 * total_events // 3
                else "后期压缩"
            )

            patterns.append({
                "pattern_type": "mixed",
                "description": f"混合压缩路径（{timing_description}）",
                "characteristics": [
                    f"压缩: {len(compression_events)} 事件",
                    f"非压缩: {len(event_trail) - len(compression_events)} 事件",
                    f"压缩率: {compression_rate:.1%}",
                    f"首次压缩位置: 第 {first_compression_pos + 1} 个事件",
                ],
                "is_efficient": compression_rate < 0.5,
            })

    return patterns


def _compare_with_historical_memories(
    current_efficiency: Dict[str, Any],
    current_segment: str,
    current_style: str,
    current_route: str,
    historical_memories: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compare current route with historical memories.

    Args:
        current_efficiency: Current route efficiency metrics
        current_segment: Current segment
        current_style: Current style bucket
        current_route: Current final route
        historical_memories: List of historical route memories

    Returns:
        Dictionary with comparison results
    """
    if not historical_memories:
        return {
            "has_sufficient_data": False,
            "similar_cases_found": 0,
            "efficiency_comparison": None,
        }

    # Find similar cases (same segment or style)
    similar_cases = []
    for mem in historical_memories:
        meta = mem.get("metadata", {})
        if current_segment and meta.get("segment") == current_segment:
            similar_cases.append(meta)
        elif current_style and meta.get("style_bucket") == current_style:
            similar_cases.append(meta)

    if len(similar_cases) < 3:
        return {
            "has_sufficient_data": False,
            "similar_cases_found": len(similar_cases),
            "efficiency_comparison": None,
        }

    # Calculate average efficiency from historical data
    # Note: historical memories may not have efficiency_score directly,
    # so we compute it from compression_rate and other metrics
    historical_efficiencies = []
    for meta in similar_cases:
        compression_rate = meta.get("compression_rate", 0)
        bottleneck_stages = meta.get("bottleneck_stages", [])
        # Simple efficiency calculation (inverse of compression + bottleneck penalty)
        eff = 1.0 - (compression_rate * 0.5) - (len(bottleneck_stages) * 0.1)
        historical_efficiencies.append(max(0.1, min(1.0, eff)))

    avg_historical_efficiency = sum(historical_efficiencies) / len(historical_efficiencies)
    current_efficiency_score = current_efficiency.get("efficiency_score", 0.5)

    diff_percent = ((current_efficiency_score - avg_historical_efficiency) / avg_historical_efficiency) * 100

    return {
        "has_sufficient_data": True,
        "similar_cases_found": len(similar_cases),
        "avg_historical_efficiency": round(avg_historical_efficiency, 3),
        "current_efficiency": round(current_efficiency_score, 3),
        "efficiency_comparison": {
            "is_better_than_average": diff_percent > 10,
            "is_worse_than_average": diff_percent < -10,
            "diff_percent": round(diff_percent, 1),
        },
    }


def _generate_llm_route_insight(
    route_efficiency: Dict[str, Any],
    patterns: List[Dict[str, Any]],
    segment: str,
    style_bucket: str,
    final_route: str,
    final_reason: str,
    helpful_patterns: List[str],
    harmful_patterns: List[str],
    recommendations: List[str],
) -> str:
    """Generate LLM-based route insight text.

    NOTE (naming fossil, kept verbatim): despite the name and docstring,
    this function performs NO LLM call — it builds a template context
    string.  Recorded in the behavior-notes, not changed.

    Args:
        route_efficiency: Route efficiency metrics
        patterns: Detected patterns
        segment: Current segment
        style_bucket: Current style bucket
        final_route: Final route taken
        final_reason: Reason for final route
        helpful_patterns: List of helpful patterns
        harmful_patterns: List of harmful patterns
        recommendations: List of recommendations

    Returns:
        String containing LLM-generated insight
    """
    # Build context for LLM
    pattern_summary = ", ".join([p["pattern_type"] for p in patterns]) if patterns else "无"
    helpful = ", ".join(helpful_patterns) if helpful_patterns else "无"
    harmful = ", ".join(harmful_patterns) if harmful_patterns else "无"
    recs = "; ".join(recommendations) if recommendations else "保持现状"

    context = f"""路由效率分析报告

【基本信息】
- 板块: {segment or '未知'}
- 风格: {style_bucket or '未知'}
- 最终路由: {final_route or '未知'}
- 路由原因: {final_reason or '未知'}

【效率指标】
- 效率得分: {route_efficiency.get('efficiency_score', 0):.2f}/1.0
- 压缩率: {route_efficiency.get('compression_rate', 0):.1%}
- 总事件数: {route_efficiency.get('total_events', 0)}
- 唯一阶段数: {len(route_efficiency.get('unique_stages', []))}
- 瓶颈阶段: {', '.join(route_efficiency.get('bottleneck_stages', [])) or '无'}

【检测到的模式】
{pattern_summary}

【有益模式】
{helpful}

【需改进模式】
{harmful}

【优化建议】
{recs}
"""
    return context


def _generate_route_insight_from_trail(
    event_trail: List[Dict[str, Any]],
    current_state: Dict[str, Any],
    historical_memories: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Generate structured route insights based on event trail.

    Analyzes the execution route and generates actionable insights about:
    - Route efficiency
    - Detected patterns
    - Helpful vs harmful patterns based on historical comparison
    - Optimization recommendations

    Args:
        event_trail: List of orchestration events
        current_state: Current state dictionary for context
        historical_memories: Optional historical route memories for comparison

    Returns:
        Dictionary containing structured route insights:
        {
            "route_efficiency": Dict,  # from analyze_route_efficiency
            "patterns": List[Dict],    # from identify_route_patterns
            "helpful_patterns": List[str],
            "harmful_patterns": List[str],
            "recommendations": List[str],
            "comparison_with_history": Dict,
            "llm_insight": str,
        }
    """
    # 1. Get route efficiency analysis
    route_efficiency = analyze_route_efficiency(event_trail)

    # 2. Identify patterns
    patterns = identify_route_patterns(event_trail)

    # 3. Initialize output
    helpful_patterns: List[str] = []
    harmful_patterns: List[str] = []
    recommendations: List[str] = []
    comparison_with_history: Dict[str, Any] = {
        "has_sufficient_data": False,
        "similar_cases_found": 0,
        "efficiency_comparison": None,
    }

    # 4. Extract context info
    ticker_info = current_state.get("ticker_info", {})
    orchestration = current_state.get("orchestration", {})
    segment = ticker_info.get("segment", "")
    style_bucket = ticker_info.get("style_bucket", "")
    final_route = orchestration.get("final_route", "")
    final_reason = orchestration.get("final_reason", "")

    # 5. Analyze patterns and generate insights
    pattern_types = [p["pattern_type"] for p in patterns]
    efficient_patterns = [p for p in patterns if p.get("is_efficient", False)]
    inefficient_patterns = [p for p in patterns if not p.get("is_efficient", True)]

    # Generate helpful patterns description
    for pattern in efficient_patterns:
        helpful_patterns.append(f"{pattern['description']}")

    # Generate harmful patterns description
    for pattern in inefficient_patterns:
        harmful_patterns.append(f"{pattern['description']}")

    # 6. Generate recommendations based on efficiency score
    efficiency_score = route_efficiency.get("efficiency_score", 1.0)

    if efficiency_score < 0.5:
        recommendations.append("路由效率较低，建议优化执行路径")
        if route_efficiency.get("bottleneck_stages"):
            recommendations.append(
                f"优化瓶颈阶段 {', '.join(route_efficiency['bottleneck_stages'])} 的处理流程"
            )
        if route_efficiency.get("compression_rate", 0) >= 0.5:
            recommendations.append("高压缩率可能导致信息丢失，考虑优化压缩触发条件")

    if route_efficiency.get("has_early_handoff"):
        recommendations.append("检测到早期压缩，建议评估上下文长度是否合理")

    if route_efficiency.get("revisit_ratio", 1.0) > 1.5:
        recommendations.append("阶段重复访问率较高，建议优化状态管理避免重复执行")

    # Add positive feedback for efficient routes
    if efficiency_score >= 0.8 and not inefficient_patterns:
        recommendations.append("当前路由效率良好，保持现有执行策略")

    # 7. Compare with historical data if available
    if historical_memories and len(historical_memories) >= 5:
        comparison_with_history = _compare_with_historical_memories(
            current_efficiency=route_efficiency,
            current_segment=segment,
            current_style=style_bucket,
            current_route=final_route,
            historical_memories=historical_memories,
        )

        # Generate insights from comparison
        if comparison_with_history.get("efficiency_comparison"):
            comp = comparison_with_history["efficiency_comparison"]
            if comp.get("is_better_than_average"):
                helpful_patterns.append(
                    f"相比同类股票平均效率高出 {comp['diff_percent']:.1f}%"
                )
            elif comp.get("is_worse_than_average"):
                harmful_patterns.append(
                    f"相比同类股票平均效率低 {abs(comp['diff_percent']):.1f}%"
                )

    # 8. Generate LLM insight
    llm_insight = _generate_llm_route_insight(
        route_efficiency=route_efficiency,
        patterns=patterns,
        segment=segment,
        style_bucket=style_bucket,
        final_route=final_route,
        final_reason=final_reason,
        helpful_patterns=helpful_patterns,
        harmful_patterns=harmful_patterns,
        recommendations=recommendations,
    )

    return {
        "route_efficiency": route_efficiency,
        "patterns": patterns,
        "helpful_patterns": helpful_patterns,
        "harmful_patterns": harmful_patterns,
        "recommendations": recommendations,
        "comparison_with_history": comparison_with_history,
        "llm_insight": llm_insight,
    }


def get_route_summary(current_state: Dict[str, Any]) -> Dict[str, Any]:
    """Get a structured summary of the route taken.

    Args:
        current_state: The current state dictionary

    Returns:
        Dictionary containing route summary with key metrics
    """
    event_trail = _extract_event_trail(current_state)
    pattern_analysis = _analyze_route_patterns(event_trail)

    orchestration = current_state.get("orchestration", {})
    route_decision = _extract_route_decision(current_state)
    semantic_trigger_audit = _extract_semantic_trigger_audit(current_state)
    semantic_execution_profile = dict(
        orchestration.get("semantic_execution_profile", {})
        or current_state.get("semantic_execution_profile", {})
        or current_state.get("screener_context", {}).get("semantic_execution_profile", {})
        or {}
    )
    semantic_trail = [
        {
            "node": e.get("node", ""),
            "phase": e.get("phase", ""),
            "route_rule": e.get("route_rule", ""),
            "route_reason": e.get("route_reason", ""),
            "semantic_trigger_reasons": list(
                dict(e.get("semantic_trigger_audit", {}) or {}).get("semantic_trigger_reasons", []) or []
            ),
        }
        for e in event_trail
    ]

    return {
        "route_taken": [e.get("node", "") for e in event_trail],
        "compression_triggered": pattern_analysis["compression_count"] > 0,
        "compression_phases": [
            e.get("phase", "") for e in event_trail if e.get("compression_triggered")
        ],
        "final_route": orchestration.get("final_route", ""),
        "final_reason": orchestration.get("final_reason", ""),
        "route_decision": route_decision,
        "route_family": route_decision.get("route_family", ""),
        "policy_role": route_decision.get("policy_role", ""),
        "capital_quality": route_decision.get("capital_quality", ""),
        "debate_rounds": route_decision.get("debate_rounds", ""),
        "debate_risk_weight": route_decision.get("debate_risk_weight", ""),
        "selected_analysts": route_decision.get("selected_analysts", []),
        "semantic_trigger_audit": semantic_trigger_audit,
        "semantic_trigger_reasons": list(semantic_trigger_audit.get("semantic_trigger_reasons", []) or []),
        "semantic_execution_profile": semantic_execution_profile,
        "semantic_route_audit_trail": semantic_trail,
        "pattern_analysis": pattern_analysis,
    }
