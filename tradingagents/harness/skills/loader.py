"""Skill loader — discovers and parses .md skill files from directories.

Supports two formats:
1. New directory format (priority):
   - bundled_dir/category/skill_name/SKILL.md
   - bundled_dir/category/skill_name/references/*.md  (optional)
2. Legacy flat file format (backward compat):
   - bundled_dir/category/skill_name.md
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from .types import DecisionType, SkillDefinition, SkillReference
from .registry import SkillRegistry


def _parse_decision_types(raw: Any) -> List[DecisionType]:
    """Parse decision_types field from YAML into DecisionType enum values.

    Accepts formats:
    - decision_types: [offensive, defensive]  (YAML strings)
    - decision_types: [DecisionType.OFFENSIVE, ...] (pyyaml evaluated as dicts — ignored)
    Returns empty list if field is absent or invalid.
    """
    if not raw:
        return []
    result: List[DecisionType] = []
    for item in (raw if isinstance(raw, list) else [raw]):
        if isinstance(item, DecisionType):
            result.append(item)
        elif isinstance(item, str):
            try:
                result.append(DecisionType(item.strip()))
            except ValueError:
                pass
        elif isinstance(item, dict) and "OFFENSIVE" in item:
            pass  # pyyaml evaluated as {'OFFENSIVE': 'offensive', ...} — skip
    return result


def _load_skill(
    raw_content: str,
    default_name: str,
    category: str,
) -> SkillDefinition:
    """Parse skill content from raw text (shared by directory and flat-file loaders).

    Args:
        raw_content: Raw file content (may include YAML frontmatter)
        default_name: Default name if frontmatter has no name
        category: Skill category (directory name)
    """
    frontmatter: Dict[str, Any] = {}
    body = raw_content

    if raw_content.startswith("---\n"):
        end_marker = raw_content.find("\n---\n", 4)
        if end_marker != -1:
            yaml_text = raw_content[4:end_marker]
            body = raw_content[end_marker + 5:]
            try:
                frontmatter = yaml.safe_load(yaml_text) or {}
            except yaml.YAMLError:
                frontmatter = {}

    name = frontmatter.get("name") or default_name
    description = frontmatter.get("description", f"Skill: {name}")
    applies_to = frontmatter.get("applies_to_analyst", [])
    decision_types = _parse_decision_types(frontmatter.get("decision_types"))
    version = str(frontmatter.get("version", "1.0"))
    metadata = {
        k: v
        for k, v in frontmatter.items()
        if k
        not in (
            "name",
            "description",
            "applies_to_analyst",
            "version",
            "decision_types",
        )
    }

    return SkillDefinition(
        name=name,
        description=description,
        category=category,
        applies_to_analyst=applies_to,
        decision_types=decision_types,
        version=version,
        content=body.strip(),
        metadata=metadata,
    )


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
            skill_def = _load_skill_from_directory(skill_dir, category)
            if skill_def is not None:
                registry.register(skill_def)

        # Load flat-file skills (backward compat), skipping those already loaded as dirs
        for md_file in sorted(category_dir.glob("*.md")):
            if md_file.stem in dir_based_stems:
                continue
            skill_def = _load_skill_from_file(md_file, category)
            if skill_def is not None:
                registry.register(skill_def)

    return registry


def _load_skill_from_directory(skill_dir: Path, category: str) -> Optional[SkillDefinition]:
    """Load a skill from a directory format (SKILL.md + optional references/ subdir).

    Returns None if SKILL.md does not exist (caller can fall back to flat .md format).
    """
    main_file = skill_dir / "SKILL.md"
    if not main_file.exists():
        return None

    raw_content = main_file.read_text(encoding="utf-8")
    skill_def = _load_skill(raw_content, skill_dir.name, category)

    # Load references from references/ subdirectory
    ref_dir = skill_dir / "references"
    references: List[SkillReference] = []
    if ref_dir.is_dir():
        for ref_file in sorted(ref_dir.glob("*.md")):
            ref_content = ref_file.read_text(encoding="utf-8")
            references.append(
                SkillReference(
                    filename=ref_file.name,
                    content=ref_content.strip(),
                )
            )
    skill_def.references = references

    return skill_def


def _load_skill_from_file(path: Path, category: str) -> Optional[SkillDefinition]:
    """Load and parse a single .md skill file (legacy flat-file format)."""
    raw_content = path.read_text(encoding="utf-8")
    return _load_skill(raw_content, path.stem, category)


def load_skills_from_dirs(directories: List[Path]) -> List[SkillDefinition]:
    """Load skills from multiple directories (for bundled + user overlay support)."""
    all_skills: List[SkillDefinition] = []
    for directory in directories:
        registry = load_skill_registry(directory)
        all_skills.extend(registry.list_skills())
    return all_skills
