"""Reflector facade (split from reflection.py — refactor/merger-pipeline style).

Keeps the public class contract used by trading_graph.py (reflect_*,
get_route_summary, generate_conclusion_summary, generate_route_insight).
LLM-based reflection stays here; pure extraction / route analytics /
conclusion summary delegate to sibling modules.
"""

from typing import Any, Dict, List

from . import conclusion, extraction, route_analytics


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

    def reflect_bull_researcher(self, current_state, returns_losses, bull_memory):
        """Reflect on bull researcher's analysis and update memory."""
        situation = extraction._extract_current_situation(current_state)
        bull_debate_history = current_state["investment_debate_state"]["bull_history"]

        result = self._reflect_on_component(
            "BULL", bull_debate_history, situation, returns_losses
        )
        bull_memory.add_situations([(situation, result)])

    def reflect_bear_researcher(self, current_state, returns_losses, bear_memory):
        """Reflect on bear researcher's analysis and update memory."""
        situation = extraction._extract_current_situation(current_state)
        bear_debate_history = current_state["investment_debate_state"]["bear_history"]

        result = self._reflect_on_component(
            "BEAR", bear_debate_history, situation, returns_losses
        )
        bear_memory.add_situations([(situation, result)])

    def reflect_trader(self, current_state, returns_losses, trader_memory):
        """Reflect on trader's decision and update memory."""
        situation = extraction._extract_current_situation(current_state)
        trader_decision = current_state["trader_investment_plan"]

        result = self._reflect_on_component(
            "TRADER", trader_decision, situation, returns_losses
        )
        trader_memory.add_situations([(situation, result)])

    def reflect_invest_judge(self, current_state, returns_losses, invest_judge_memory):
        """Reflect on investment judge's decision and update memory."""
        situation = extraction._extract_current_situation(current_state)
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
        situation = extraction._extract_current_situation(current_state)
        judge_decision = current_state["risk_debate_state"]["judge_decision"]

        result = self._reflect_on_component(
            "PORTFOLIO MANAGER", judge_decision, situation, returns_losses
        )
        portfolio_manager_memory.add_situations([(situation, result)])

        if route_memory is not None:
            event_trail = extraction._extract_event_trail(current_state)

            # Generate structured route insight
            historical_memories = None
            if hasattr(route_memory, "export_memories"):
                historical_memories = route_memory.export_memories()

            structured_insight = route_analytics._generate_route_insight_from_trail(
                event_trail=event_trail,
                current_state=current_state,
                historical_memories=historical_memories,
            )

            route_summary = route_analytics.get_route_summary(current_state)
            structured_context = extraction._extract_orchestration_context_structured(current_state)

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

    def generate_route_insight(self, current_state: Dict[str, Any]) -> str:
        """Generate a reflection on the execution route taken.

        NOTE: no external callers found in the codebase (grep 2026-08-16);
        kept for API compatibility, behavior preserved verbatim.

        Args:
            current_state: The current state dictionary

        Returns:
            A string containing route insights that can be stored in memory
        """
        event_trail = extraction._extract_event_trail(current_state)
        pattern_analysis = route_analytics._analyze_route_patterns(event_trail)

        final_route = current_state.get("orchestration", {}).get("final_route", "")
        final_reason = current_state.get("orchestration", {}).get("final_reason", "")
        ticker_info = current_state.get("ticker_info", {})
        segment = ticker_info.get("segment", "")
        style_bucket = ticker_info.get("style_bucket", "")

        formatted_trail = extraction._format_event_trail(event_trail)

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
        """Get a structured summary of the route taken (delegates to route_analytics)."""
        return route_analytics.get_route_summary(current_state)

    def generate_conclusion_summary(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a structured lightweight conclusion summary (delegates to conclusion)."""
        return conclusion.generate_conclusion_summary(self.quick_thinking_llm, current_state)
