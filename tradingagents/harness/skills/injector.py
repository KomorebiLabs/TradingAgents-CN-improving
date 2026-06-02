"""tradingagents/harness/skills/injector.py"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .types import DecisionType, SkillDefinition
from .registry import SkillRegistry
from .loader import load_skill_registry
from .mapping import DecisionSkillMapper, DECISION_SKILL_MAPPING

# Backward-compatible re-export: old code imports this from injector.py
ANALYST_SKILL_MAPPING = DECISION_SKILL_MAPPING

# Analyst-type string → DecisionType mapping (for backward compat with analyst callers)
ANALYST_TYPE_MAPPING: Dict[str, "DecisionType"] = {
    "market": DecisionType.OFFENSIVE,
    "news": DecisionType.CATALYST,
    "fundamentals": DecisionType.VALUATION,
    "social": DecisionType.SENTIMENT,
}


# Skill 使用声明指令（注入到 prompt 末尾）
SKILL_USAGE_INSTRUCTION = """
When your analysis is complete, include a <SkillsUsed> block listing every skill
you actively applied during this reasoning. Format:

<SkillsUsed>
- <skill-name>: <one-sentence justification of how you used it>
- <skill-name>
</SkillsUsed>

Skills you were provided are: {injected_skill_names}
Only declare skills you actually referenced. If none were used, write:
<SkillsUsed>
- (none)
</SkillsUsed>
""".strip()


class SkillInjector:
    """Injects layered skill content into Agent prompts.

    Supports:
    - Decision-type based routing (replaces analyst-type routing)
    - Round-aware injection (round 1 = core only, round N = full + references)
    - Counter-round skill injection (Bull gets fraud-detection when countering Bear)
    """

    def __init__(
        self,
        bundled_dir: Optional[Path] = None,
        mapping: Optional[Dict[DecisionType, List[str]] | None] = None,
    ) -> None:
        if bundled_dir is None:
            bundled_dir = Path(__file__).parent / "bundled"
        self._bundled_dir = bundled_dir
        self._registry: Optional[SkillRegistry] = None
        self._mapper = DecisionSkillMapper(mapping)

    def _ensure_registry(self) -> SkillRegistry:
        if self._registry is None:
            self._registry = load_skill_registry(self._bundled_dir)
        return self._registry

    def build_skill_section(
        self,
        decision_type: DecisionType | str,
        node_name: str | None = None,
        debate_round: int = 1,
        is_counter_round: bool = False,
        include_references: bool = False,
    ) -> Tuple[str, List[str]]:
        """Build skill Markdown section for a given decision type.

        Args:
            decision_type: Either a DecisionType enum value, or one of the analyst-type
                strings ("market", "news", "fundamentals", "social") which are
                automatically mapped to the appropriate DecisionType.
        Returns:
            Tuple of (section_text, injected_skill_names)
        """
        # Resolve analyst-type string to DecisionType if needed.
        # DecisionType(str, Enum) is a str subclass, so check for DecisionType first.
        if not isinstance(decision_type, DecisionType):
            if isinstance(decision_type, str):
                mapped = ANALYST_TYPE_MAPPING.get(decision_type)
                if mapped is None:
                    return "", []
                decision_type = mapped
            else:
                return "", []

        registry = self._ensure_registry()
        skill_names = self._mapper.get_skill_names(
            decision_type=decision_type,
            node_name=node_name,
            debate_round=debate_round,
            is_counter_round=is_counter_round,
        )
        skills = registry.get_skills_by_names(skill_names)

        if not skills:
            return "", []

        sections = ["# Analytical Skills Available", ""]
        for skill in skills:
            if include_references:
                sections.append(skill.to_full_section())
            else:
                sections.append(skill.to_core_section())
            sections.append("")

        return "\n".join(sections), skill_names

    def inject(
        self,
        decision_type: DecisionType,
        existing_prompt: str,
        node_name: str | None = None,
        debate_round: int = 1,
        is_counter_round: bool = False,
        is_adjudication: bool = False,
    ) -> Tuple[str, List[str]]:
        """Append skill content + usage instruction to an existing system prompt.

        Returns:
            Tuple of (full_prompt, injected_skill_names)
        """
        strategy = self._mapper.get_injection_strategy(
            debate_round=debate_round,
            is_adjudication=is_adjudication,
        )
        include_references = strategy["include_references"]

        skill_section, skill_names = self.build_skill_section(
            decision_type=decision_type,
            node_name=node_name,
            debate_round=debate_round,
            is_counter_round=is_counter_round,
            include_references=include_references,
        )
        if not skill_section:
            return existing_prompt, []

        separator = (
            "\n\n"
            + "=" * 60 + "\n"
            + "## INJECTED ANALYTICAL SKILLS\n"
            + "=" * 60 + "\n"
        )

        skill_usage_instruction = SKILL_USAGE_INSTRUCTION.format(
            injected_skill_names=", ".join(sorted(skill_names)),
        )

        full_prompt = (
            existing_prompt
            + separator
            + skill_section
            + "\n\n"
            + skill_usage_instruction
        )
        return full_prompt, skill_names


# Backward-compatible alias for existing analyst-type callers
class AnalystSkillInjector:
    """Legacy wrapper: maps analyst type to decision type for backward compat."""

    ANALYST_TO_DECISION: Dict[str, DecisionType] = {
        "market": DecisionType.OFFENSIVE,
        "news": DecisionType.CATALYST,
        "fundamentals": DecisionType.VALUATION,
        "social": DecisionType.SENTIMENT,
    }

    def __init__(self) -> None:
        self._delegate = SkillInjector()

    def inject_into_prompt(
        self,
        analyst_type: str,
        existing_prompt: str,
        include_references: bool = False,
    ) -> str:
        decision_type = self.ANALYST_TO_DECISION.get(analyst_type, DecisionType.VALUATION)
        section, _ = self._delegate.build_skill_section(
            decision_type=decision_type,
            include_references=include_references,
        )
        if not section:
            return existing_prompt
        separator = (
            "\n\n"
            + "=" * 60 + "\n"
            + "## INJECTED ANALYTICAL SKILLS\n"
            + "=" * 60 + "\n"
        )
        return existing_prompt + separator + section
