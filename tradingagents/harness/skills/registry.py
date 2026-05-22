"""In-memory skill registry with analyst-type filtering."""
from typing import Dict, List, Optional

from .types import SkillDefinition


class SkillRegistry:
    """In-memory registry for skill definitions. Supports name lookup and analyst-type filtering."""

    def __init__(self) -> None:
        self._skills: Dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        """Register a skill. Later registrations overwrite earlier ones with the same name."""
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[SkillDefinition]:
        """Get a skill by name. Returns None if not found."""
        return self._skills.get(name)

    def list_skills(self) -> List[SkillDefinition]:
        """List all registered skills."""
        return list(self._skills.values())

    def get_skills_for_analyst(self, analyst_type: str) -> List[SkillDefinition]:
        """Return all skills that apply to a given analyst type (or skills with no restriction)."""
        return [
            s for s in self._skills.values()
            if not s.applies_to_analyst or analyst_type in s.applies_to_analyst
        ]

    def get_skills_by_names(self, names: List[str]) -> List[SkillDefinition]:
        """Return skills matching the given name list. Unknown names are silently skipped."""
        return [self._skills[n] for n in names if n in self._skills]
