"""tradingagents/harness/skills/audit.py"""
from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime, timezone
from typing import List

from .types import SkillAuditEntry, SkillUsageRecord


# Skill usage declaration XML tags (following existing <decision> convention)
SKILL_USAGE_PATTERN = re.compile(
    r"<SkillsUsed>(.*?)</SkillsUsed>",
    re.DOTALL | re.IGNORECASE,
)
SKILL_ITEM_PATTERN = re.compile(
    r"-\s*([a-z0-9_-]+)(?:\s*:\s*(.+))?",
    re.IGNORECASE,
)


def parse_skill_usage(content: str) -> List[SkillUsageRecord]:
    """Parse <SkillsUsed> declarations from LLM response.

    Parses format:
    <SkillsUsed>
    - breakout-recognition: 用于验证突破有效性
    - volume-analysis
    </SkillsUsed>

    Returns:
        List of SkillUsageRecord parsed from the response.
        Empty list if no <SkillsUsed> block found.
    """
    records: List[SkillUsageRecord] = []
    match = SKILL_USAGE_PATTERN.search(content)
    if not match:
        return records

    block = match.group(1)
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        item_match = SKILL_ITEM_PATTERN.match(line)
        if item_match:
            skill_name = item_match.group(1).strip().lower()
            justification = item_match.group(2).strip() if item_match.group(2) else ""
        elif line.startswith("-") and "(none)" in line.lower():
            skill_name = "(none)"
            justification = ""
        else:
            continue
        records.append(SkillUsageRecord(
            skill_name=skill_name,
            decision_type="",
            layer="core",
            usage_type="declared",
            justification=justification,
        ))
    return records


def build_skill_audit_entry(
    node_name: str,
    decision_type: str,
    debate_round: int,
    is_counter_round: bool,
    is_adjudication: bool,
    injected_skill_names: List[str],
    response_content: str,
) -> SkillAuditEntry:
    """Build complete audit record for one Agent node invocation.

    Compares "injected skills" vs "LLM declared skills":
    - injected: all skills SkillInjector added this round
    - declared: skills LLM listed in <SkillsUsed>
    - unmatched_declared: LLM declared but we didn't inject (cross-round or other source)
    - skill_match_rate: declared / injected ratio
    """
    declared_records = parse_skill_usage(response_content)
    declared_names = {r.skill_name for r in declared_records}
    injected_set = set(injected_skill_names)

    matched = declared_names & injected_set
    unmatched = sorted(declared_names - injected_set)
    match_rate = len(matched) / len(injected_set) if injected_set else 0.0

    for r in declared_records:
        r.decision_type = decision_type

    return SkillAuditEntry(
        node_name=node_name,
        decision_type=decision_type,
        debate_round=debate_round,
        is_counter_round=is_counter_round,
        is_adjudication=is_adjudication,
        injected_skills=sorted(injected_set),
        declared_skills=declared_records,
        unmatched_declared=unmatched,
        skill_match_rate=round(match_rate, 3),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def build_skill_audit_summary(entries: List[SkillAuditEntry]) -> dict:
    """Aggregate multiple audit records into a readable summary report for logging/debugging."""
    if not entries:
        return {"summary": "No skill audit entries."}

    total_injected = sum(len(e.injected_skills) for e in entries)
    total_declared = sum(len(e.declared_skills) for e in entries)
    avg_match_rate = sum(e.skill_match_rate for e in entries) / len(entries)
    all_declared = sorted({r.skill_name for e in entries for r in e.declared_skills})
    all_injected = sorted({s for e in entries for s in e.injected_skills})

    return {
        "total_invocations": len(entries),
        "total_skills_injected": total_injected,
        "total_skills_declared": total_declared,
        "avg_match_rate": round(avg_match_rate, 3),
        "all_declared_skills": all_declared,
        "all_injected_skills": all_injected,
        "decluttered_skills": sorted(set(all_injected) - set(all_declared)),
        "per_node": [
            {
                "node": e.node_name,
                "round": e.debate_round,
                "match_rate": e.skill_match_rate,
                "injected": e.injected_skills,
                "declared": [r.skill_name for r in e.declared_skills],
            }
            for e in entries
        ],
    }
