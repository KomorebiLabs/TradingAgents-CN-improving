"""State extraction helpers (split from reflection.py — refactor/merger-pipeline style).

Pure functions over the AgentState dict: extract orchestration context,
event trail, route decision, semantic trigger audit.  No LLM, no self.
"""

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

from tradingagents.agents.utils.state_helpers import extract_semantic_trigger_audit


def _extract_event_trail(current_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract the event trail from current state.

    Returns:
        List of orchestration events, or empty list if not available.
    """
    orchestration = current_state.get("orchestration", {})
    return list(orchestration.get("event_trail", []) or [])


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


def _format_event_trail(event_trail: List[Dict[str, Any]]) -> str:
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


def _extract_orchestration_context(current_state: Dict[str, Any]) -> str:
    """Summarize orchestration telemetry for reflection and memory."""
    orchestration = dict(current_state.get("orchestration", {}))
    ticker_info = dict(current_state.get("ticker_info", {}))
    route_decision = _extract_route_decision(current_state)
    semantic_trigger_audit = _extract_semantic_trigger_audit(current_state)

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


def _extract_current_situation(current_state: Dict[str, Any]) -> str:
    """Extract the current market situation from the state."""
    curr_market_report = current_state["market_report"]
    curr_sentiment_report = current_state["sentiment_report"]
    curr_news_report = current_state["news_report"]
    curr_fundamentals_report = current_state["fundamentals_report"]
    orchestration_context = _extract_orchestration_context(current_state)

    return (
        f"{curr_market_report}\n\n"
        f"{curr_sentiment_report}\n\n"
        f"{curr_news_report}\n\n"
        f"{curr_fundamentals_report}\n\n"
        f"{orchestration_context}"
    )


def _extract_orchestration_context_structured(
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
    event_trail = _extract_event_trail(current_state)
    route_decision = _extract_route_decision(current_state)
    semantic_trigger_audit = _extract_semantic_trigger_audit(current_state)

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
