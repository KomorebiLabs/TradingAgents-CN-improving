from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Union


def _safe_int(val: Any, default: int = 0) -> int:
    if val is None:
        return default
    if isinstance(val, int):
        return val
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    if isinstance(val, float):
        return val
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return default


SEMANTIC_TRIGGER_SLOT_KEYS = {
    "policy_role": "policy_role",
    "capital_quality": "capital_quality",
    "semantic_priority": "semantic_priority",
    "policy_multi_concept_overlap_count": "policy_multi_concept_overlap_count",
    "capital_heat_quality_gap_score": "capital_heat_quality_gap_score",
    "technical_volume_price_divergence_score": "technical_volume_price_divergence_score",
}


def extract_semantic_trigger_audit(
    route_decision: Dict[str, Any] | None = None,
    semantic_prompt_slots: Dict[str, Any] | None = None,
    applied_controls: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build a compact, stable audit payload for semantic route triggers."""
    route_decision = dict(route_decision or {})
    semantic_prompt_slots = dict(semantic_prompt_slots or {})
    applied_controls = dict(applied_controls or {})

    trigger_slots = {
        audit_key: semantic_prompt_slots.get(slot_key)
        for audit_key, slot_key in SEMANTIC_TRIGGER_SLOT_KEYS.items()
        if semantic_prompt_slots.get(slot_key) is not None
    }
    trigger_slots.update(
        {
            "analyst_focus": list(route_decision.get("analyst_focus", []) or []),
            "selected_analysts": list(route_decision.get("selected_analysts", []) or []),
            "debate_rounds": route_decision.get("debate_rounds", ""),
            "debate_risk_weight": route_decision.get("debate_risk_weight", ""),
            "conflict_tier": route_decision.get("conflict_tier", ""),
        }
    )

    trigger_reasons: List[str] = []
    policy_role = str(route_decision.get("policy_role", "") or semantic_prompt_slots.get("policy_role", "") or "")
    capital_quality = str(route_decision.get("capital_quality", "") or semantic_prompt_slots.get("capital_quality", "") or "")
    semantic_priority = _safe_int(route_decision.get("semantic_priority", semantic_prompt_slots.get("semantic_priority", 0)))
    overlap_count = _safe_int(semantic_prompt_slots.get("policy_multi_concept_overlap_count", 0))
    heat_gap = _safe_float(semantic_prompt_slots.get("capital_heat_quality_gap_score", 0.0))
    technical_divergence = _safe_float(semantic_prompt_slots.get("technical_volume_price_divergence_score", 0.0))
    analyst_focus = trigger_slots["analyst_focus"]

    if policy_role:
        trigger_reasons.append(f"policy_role={policy_role}")
    if capital_quality:
        trigger_reasons.append(f"capital_quality={capital_quality}")
    if overlap_count > 0:
        trigger_reasons.append(f"concept_overlap_count={overlap_count}")
    if "concept_overlap" in analyst_focus:
        trigger_reasons.append("analyst_focus:concept_overlap")
    if heat_gap >= 20:
        trigger_reasons.append(f"heat_quality_gap={heat_gap:.1f}")
    if "heat_quality_gap" in analyst_focus:
        trigger_reasons.append("analyst_focus:heat_quality_gap")
    if technical_divergence >= 30:
        trigger_reasons.append(f"technical_divergence={technical_divergence:.1f}")
    if "technical_risk" in analyst_focus:
        trigger_reasons.append("analyst_focus:technical_risk")
    if semantic_priority >= 4:
        trigger_reasons.append(f"semantic_priority_boost={semantic_priority}")
    elif semantic_priority <= -3:
        trigger_reasons.append(f"semantic_priority_penalty={semantic_priority}")
    if applied_controls.get("force_risk_review"):
        trigger_reasons.append("control:force_risk_review")
    if applied_controls.get("risk_hardening"):
        trigger_reasons.append("control:risk_hardening")
    if applied_controls.get("debate_round_limit") is not None:
        trigger_reasons.append(f"control:debate_round_limit={applied_controls.get('debate_round_limit')}")
    if applied_controls.get("risk_round_limit") is not None:
        trigger_reasons.append(f"control:risk_round_limit={applied_controls.get('risk_round_limit')}")

    route_decision_snapshot = {
        "route_family": route_decision.get("route_family", ""),
        "policy_role": route_decision.get("policy_role", ""),
        "capital_quality": route_decision.get("capital_quality", ""),
        "conflict_tier": route_decision.get("conflict_tier", ""),
        "semantic_priority": semantic_priority,
        "debate_rounds": route_decision.get("debate_rounds", ""),
        "debate_risk_weight": route_decision.get("debate_risk_weight", ""),
        "analyst_focus": list(route_decision.get("analyst_focus", []) or []),
        "selected_analysts": list(route_decision.get("selected_analysts", []) or []),
    }

    return {
        "semantic_trigger_slots": trigger_slots,
        "semantic_trigger_reasons": trigger_reasons,
        "semantic_priority": semantic_priority,
        "route_decision_snapshot": route_decision_snapshot,
    }


def create_orchestration_event(
    node: str,
    stage: str,
    phase: str,
    next_stage: str,
    compression_required: bool,
    context_estimate: int = 0,
    route_rule: str = "",
    route_reason: str = "",
    applied_controls: Dict[str, Any] | None = None,
    semantic_trigger_audit: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Create a new orchestration event with current timestamp.

    Args:
        node: Name of the node that produced this event
        stage: Current stage at time of event
        phase: Current phase at time of event
        next_stage: Next stage target at time of event
        compression_required: Whether compression is required
        context_estimate: Estimated context length in characters

    Returns:
        A new OrchestrationEvent dictionary
    """
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": node,
        "stage": stage,
        "phase": phase,
        "next_stage": next_stage,
        "compression_required": compression_required,
        "compression_triggered": compression_required,
        "context_estimate": context_estimate,
        "route_rule": route_rule,
        "route_reason": route_reason,
        "applied_controls": dict(applied_controls or {}),
        "semantic_trigger_audit": dict(semantic_trigger_audit or {}),
    }


