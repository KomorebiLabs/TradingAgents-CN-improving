# TradingAgents/graph/reflection.py

from typing import Any, Dict, List, Optional
from datetime import datetime
from collections import Counter

from tradingagents.agents.utils.state_helpers import extract_semantic_trigger_audit


class Reflector:
    """Handles reflection on decisions and updating memory."""

    def __init__(self, quick_thinking_llm: Any):
        """Initialize the reflector with an LLM."""
        self.quick_thinking_llm = quick_thinking_llm
        self.reflection_system_prompt = self._get_reflection_prompt()
        self.route_insight_system_prompt = self._get_route_insight_prompt()

    def _get_reflection_prompt(self) -> str:
        """Get the system prompt for reflection."""
        return """
You are an expert financial analyst tasked with reviewing trading decisions/analysis and providing a comprehensive, step-by-step analysis. 
Your goal is to deliver detailed insights into investment decisions and highlight opportunities for improvement, adhering strictly to the following guidelines:

1. Reasoning:
   - For each trading decision, determine whether it was correct or incorrect. A correct decision results in an increase in returns, while an incorrect decision does the opposite.
   - Analyze the contributing factors to each success or mistake. Consider:
     - Market intelligence.
     - Technical indicators.
     - Technical signals.
     - Price movement analysis.
     - Overall market data analysis 
     - News analysis.
     - Social media and sentiment analysis.
     - Fundamental data analysis.
     - Weight the importance of each factor in the decision-making process.

2. Improvement:
   - For any incorrect decisions, propose revisions to maximize returns.
   - Provide a detailed list of corrective actions or improvements, including specific recommendations (e.g., changing a decision from HOLD to BUY on a particular date).

3. Summary:
   - Summarize the lessons learned from the successes and mistakes.
   - Highlight how these lessons can be adapted for future trading scenarios and draw connections between similar situations to apply the knowledge gained.

4. Query:
   - Extract key insights from the summary into a concise sentence of no more than 1000 tokens.
   - Ensure the condensed sentence captures the essence of the lessons and reasoning for easy reference.

Adhere strictly to these instructions, and ensure your output is detailed, accurate, and actionable. You will also be given objective descriptions of the market from a price movements, technical indicator, news, and sentiment perspective to provide more context for your analysis.
"""

    def _get_route_insight_prompt(self) -> str:
        """Get the system prompt for route insight generation."""
        return """
You are an orchestration analyst tasked with reviewing the execution route taken by a multi-agent trading system.

Your goal is to evaluate whether the chosen execution path (direct vs. handoff/compression) contributed positively or negatively to the final decision quality.

For each route segment, assess:
1. Whether compression was triggered and if it preserved or lost critical information
2. Whether the direct path would have been better or worse
3. What patterns in the input (e.g., long debates, complex risk scenarios) correlate with needing compression

Output a concise route insight that can be stored and retrieved for future route optimization.
"""

    def _extract_current_situation(self, current_state: Dict[str, Any]) -> str:
        """Extract the current market situation from the state."""
        curr_market_report = current_state["market_report"]
        curr_sentiment_report = current_state["sentiment_report"]
        curr_news_report = current_state["news_report"]
        curr_fundamentals_report = current_state["fundamentals_report"]
        orchestration_context = self._extract_orchestration_context(current_state)

        return (
            f"{curr_market_report}\n\n"
            f"{curr_sentiment_report}\n\n"
            f"{curr_news_report}\n\n"
            f"{curr_fundamentals_report}\n\n"
            f"{orchestration_context}"
        )

    def _extract_orchestration_context(self, current_state: Dict[str, Any]) -> str:
        """Summarize orchestration telemetry for reflection and memory."""
        orchestration = dict(current_state.get("orchestration", {}))
        ticker_info = dict(current_state.get("ticker_info", {}))
        route_decision = self._extract_route_decision(current_state)
        semantic_trigger_audit = self._extract_semantic_trigger_audit(current_state)

        stage = orchestration.get("stage", "")
        phase = orchestration.get("phase", "")
        next_stage = orchestration.get("next_stage", "")
        completed = orchestration.get("completed", False)
        final_route = orchestration.get("final_route", "")
        final_reason = orchestration.get("final_reason", "")
        compression_required = orchestration.get("compression_required", False)
        compression_notes = str(orchestration.get("compression_notes", "")).strip()
        selected_analysts = orchestration.get("selected_analysts") or ticker_info.get("selected_analysts") or []
        segment = ticker_info.get("segment", "")
        style_bucket = ticker_info.get("style_bucket", "")
        skills = ticker_info.get("skills", [])

        compression_excerpt = compression_notes[:600]
        return (
            "Execution Orchestration Context:\n"
            f"- stage: {stage}\n"
            f"- phase: {phase}\n"
            f"- next_stage: {next_stage}\n"
            f"- completed: {completed}\n"
            f"- final_route: {final_route}\n"
            f"- final_reason: {final_reason}\n"
            f"- compression_required: {compression_required}\n"
            f"- selected_analysts: {selected_analysts}\n"
            f"- route_decision: {route_decision}\n"
            f"- semantic_trigger_reasons: {semantic_trigger_audit.get('semantic_trigger_reasons', [])}\n"
            f"- semantic_trigger_slots: {semantic_trigger_audit.get('semantic_trigger_slots', {})}\n"
            f"- segment: {segment}\n"
            f"- style_bucket: {style_bucket}\n"
            f"- skills: {skills}\n"
            f"- compression_notes_excerpt: {compression_excerpt}"
        )

    def _extract_orchestration_context_structured(
        self,
        current_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Extract orchestration context as a structured dict.

        Returns a structured dictionary with typed fields that can be
        used for structured memory storage and querying.

        Args:
            current_state: The current state dictionary

        Returns:
            Dict containing structured orchestration metadata
        """
        orchestration = dict(current_state.get("orchestration", {}))
        ticker_info = dict(current_state.get("ticker_info", {}))
        event_trail = self._extract_event_trail(current_state)
        route_decision = self._extract_route_decision(current_state)
        semantic_trigger_audit = self._extract_semantic_trigger_audit(current_state)

        # Extract stage and phase sequences from event trail
        stage_sequence = [e.get("stage", "") for e in event_trail if e.get("stage")]
        phase_sequence = [e.get("phase", "") for e in event_trail if e.get("phase")]

        # Calculate compression statistics
        compression_phases = [
            e.get("phase", "") for e in event_trail if e.get("compression_triggered")
        ]
        compression_rate = len(compression_phases) / max(len(stage_sequence), 1)

        # Determine route category
        if compression_rate == 0:
            route_category = "normal"
        elif compression_rate < 0.5:
            route_category = "mixed"
        else:
            route_category = "complex"

        # Identify bottleneck stages (stages visited 2 or more times)
        stage_counts = Counter(stage_sequence)
        bottleneck_stages = [s for s, c in stage_counts.items() if c >= 2]

        # Get current values
        stage = orchestration.get("stage", "")
        phase = orchestration.get("phase", "")
        final_route = orchestration.get("final_route", "")
        final_reason = orchestration.get("final_reason", "")
        selected_analysts = orchestration.get("selected_analysts") or ticker_info.get("selected_analysts") or []
        segment = ticker_info.get("segment", "")
        style_bucket = ticker_info.get("style_bucket", "")
        skills = ticker_info.get("skills", [])

        return {
            # Stage/phase info
            "stage_sequence": stage_sequence,
            "phase_sequence": phase_sequence,
            "compression_phases": compression_phases,
            "compression_rate": compression_rate,
            "compression_triggered": len(compression_phases) > 0,

            # Route categorization
            "route_category": route_category,
            "final_route": final_route,
            "final_reason": final_reason,
            "route_decision": route_decision,
            "semantic_trigger_audit": semantic_trigger_audit,
            "semantic_trigger_reasons": list(semantic_trigger_audit.get("semantic_trigger_reasons", []) or []),

            # Tool/context info
            "segment": segment,
            "style_bucket": style_bucket,
            "selected_analysts": selected_analysts,
            "skills": skills,

            # Event statistics
            "total_events": len(event_trail),
            "unique_stages": list(dict.fromkeys(stage_sequence)),  # Preserve order, remove duplicates
            "bottleneck_stages": bottleneck_stages,

            # Current position
            "current_stage": stage,
            "current_phase": phase,

            # Ticker info
            "ticker": ticker_info.get("ticker", ""),
            "company_name": ticker_info.get("company_name", ""),

            # Timestamps
            "trade_date": ticker_info.get("trade_date", datetime.now().strftime("%Y-%m-%d")),
            "created_at": datetime.now().isoformat(),
        }

    def _reflect_on_component(
        self, component_type: str, report: str, situation: str, returns_losses
    ) -> str:
        """Generate reflection for a component."""
        component_context = self._build_component_context(component_type)
        messages = [
            ("system", self.reflection_system_prompt),
            (
                "human",
                f"Component: {component_type}\n\n"
                f"Component-specific orchestration guidance: {component_context}\n\n"
                f"Returns: {returns_losses}\n\n"
                f"Analysis/Decision: {report}\n\n"
                f"Objective Market Reports for Reference: {situation}",
            ),
        ]

        result = self.quick_thinking_llm.invoke(messages).content
        return result

    def _build_component_context(self, component_type: str) -> str:
        """Map orchestration telemetry to the most relevant reflection lens."""
        context_map = {
            "BULL": "Focus on whether the research-stage path selection preserved enough bullish evidence before handoff.",
            "BEAR": "Focus on whether the research-stage path selection preserved enough bearish evidence before handoff.",
            "TRADER": "Pay attention to whether research-to-trader handoff compression helped or hid execution-critical details.",
            "INVEST JUDGE": "Judge whether research orchestration, debate length, and any handoff memo improved decision clarity.",
            "PORTFOLIO MANAGER": "Judge whether the risk finalization route, final_reason, and any compression memo improved the final risk-adjusted decision.",
        }
        return context_map.get(
            component_type,
            "Use the orchestration telemetry to explain whether the execution path helped or hurt decision quality.",
        )

    def _extract_event_trail(self, current_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract the event trail from current state.

        Returns:
            List of orchestration events, or empty list if not available.
        """
        orchestration = current_state.get("orchestration", {})
        return list(orchestration.get("event_trail", []) or [])

    @staticmethod
    def _extract_route_decision(current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract the semantic route decision used by the graph."""
        orchestration = dict(current_state.get("orchestration", {}))
        ticker_info = dict(current_state.get("ticker_info", {}))
        route_decision = dict(orchestration.get("route_decision", {}) or ticker_info.get("route_decision", {}) or {})
        semantic_flow_controls = dict(route_decision.get("semantic_flow_controls", {}) or {})
        route_decision.setdefault("route_family", orchestration.get("route_family", ""))
        route_decision.setdefault("policy_role", orchestration.get("policy_role", ""))
        route_decision.setdefault("capital_quality", orchestration.get("capital_quality", ""))
        route_decision.setdefault("conflict_tier", orchestration.get("conflict_tier", ""))
        route_decision.setdefault("debate_rounds", orchestration.get("debate_rounds", ""))
        route_decision.setdefault("debate_risk_weight", orchestration.get("debate_risk_weight", ""))
        route_decision.setdefault("selected_analysts", orchestration.get("selected_analysts", []))
        route_decision.setdefault("analyst_focus", orchestration.get("analyst_focus", []))
        route_decision.setdefault("semantic_flow_controls", semantic_flow_controls)
        return route_decision

    @staticmethod
    def _extract_semantic_trigger_audit(current_state: Dict[str, Any]) -> Dict[str, Any]:
        orchestration = dict(current_state.get("orchestration", {}))
        ticker_info = dict(current_state.get("ticker_info", {}))
        route_decision = dict(orchestration.get("route_decision", {}) or ticker_info.get("route_decision", {}) or {})
        semantic_prompt_slots = dict(
            current_state.get("semantic_prompt_slots", {})
            or current_state.get("screener_context", {}).get("semantic_prompt_slots", {})
            or ticker_info.get("semantic_prompt_slots", {})
            or {}
        )
        applied_controls = dict(orchestration.get("applied_controls", {}) or {})
        existing = dict(orchestration.get("semantic_trigger_audit", {}) or {})
        if existing:
            return existing
        return extract_semantic_trigger_audit(
            route_decision=route_decision,
            semantic_prompt_slots=semantic_prompt_slots,
            applied_controls=applied_controls,
        )

    def _format_event_trail(self, event_trail: List[Dict[str, Any]]) -> str:
        """Format event trail into a human-readable string.

        Args:
            event_trail: List of orchestration events

        Returns:
            Formatted string representation of the route taken
        """
        if not event_trail:
            return "No event trail recorded."

        lines = ["=== Execution Route Timeline ==="]
        for i, event in enumerate(event_trail, 1):
            node = event.get("node", "unknown")
            phase = event.get("phase", "")
            stage = event.get("stage", "")
            next_stage = event.get("next_stage", "")
            compression = "Y" if event.get("compression_triggered") else "N"
            context_estimate = event.get("context_estimate", 0)
            timestamp = event.get("timestamp", "")
            semantic_trigger_audit = dict(event.get("semantic_trigger_audit", {}) or {})
            semantic_trigger_reasons = list(semantic_trigger_audit.get("semantic_trigger_reasons", []) or [])

            lines.append(
                f"{i}. [{timestamp}] {node}\n"
                f"   phase={phase} | stage={stage} | next_stage={next_stage}\n"
                f"   compression_triggered={compression} | context_estimate={context_estimate}"
            )
            if semantic_trigger_reasons:
                lines.append(
                    f"   semantic_triggers={'; '.join(semantic_trigger_reasons[:5])}"
                )

        compression_count = sum(1 for e in event_trail if e.get("compression_triggered"))
        lines.append(f"\nTotal events: {len(event_trail)}")
        lines.append(f"Compression events: {compression_count}")

        return "\n".join(lines)

    def _analyze_route_patterns(self, event_trail: List[Dict[str, Any]]) -> Dict[str, Any]:
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

    def analyze_route_efficiency(self, event_trail: List[Dict[str, Any]]) -> Dict[str, Any]:
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

    def identify_route_patterns(self, event_trail: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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

    def _generate_route_insight_from_trail(
        self,
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
        route_efficiency = self.analyze_route_efficiency(event_trail)

        # 2. Identify patterns
        patterns = self.identify_route_patterns(event_trail)

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
            comparison_with_history = self._compare_with_historical_memories(
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
        llm_insight = self._generate_llm_route_insight(
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

    def _compare_with_historical_memories(
        self,
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
        self,
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

    def generate_route_insight(self, current_state: Dict[str, Any]) -> str:
        """Generate a reflection on the execution route taken.

        This method analyzes the event_trail to understand:
        - Which phases triggered compression and why
        - Whether the chosen paths (direct vs handoff) were optimal
        - What patterns in input correlate with needing compression

        Args:
            current_state: The current state dictionary

        Returns:
            A string containing route insights that can be stored in memory
        """
        event_trail = self._extract_event_trail(current_state)
        pattern_analysis = self._analyze_route_patterns(event_trail)

        final_route = current_state.get("orchestration", {}).get("final_route", "")
        final_reason = current_state.get("orchestration", {}).get("final_reason", "")
        ticker_info = current_state.get("ticker_info", {})
        segment = ticker_info.get("segment", "")
        style_bucket = ticker_info.get("style_bucket", "")

        formatted_trail = self._format_event_trail(event_trail)

        messages = [
            ("system", self.route_insight_system_prompt),
            (
                "human",
                f"Event Trail Analysis:\n{formatted_trail}\n\n"
                f"Route Patterns:\n"
                f"- Total events: {pattern_analysis['total_events']}\n"
                f"- Compression events: {pattern_analysis['compression_count']}\n"
                f"- Phases visited: {pattern_analysis['phases_visited']}\n"
                f"- Handoff occurred: {pattern_analysis['handoff_occurred']}\n"
                f"- Compression rate: {pattern_analysis['compression_rate']:.2%}\n"
                f"- Avg context per phase: {pattern_analysis['avg_context_per_phase']}\n\n"
                f"Final Route: {final_route}\n"
                f"Final Reason: {final_reason}\n\n"
                f"Instrument Context:\n"
                f"- Segment: {segment}\n"
                f"- Style Bucket: {style_bucket}\n\n"
                f"Based on the event trail and patterns above, generate a concise insight "
                f"about whether the execution route was optimal and what could be improved."
            ),
        ]

        result = self.quick_thinking_llm.invoke(messages).content
        return result

    def get_route_summary(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Get a structured summary of the route taken.

        Args:
            current_state: The current state dictionary

        Returns:
            Dictionary containing route summary with key metrics
        """
        event_trail = self._extract_event_trail(current_state)
        pattern_analysis = self._analyze_route_patterns(event_trail)

        orchestration = current_state.get("orchestration", {})
        route_decision = self._extract_route_decision(current_state)
        semantic_trigger_audit = self._extract_semantic_trigger_audit(current_state)
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

    def reflect_bull_researcher(self, current_state, returns_losses, bull_memory):
        """Reflect on bull researcher's analysis and update memory."""
        situation = self._extract_current_situation(current_state)
        bull_debate_history = current_state["investment_debate_state"]["bull_history"]

        result = self._reflect_on_component(
            "BULL", bull_debate_history, situation, returns_losses
        )
        bull_memory.add_situations([(situation, result)])

    def reflect_bear_researcher(self, current_state, returns_losses, bear_memory):
        """Reflect on bear researcher's analysis and update memory."""
        situation = self._extract_current_situation(current_state)
        bear_debate_history = current_state["investment_debate_state"]["bear_history"]

        result = self._reflect_on_component(
            "BEAR", bear_debate_history, situation, returns_losses
        )
        bear_memory.add_situations([(situation, result)])

    def reflect_trader(self, current_state, returns_losses, trader_memory):
        """Reflect on trader's decision and update memory."""
        situation = self._extract_current_situation(current_state)
        trader_decision = current_state["trader_investment_plan"]

        result = self._reflect_on_component(
            "TRADER", trader_decision, situation, returns_losses
        )
        trader_memory.add_situations([(situation, result)])

    def reflect_invest_judge(self, current_state, returns_losses, invest_judge_memory):
        """Reflect on investment judge's decision and update memory."""
        situation = self._extract_current_situation(current_state)
        judge_decision = current_state["investment_debate_state"]["judge_decision"]

        result = self._reflect_on_component(
            "INVEST JUDGE", judge_decision, situation, returns_losses
        )
        invest_judge_memory.add_situations([(situation, result)])

    def reflect_portfolio_manager(
        self,
        current_state,
        returns_losses,
        portfolio_manager_memory,
        route_memory=None,
    ):
        """Reflect on portfolio manager's decision and update memory.

        Args:
            current_state: The current state dictionary
            returns_losses: Returns/losses data for reflection
            portfolio_manager_memory: Memory for portfolio manager reflections
            route_memory: Optional StructuredMemory for route insights with metadata
        """
        situation = self._extract_current_situation(current_state)
        judge_decision = current_state["risk_debate_state"]["judge_decision"]

        result = self._reflect_on_component(
            "PORTFOLIO MANAGER", judge_decision, situation, returns_losses
        )
        portfolio_manager_memory.add_situations([(situation, result)])

        if route_memory is not None:
            event_trail = self._extract_event_trail(current_state)

            # Generate structured route insight
            historical_memories = None
            if hasattr(route_memory, "export_memories"):
                historical_memories = route_memory.export_memories()

            structured_insight = self._generate_route_insight_from_trail(
                event_trail=event_trail,
                current_state=current_state,
                historical_memories=historical_memories,
            )

            route_summary = self.get_route_summary(current_state)
            structured_context = self._extract_orchestration_context_structured(current_state)

            compression_triggered = route_summary["compression_triggered"]
            compression_phases = route_summary["compression_phases"]
            route_decision = route_summary.get("route_decision", {})
            semantic_trigger_audit = route_summary.get("semantic_trigger_audit", {})

            # Build comprehensive metadata using structured context and insight
            route_efficiency = structured_insight.get("route_efficiency", {})
            metadata = {
                # Core routing info
                "segment": structured_context.get("segment", ""),
                "style_bucket": structured_context.get("style_bucket", ""),
                "final_route": structured_context.get("final_route", ""),
                "final_reason": structured_context.get("final_reason", ""),
                "route_category": structured_context.get("route_category", "unknown"),

                # Compression info
                "compression_triggered": compression_triggered,
                "compression_phases": compression_phases,
                "compression_rate": structured_context.get("compression_rate", 0.0),

                # Event statistics
                "total_events": structured_context.get("total_events", 0),
                "unique_stages": structured_context.get("unique_stages", []),
                "bottleneck_stages": structured_context.get("bottleneck_stages", []),

                # Sequences
                "stage_sequence": structured_context.get("stage_sequence", []),
                "phase_sequence": structured_context.get("phase_sequence", []),

                # Tool/context
                "selected_analysts": structured_context.get("selected_analysts", []),
                "skills": structured_context.get("skills", []),
                "route_decision": route_decision,
                "semantic_trigger_audit": semantic_trigger_audit,
                "semantic_trigger_reasons": route_summary.get("semantic_trigger_reasons", []),
                "semantic_route_audit_trail": route_summary.get("semantic_route_audit_trail", []),
                "route_family": route_summary.get("route_family", ""),
                "policy_role": route_summary.get("policy_role", ""),
                "capital_quality": route_summary.get("capital_quality", ""),
                "debate_rounds": route_summary.get("debate_rounds", ""),
                "debate_risk_weight": route_summary.get("debate_risk_weight", ""),

                # Timestamps
                "trade_date": structured_context.get("trade_date", ""),
                "created_at": structured_context.get("created_at", ""),

                # Ticker
                "ticker": structured_context.get("ticker", ""),
                "company_name": structured_context.get("company_name", ""),

                # === NEW: Route efficiency and insights ===
                "efficiency_score": route_efficiency.get("efficiency_score", 0.5),
                "detected_patterns": [p["pattern_type"] for p in structured_insight.get("patterns", [])],
                "helpful_patterns": structured_insight.get("helpful_patterns", []),
                "harmful_patterns": structured_insight.get("harmful_patterns", []),
                "optimization_recommendations": structured_insight.get("recommendations", []),
                "revisit_ratio": route_efficiency.get("revisit_ratio", 1.0),
                "has_early_handoff": route_efficiency.get("has_early_handoff", False),
            }

            # Build enhanced route situation description
            route_situation = (
                f"Segment: {metadata['segment']}\n"
                f"Style: {metadata['style_bucket']}\n"
                f"Route: {metadata['final_route']}\n"
                f"Route decision: {route_decision}\n"
                f"Route Category: {metadata['route_category']}\n"
                f"Compression triggered: {compression_triggered}\n"
                f"Compression rate: {metadata['compression_rate']:.2%}\n"
                f"Compression phases: {compression_phases}\n"
                f"Total events: {metadata['total_events']}\n"
                f"Bottleneck stages: {metadata['bottleneck_stages']}\n"
                f"=== Route Efficiency ===\n"
                f"Efficiency Score: {metadata['efficiency_score']:.2f}/1.0\n"
                f"Revisit Ratio: {metadata['revisit_ratio']:.2f}\n"
                f"Early Handoff: {metadata['has_early_handoff']}\n"
                f"Detected Patterns: {', '.join(metadata['detected_patterns']) or 'none'}"
            )

            # Use the structured insight text from LLM
            route_insight = structured_insight.get("llm_insight", "")

            if hasattr(route_memory, "add_situation"):
                route_memory.add_situation(
                    situation=route_situation,
                    recommendation=route_insight,
                    metadata=metadata,
                )
            else:
                route_memory.add_situations([(route_situation, route_insight)])

    def generate_conclusion_summary(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a structured lightweight conclusion summary for cross-session memory.

        Hybrid approach:
        - Structured fields: extracted from AgentState via template (no LLM cost)
        - summary field: generated by a lightweight LLM call (~50-100 tokens)

        Args:
            current_state: The final AgentState after analysis completes

        Returns:
            Dict containing: ticker, trade_date, summary, dimensions, final_decision,
            confidence, key_reasons, risks
        """
        ticker = current_state.get("company_of_interest", "UNKNOWN")
        trade_date = str(current_state.get("trade_date", ""))

        # ── Template-based extraction (no LLM cost) ─────────────────────────────
        decision_blocks = current_state.get("decision_blocks") or {}
        investment_plan = decision_blocks.get("investment_plan", "")
        trader_plan = decision_blocks.get("trader_plan", "")
        final_decision = decision_blocks.get("final_trade_decision", "")

        investment_debate = current_state.get("investment_debate_state") or {}
        judge_decision = investment_debate.get("judge_decision", "")

        risk_debate = current_state.get("risk_debate_state") or {}
        risk_judge = risk_debate.get("judge_decision", "")

        bull_history = investment_debate.get("bull_history", "")
        bear_history = investment_debate.get("bear_history", "")

        # Build key_reasons and risks lists
        key_reasons = []
        risks = []

        if bull_history and len(bull_history) > 10:
            key_reasons.append(f"Bull case: {bull_history[:300]}")
        if judge_decision and len(judge_decision) > 10:
            key_reasons.append(f"Investment judgment: {judge_decision[:300]}")
        if risk_judge and len(risk_judge) > 10:
            risks.append(f"Risk judgment: {risk_judge[:300]}")

        # Extract dimensions from screener_context
        dimensions = {}
        screener_context = current_state.get("screener_context") or {}
        route_decision = screener_context.get("route_decision") or {}
        signal_card = route_decision.get("signal_card") or {}
        if isinstance(signal_card, dict):
            dimensions = {
                "policy": signal_card.get("policy_signal_score", 0.5),
                "technical": signal_card.get("technical_signal_score", 0.5),
                "smart_money": signal_card.get("smart_money_signal_score", 0.5),
            }

        # Determine confidence level
        confidence = "中"
        if final_decision:
            dl = final_decision.upper()
            if "强" in final_decision or "买入" in final_decision or "BUY" in dl:
                confidence = "高"
            elif "不" in final_decision or "卖出" in final_decision or "SELL" in dl:
                confidence = "低"
        if judge_decision and ("不" in judge_decision or "无" in judge_decision):
            confidence = "低"

        # ── LLM-generated one-line summary (hybrid part) ───────────────────────
        prompt = (
            f"Given the following analysis results for {ticker} on {trade_date}, "
            f"write ONE concise sentence (in Chinese, under 50 characters) that captures the core investment conclusion.\n\n"
            f"Investment plan: {investment_plan[:500]}\n"
            f"Final decision: {final_decision[:500]}\n"
            f"Judge opinion: {judge_decision[:300]}\n"
            f"Risk opinion: {risk_judge[:300]}"
        )

        summary_text = "分析完成"
        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.quick_thinking_llm.invoke(messages)
            if hasattr(response, "content") and response.content:
                summary_text = response.content.strip()[:200]
        except Exception:
            summary_text = f"分析完成，结论：{final_decision[:100] if final_decision else '待确认'}"

        return {
            "ticker": ticker,
            "trade_date": trade_date,
            "summary": summary_text,
            "dimensions": dimensions,
            "final_decision": final_decision[:500] if final_decision else "N/A",
            "confidence": confidence,
            "key_reasons": key_reasons[:5],
            "risks": risks[:5],
        }
