"""tradingagents/harness/skills/types.py"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class DecisionType(str, Enum):
    OFFENSIVE = "offensive"
    DEFENSIVE = "defensive"
    VALUATION = "valuation"
    CATALYST = "catalyst"
    SENTIMENT = "sentiment"


class SkillLayer(str, Enum):
    CORE = "core"
    REFERENCE = "ref"


@dataclass
class SkillReference:
    """A reference document under the references/ subdirectory of a skill directory."""
    filename: str
    content: str

    def to_prompt_section(self) -> str:
        return f"**Reference: {self.filename}**\n{self.content}"


@dataclass
class SkillDefinition:
    """A single skill definition with metadata and layered content.

    Supports:
    - content: SKILL.md body (CORE layer)
    - references: List[SkillReference] from references/ subdir (REFERENCE layer)
    """
    name: str
    description: str
    decision_types: List[DecisionType] = field(default_factory=list)
    version: str = "1.0"
    category: Optional[str] = None
    applies_to_analyst: List[str] = field(default_factory=list)
    content: str = ""
    references: List[SkillReference] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_prompt_section(self, include_references: bool = False) -> str:
        parts = [f"## Skill: {self.name}\n\n{self.content}"]
        if include_references and self.references:
            parts.append("\n**References:**")
            for ref in self.references:
                parts.append(f"\n{ref.to_prompt_section()}")
        return "\n".join(parts)

    def to_core_section(self) -> str:
        return self.to_prompt_section(include_references=False)

    def to_full_section(self) -> str:
        return self.to_prompt_section(include_references=True)


@dataclass
class SkillUsageRecord:
    """Record of a skill actually used by an LLM in a response."""
    skill_name: str
    decision_type: str = ""
    layer: str = "core"
    usage_type: str = "declared"
    justification: str = ""


@dataclass
class SkillAuditEntry:
    """Complete audit record for a single Agent node invocation."""
    node_name: str
    decision_type: str
    debate_round: int
    is_counter_round: bool
    is_adjudication: bool
    injected_skills: List[str] = field(default_factory=list)
    declared_skills: List[SkillUsageRecord] = field(default_factory=list)
    unmatched_declared: List[str] = field(default_factory=list)
    skill_match_rate: float = 0.0
    timestamp: str = ""
