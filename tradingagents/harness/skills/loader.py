"""Skill loader — discovers and parses .md skill files from directories."""
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .types import SkillDefinition
from .registry import SkillRegistry


def load_skill_registry(bundled_dir: Path) -> SkillRegistry:
    """Load all .md skill files from a directory tree into a SkillRegistry.

    Convention:
    - bundled_dir/ 下的每个子目录名 = category（如 market, news, fundamentals）
    - 子目录下每个 *.md 文件 = 一个 Skill
    - 文件名（不含扩展名）= Skill 的默认 name
    - YAML frontmatter 中 name 字段覆盖文件名
    """
    registry = SkillRegistry()
    if not bundled_dir.exists():
        return registry

    for category_dir in sorted(bundled_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name

        for md_file in sorted(category_dir.glob("*.md")):
            skill = _load_skill_file(md_file, category)
            if skill is not None:
                registry.register(skill)

    return registry


def _load_skill_file(path: Path, category: str) -> Optional[SkillDefinition]:
    """Load and parse a single .md skill file.

    Parses YAML frontmatter (--- ... ---) at the top of the file.
    Falls back to filename-based metadata if no frontmatter is present.
    """
    content = path.read_text(encoding="utf-8")
    name_from_file = path.stem
    frontmatter: Dict[str, Any] = {}
    body = content

    if content.startswith("---\n"):
        end_marker = content.find("\n---\n", 4)
        if end_marker != -1:
            yaml_text = content[4:end_marker]
            body = content[end_marker + 5 :]
            try:
                frontmatter = yaml.safe_load(yaml_text) or {}
            except yaml.YAMLError:
                frontmatter = {}

    name = frontmatter.get("name") or name_from_file
    description = frontmatter.get("description", f"Skill: {name}")
    applies_to = frontmatter.get("applies_to_analyst", [])
    version = str(frontmatter.get("version", "1.0"))
    metadata = {
        k: v for k, v in frontmatter.items()
        if k not in ("name", "description", "applies_to_analyst", "version")
    }

    return SkillDefinition(
        name=name,
        description=description,
        category=category,
        applies_to_analyst=applies_to,
        version=version,
        content=body.strip(),
        metadata=metadata,
    )


def load_skills_from_dirs(directories: List[Path]) -> List[SkillDefinition]:
    """Load skills from multiple directories (for bundled + user overlay support)."""
    all_skills: List[SkillDefinition] = []
    for directory in directories:
        registry = load_skill_registry(directory)
        all_skills.extend(registry.list_skills())
    return all_skills
