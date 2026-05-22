"""SkillInjector — injects skill content into Agent system prompts by analyst type."""
from pathlib import Path
from typing import Dict, List, Optional

from .types import SkillDefinition
from .registry import SkillRegistry
from .loader import load_skill_registry


# Analyst type → list of skill names to load (Focused taxonomy)
ANALYST_SKILL_MAPPING: Dict[str, List[str]] = {
    "market": ["indicator-library", "trend-patterns", "volume-analysis", "breakout-recognition"],
    "news": ["policy-impact", "sector-rotation", "event-catalyst"],
    "fundamentals": ["fraud-detection", "valuation-methods", "growth-quality"],
    "social": ["sentiment-scoring", "crowd-behavior"],
}


class SkillInjector:
    """Injects skill content into Agent system prompts based on analyst type.

    Usage:
        injector = SkillInjector()  # loads bundled skills automatically
        skill_section = injector.build_skill_section("market")
        # append to analyst's system_message
    """

    def __init__(self, bundled_dir: Optional[Path] = None) -> None:
        if bundled_dir is None:
            bundled_dir = Path(__file__).parent / "bundled"
        self._bundled_dir = bundled_dir
        self._registry: Optional[SkillRegistry] = None

    def _ensure_registry(self) -> SkillRegistry:
        if self._registry is None:
            self._registry = load_skill_registry(self._bundled_dir)
        return self._registry

    def build_skill_section(self, analyst_type: str) -> str:
        """Build Markdown skill content for a given analyst type.

        Returns:
            A Markdown section listing all applicable skills, ready for prompt injection.
            Returns empty string if no skills match.
        """
        registry = self._ensure_registry()
        skill_names = ANALYST_SKILL_MAPPING.get(analyst_type, [])
        skills = registry.get_skills_by_names(skill_names)

        if not skills:
            return ""

        sections = [
            "# Analytical Skills Available",
            "",
        ]
        for skill in skills:
            sections.append(skill.to_prompt_section())
            sections.append("")

        return "\n".join(sections)

    def inject_into_prompt(
        self,
        analyst_type: str,
        existing_prompt: str,
    ) -> str:
        """Append skill content to an existing system prompt.

        Args:
            analyst_type: The analyst type (market/news/fundamentals/social)
            existing_prompt: The current system prompt string

        Returns:
            The existing prompt with skill content appended.
        """
        skill_section = self.build_skill_section(analyst_type)
        if not skill_section:
            return existing_prompt

        separator = (
            "\n\n"
            + "=" * 60 + "\n"
            + "## INJECTED ANALYTICAL SKILLS\n"
            + "=" * 60 + "\n"
        )
        return existing_prompt + separator + skill_section