def append_orchestration_event(
    existing_trail: List[Dict[str, Any]] | None,
    event: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Append a new event to the existing event trail.

    Args:
        existing_trail: Current event trail (can be None or empty)
        event: New event to append

    Returns:
        Updated event trail with the new event appended
    """
    if existing_trail is None:
        return [event]
    trail = list(existing_trail)
    trail.append(event)
    return trail


def build_orchestration_event(
    node_name: str,
    orchestration: Dict[str, Any],
    context_estimate: int = 0,
    route_rule: str | None = None,
    route_reason: str | None = None,
    applied_controls: Dict[str, Any] | None = None,
    semantic_trigger_audit: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build an orchestration event from current orchestration state.

    This is a convenience function that extracts relevant fields from
    the orchestration dict and creates a properly formatted event.

    Args:
        node_name: Name of the current node
        orchestration: Current orchestration state dict
        context_estimate: Optional context size estimate

    Returns:
        A new OrchestrationEvent dictionary
    """
    return create_orchestration_event(
        node=node_name,
        stage=str(orchestration.get("stage", "")),
        phase=str(orchestration.get("phase", "")),
        next_stage=str(orchestration.get("next_stage", "")),
        compression_required=bool(orchestration.get("compression_required", False)),
        context_estimate=context_estimate,
        route_rule=str(route_rule if route_rule is not None else orchestration.get("route_rule", "")),
        route_reason=str(route_reason if route_reason is not None else orchestration.get("route_reason", "")),
        applied_controls=dict(applied_controls if applied_controls is not None else orchestration.get("applied_controls", {}) or {}),
        semantic_trigger_audit=dict(
            semantic_trigger_audit
            if semantic_trigger_audit is not None
            else orchestration.get("semantic_trigger_audit", {}) or {}
        ),
    )


def get_event_trail_summary(event_trail: List[Dict[str, Any]] | None) -> str:
    """Generate a human-readable summary of the event trail.

    Args:
        event_trail: The event trail to summarize

    Returns:
        A formatted string summarizing the route taken
    """
    if not event_trail:
        return "No orchestration events recorded."

    lines = ["=== Orchestration Route Summary ==="]
    for i, event in enumerate(event_trail, 1):
        node = event.get("node", "unknown")
        stage = event.get("stage", "")
        phase = event.get("phase", "")
        compression = "Y" if event.get("compression_triggered") else "N"
        lines.append(
            f"{i}. {node} | phase={phase} stage={stage} | compression={compression}"
        )
        audit = dict(event.get("semantic_trigger_audit", {}) or {})
        reasons = list(audit.get("semantic_trigger_reasons", []) or [])
        if reasons:
            lines.append(f"   semantic_triggers={', '.join(reasons[:4])}")

    final = event_trail[-1]
    lines.append(f"\nFinal route: {final.get('next_stage', 'N/A')}")
    lines.append(f"Final reason: {final.get('phase', 'N/A')}")

    return "\n".join(lines)


def sync_report_updates(
    report_key: str,
    report_value: str,
    messages: list[Any] | None = None,
    sender: str | None = None,
) -> Dict[str, Any]:
    """Return a dual-write update for legacy and structured report state."""
    key_map = {
        "market": "market_report",
        "sentiment": "sentiment_report",
        "news": "news_report",
        "fundamentals": "fundamentals_report",
    }
    if report_key not in key_map:
        raise ValueError(f"Unsupported report_key: {report_key}")

    update: Dict[str, Any] = {
        key_map[report_key]: report_value,
        "analyst_reports": {
            report_key: report_value,
        },
    }
    if messages is not None:
        update["messages"] = messages
    if sender is not None:
        update["sender"] = sender
    return update


def sync_decision_updates(
    decision_key: str,
    decision_value: str,
    sender: str | None = None,
) -> Dict[str, Any]:
    """Return a dual-write update for legacy and structured decision state."""
    key_map = {
        "investment_plan": "investment_plan",
        "trader_plan": "trader_investment_plan",
        "final_trade_decision": "final_trade_decision",
    }
    if decision_key not in key_map:
        raise ValueError(f"Unsupported decision_key: {decision_key}")

    update: Dict[str, Any] = {
        key_map[decision_key]: decision_value,
        "decision_blocks": {
            decision_key: decision_value,
        },
    }
    if sender is not None:
        update["sender"] = sender
    return update


def sync_investment_debate_update(
    debate_state: Dict[str, Any],
    sender: str | None = None,
) -> Dict[str, Any]:
    """Return a dual-write update for investment debate state."""
    update: Dict[str, Any] = {
        "investment_debate_state": debate_state,
        "debate_blocks": {
            "investment": debate_state,
        },
    }
    if sender is not None:
        update["sender"] = sender
    return update


def sync_risk_debate_update(
    debate_state: Dict[str, Any],
    sender: str | None = None,
) -> Dict[str, Any]:
    """Return a dual-write update for risk debate state."""
    update: Dict[str, Any] = {
        "risk_debate_state": debate_state,
        "debate_blocks": {
            "risk": debate_state,
        },
    }
    if sender is not None:
        update["sender"] = sender
    return update


def normalize_next_stage(next_stage: str | None, default_stage: str) -> str:
    """Collapse handoff stage aliases back to their execution target."""
    if not next_stage:
        return default_stage
    if next_stage.endswith("_handoff"):
        return next_stage[: -len("_handoff")]
    return next_stage


# ---------------------------------------------------------------------------
# Context-size proxy thresholds (character counts)
#
# These drive "compression handoff" routing: when an intermediate output
# exceeds a threshold, the graph routes through a handoff node that
# compresses the context before the next phase. Character length is a
# proxy for token count — tune here only, do not inline magic numbers.
# ---------------------------------------------------------------------------
RESEARCH_MANAGER_HISTORY_CHARS = 4000
RESEARCH_MANAGER_DECISION_CHARS = 2500
TRADER_PLAN_CHARS = 3200
TRADER_OUTPUT_CHARS = 2200
RISK_HISTORY_CHARS = 3500
RISK_ARGUMENT_CHARS = 1600


def determine_research_manager_next_stage(
    debate_history: str,
    manager_decision: str,
    compression_notes: str,
) -> str:
    """Choose whether research output should go straight to trader or through handoff."""
    has_notes = bool(str(compression_notes).strip())
    if has_notes:
        return "trader"

    history_len = len(str(debate_history))
    decision_len = len(str(manager_decision))
    if history_len >= RESEARCH_MANAGER_HISTORY_CHARS or decision_len >= RESEARCH_MANAGER_DECISION_CHARS:
        return "trader_handoff"
    return "trader"


def determine_trader_next_stage(
    investment_plan: str,
    trader_output: str,
    compression_notes: str,
) -> str:
    """Choose whether trader output should go straight to risk or through handoff."""
    has_notes = bool(str(compression_notes).strip())
    if has_notes:
        return "risk"

    plan_len = len(str(investment_plan))
    output_len = len(str(trader_output))
    if plan_len >= TRADER_PLAN_CHARS or output_len >= TRADER_OUTPUT_CHARS:
        return "risk_handoff"
    return "risk"


def determine_risk_next_stage(
    risk_history: str,
    latest_argument: str,
    compression_notes: str,
) -> str:
    """Choose whether risk debate should go straight to portfolio or through handoff."""
    has_notes = bool(str(compression_notes).strip())
    if has_notes:
        return "portfolio"

    history_len = len(str(risk_history))
    argument_len = len(str(latest_argument))
    if history_len >= RISK_HISTORY_CHARS or argument_len >= RISK_ARGUMENT_CHARS:
        return "portfolio_handoff"
    return "portfolio"


def has_full_risk_debate_coverage(risk_debate_state: Dict[str, Any]) -> bool:
    """Return whether aggressive, conservative, and neutral views are all present."""
    return all(
        bool(str(risk_debate_state.get(key, "")).strip())
        for key in (
            "current_aggressive_response",
            "current_conservative_response",
            "current_neutral_response",
        )
    )


def determine_risk_follow_up_speaker(risk_debate_state: Dict[str, Any]) -> str:
    """Choose which risk analyst should speak next to complete the debate cycle."""
    if not str(risk_debate_state.get("current_aggressive_response", "")).strip():
        return "Aggressive Analyst"
    if not str(risk_debate_state.get("current_conservative_response", "")).strip():
        return "Conservative Analyst"
    if not str(risk_debate_state.get("current_neutral_response", "")).strip():
        return "Neutral Analyst"

    latest_speaker = str(risk_debate_state.get("latest_speaker", ""))
    if latest_speaker.startswith("Aggressive"):
        return "Conservative Analyst"
    if latest_speaker.startswith("Conservative"):
        return "Neutral Analyst"
    return "Aggressive Analyst"


def determine_risk_debate_exit_stage(
    risk_debate_state: Dict[str, Any],
    compression_notes: str,
) -> str:
    """Choose whether the finished risk debate should go direct to portfolio or handoff first."""
    latest_argument = " ".join(
        str(risk_debate_state.get(key, "")).strip()
        for key in (
            "current_aggressive_response",
            "current_conservative_response",
            "current_neutral_response",
        )
    ).strip()
    return determine_risk_next_stage(
        risk_history=str(risk_debate_state.get("history", "")),
        latest_argument=latest_argument,
        compression_notes=compression_notes,
    )


def validate_debate_state(debate_state: Dict[str, Any], debate_type: str = "investment") -> Dict[str, Any]:
    """Validate debate state and return validation report.

    Args:
        debate_state: The debate state to validate
        debate_type: Either "investment" or "risk"

    Returns:
        Dict with validation results including is_valid and any issues found
    """
    issues = []

    if debate_type == "investment":
        required_fields = ["bull_history", "bear_history", "history", "current_response"]
        for field in required_fields:
            if field not in debate_state:
                issues.append(f"Missing required field: {field}")

        count = debate_state.get("count", 0)
        if not isinstance(count, int) or count < 0:
            issues.append(f"Invalid count value: {count}")
    else:
        required_fields = [
            "aggressive_history", "conservative_history", "neutral_history",
            "history", "latest_speaker"
        ]
        for field in required_fields:
            if field not in debate_state:
                issues.append(f"Missing required field: {field}")

        count = debate_state.get("count", 0)
        if not isinstance(count, int) or count < 0:
            issues.append(f"Invalid count value: {count}")

    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "debate_type": debate_type,
    }


