"""Skill loader — discovers and parses .md skill files from directories.

Supports two formats:
1. New directory format (priority):
   - bundled_dir/category/skill_name/SKILL.md
   - bundled_dir/category/skill_name/references/*.md  (optional)
2. Legacy flat file format (backward compat):
   - bundled_dir/category/skill_name.md
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from .types import SkillDefinition, SkillReference
from .registry import SkillRegistry


def load_skill_registry(bundled_dir: Path) -> SkillRegistry:
    """Load all skills from a bundled directory into a SkillRegistry.

    Convention:
    - bundled_dir/ 下的每个子目录名 = category（如 market, news, fundamentals）
    - 每个 category 下优先扫描子目录格式（SKILL.md + references/），再扫描 .md 文件
    - 同名 skill 存在时，子目录格式优先于 .md 文件
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

        # Collect directory-based skill stems so we skip .md files with the same name
        dir_based_stems: Set[str] = set()
        for skill_dir in sorted(category_dir.iterdir()):
            if skill_dir.is_dir():
                dir_based_stems.add(skill_dir.name)

        # Load directory-format skills first (priority)
        for skill_dir in sorted(category_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill = _load_skill_directory(skill_dir, category)
            if skill is not None:
                registry.register(skill)

        # Load flat-file skills (backward compat), skipping those already loaded as dirs
        for md_file in sorted(category_dir.glob("*.md")):
            if md_file.stem in dir_based_stems:
                continue
            skill = _load_skill_file(md_file, category)
            if skill is not None:
                registry.register(skill)

    return registry


def _load_skill_directory(skill_dir: Path, category: str) -> Optional[SkillDefinition]:
    """Load a skill from a directory format (SKILL.md + optional references/ subdir).

    Returns None if SKILL.md does not exist (caller can fall back to flat .md format).
    """
    main_file = skill_dir / "SKILL.md"
    if not main_file.exists():
        return None

    content = main_file.read_text(encoding="utf-8")
    name_from_dir = skill_dir.name
    frontmatter: Dict[str, Any] = {}
    body = content

    if content.startswith("---\n"):
        end_marker = content.find("\n---\n", 4)
        if end_marker != -1:
            yaml_text = content[4:end_marker]
            body = content[end_marker + 5:]
            try:
                frontmatter = yaml.safe_load(yaml_text) or {}
            except yaml.YAMLError:
                frontmatter = {}

    name = frontmatter.get("name") or name_from_dir
    description = frontmatter.get("description", f"Skill: {name}")
    applies_to = frontmatter.get("applies_to_analyst", [])
    version = str(frontmatter.get("version", "1.0"))
    metadata = {
        k: v for k, v in frontmatter.items()
        if k not in ("name", "description", "applies_to_analyst", "version")
    }

    references: List[SkillReference] = []
    ref_dir = skill_dir / "references"
    if ref_dir.is_dir():
        for ref_file in sorted(ref_dir.glob("*.md")):
            ref_content = ref_file.read_text(encoding="utf-8")
            references.append(SkillReference(
                filename=ref_file.name,
                content=ref_content.strip(),
            ))

    return SkillDefinition(
        name=name,
        description=description,
        category=category,
        applies_to_analyst=applies_to,
        version=version,
        content=body.strip(),
        references=references,
        metadata=metadata,
    )


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
            body = content[end_marker + 5:]
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
