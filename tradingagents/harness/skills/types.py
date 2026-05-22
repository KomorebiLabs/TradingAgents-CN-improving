"""Skill definition types and models."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SkillDefinition(BaseModel):
    """A single skill definition with metadata and content."""

    name: str = Field(description="Unique skill name (e.g. fraud_detection)")
    description: str = Field(description="Short description for display and routing")
    category: Optional[str] = Field(default=None, description="Skill category (e.g. market, fundamentals)")
    applies_to_analyst: List[str] = Field(
        default_factory=list,
        description="Which analyst types this skill applies to (e.g. [fundamentals, news])",
    )
    version: str = Field(default="1.0", description="Skill version")
    content: str = Field(default="", description="Full Markdown skill content")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extra metadata parsed from YAML frontmatter",
    )

    def to_prompt_section(self) -> str:
        """Render this skill as a Markdown section for Agent prompt injection."""
        return f"## Skill: {self.name}\n\n{self.content}"
