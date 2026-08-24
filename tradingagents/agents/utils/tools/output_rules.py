"""Output-format enforcement helpers and message utilities."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - optional runtime dependency
    from langchain_core.messages import HumanMessage, RemoveMessage
except Exception:  # pragma: no cover
    class HumanMessage:
        def __init__(self, content: str):
            self.content = content

    class RemoveMessage:
        def __init__(self, id=None):
            self.id = id

def enforce_execution_profile_output(content: str, execution_profile: Dict[str, Any]) -> str:
    rendered = str(content or "")
    must_include = list(execution_profile.get("evidence_must_include", []) or [])
    conclusion_mode = str(execution_profile.get("conclusion_mode", "standard") or "standard")
    missing_evidence = [
        item for item in must_include if str(item).lower() not in rendered.lower()
    ]

    template_checks: List[str] = []
    if conclusion_mode == "risk_first":
        if "risk" not in rendered.lower():
            template_checks.append("missing_risk_section")
    elif conclusion_mode == "leader_continuation_vs_failure":
        if "continuation" not in rendered.lower():
            template_checks.append("missing_continuation_section")
        if "failure" not in rendered.lower() and "invalidation" not in rendered.lower():
            template_checks.append("missing_failure_or_invalidation_section")
    elif conclusion_mode == "member_quality_confirmation":
        if "quality" not in rendered.lower():
            template_checks.append("missing_quality_section")

    if missing_evidence:
        rendered += (
            f"\n\n[execution_profile_evidence_check] missing={missing_evidence}"
        )
    if template_checks:
        rendered += (
            f"\n\n[execution_profile_structure_check] mode={conclusion_mode} missing={template_checks}"
        )
    return rendered


def suppress_repeated_tool_calls(
    result: Any,
    prior_messages: List[Any],
    role: str,
    max_tool_rounds: int = 3,
) -> Dict[str, int]:
    """Bound one analyst tool loop by signature dedupe and a hard round cap."""
    seen = set()
    prior_tool_rounds = 0
    for message in prior_messages:
        calls = list(getattr(message, "tool_calls", None) or [])
        if calls:
            prior_tool_rounds += 1
        for call in calls:
            signature = (
                str(call.get("name") or ""),
                json.dumps(call.get("args") or {}, sort_keys=True, ensure_ascii=False, default=str),
            )
            seen.add(signature)

    current_calls = list(getattr(result, "tool_calls", None) or [])
    budget_exhausted = prior_tool_rounds >= max(1, int(max_tool_rounds))
    kept = []
    suppressed = 0
    for call in current_calls:
        signature = (
            str(call.get("name") or ""),
            json.dumps(call.get("args") or {}, sort_keys=True, ensure_ascii=False, default=str),
        )
        if budget_exhausted or signature in seen:
            suppressed += 1
            continue
        seen.add(signature)
        kept.append(call)

    result.tool_calls = kept
    if suppressed and not kept and not str(getattr(result, "content", "") or "").strip():
        result.content = (
            f"## {role} data availability\n\n"
            "Status: unavailable. The analyst tool-loop reached its retry "
            "budget or requested only calls already attempted with identical "
            "arguments. Further calls were stopped to prevent token "
            "amplification. No unsupported "
            "numeric conclusion may be inferred from this missing evidence."
        )
    return {"suppressed": suppressed, "remaining": len(kept)}


def enforce_skill_usage(
    content: str,
    injected_skill_names: List[str],
    node_name: str,
    decision_type: str,
    debate_round: int,
    is_counter_round: bool,
    is_adjudication: bool,
) -> dict:
    """Verify LLM response skill usage declarations and build audit record.

    If LLM declares no skills, append a reminder to content (does not modify existing content).
    Returns dict with updated content and audit_entry for AgentState writing.
    """
    from tradingagents.harness.skills.audit import build_skill_audit_entry

    entry = build_skill_audit_entry(
        node_name=node_name,
        decision_type=decision_type,
        debate_round=debate_round,
        is_counter_round=is_counter_round,
        is_adjudication=is_adjudication,
        injected_skill_names=injected_skill_names,
        response_content=content,
    )

    result_content = content
    if entry.declared_skills and entry.declared_skills[0].skill_name == "(none)":
        result_content = content.rstrip() + (
            "\n\n[skill_usage_reminder] No skills were declared. "
            "Consider if any of these were applicable: "
            + ", ".join(injected_skill_names[:5])
        )

    return {
        "content": result_content,
        "audit_entry": asdict(entry),
    }


def create_msg_delete(completed_role: str = "analyst"):
    def delete_messages(state):
        """Clear tool-loop history and leave exactly one stable handoff."""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]
        placeholder = HumanMessage(
            content=(
                "[SYSTEM_HANDOFF] Prior tool-loop messages were cleared. "
                "Read canonical state fields and execute only your assigned role. "
                "This handoff is not evidence."
            ),
            id=f"phase-handoff:{completed_role}",
        )
        return {"messages": removal_operations + [placeholder]}

    return delete_messages