def validate_orchestration_state(orchestration: Dict[str, Any]) -> Dict[str, Any]:
    """Validate orchestration state and return validation report.

    Args:
        orchestration: The orchestration state to validate

    Returns:
        Dict with validation results including is_valid and any issues found
    """
    issues = []
    warnings = []

    valid_stages = ["analysis", "analyst", "research", "trader", "risk", "risk_finalize", "portfolio", "completed", "error"]
    stage = orchestration.get("stage", "")
    if stage and stage not in valid_stages:
        warnings.append(f"Unusual stage value: {stage}")

    valid_phases = ["analyst", "research", "trader", "risk", "completed", "error"]
    phase = orchestration.get("phase", "")
    if phase and phase not in valid_phases:
        warnings.append(f"Unusual phase value: {phase}")

    completed = orchestration.get("completed", False)
    if not isinstance(completed, bool):
        issues.append(f"completed should be bool, got: {type(completed)}")

    event_trail = orchestration.get("event_trail")
    if event_trail is not None and not isinstance(event_trail, list):
        issues.append(f"event_trail should be list, got: {type(event_trail)}")

    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def sanitize_debate_count(count: int, max_allowed: int = 1000) -> int:
    """Sanitize debate count to prevent overflow.

    Args:
        count: The raw count value
        max_allowed: Maximum allowed count value

    Returns:
        Sanitized count value
    """
    if not isinstance(count, int):
        try:
            count = int(count)
        except (ValueError, TypeError):
            count = 0

    if count < 0:
        return 0

    if count > max_allowed:
        return max_allowed

    return count
