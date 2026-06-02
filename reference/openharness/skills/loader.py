"""
模块文档: loader.py - 技能加载器

================================================================================
特殊Python语法说明:
1. yaml.safe_load:
   YAML解析器，将YAML格式解析为Python对象。
   safe_load只解析标准YAML，避免执行任意代码。

2. Path.glob("*.md"):
   返回匹配通配符模式的所有文件。
   *.md 匹配所有Markdown文件。

3. Path.iterdir():
   返回目录中的所有条目（文件和子目录）。

4. Path.read_text(encoding="utf-8"):
   读取文件内容，指定编码为UTF-8。

5. from __future__ import annotations:
   启用延迟注解评估，解决循环导入问题。
================================================================================

功能说明:
    负责从各种来源加载技能定义：
    - 内置技能 (bundled)
    - 用户技能 (user)
    - 插件技能 (plugin)
    
    技能以Markdown文件形式存储，支持YAML frontmatter定义元数据。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import yaml

from openharness.config.paths import get_config_dir
from openharness.config.settings import load_settings
from openharness.skills.bundled import get_bundled_skills
from openharness.skills.registry import SkillRegistry
from openharness.skills.types import SkillDefinition

logger = logging.getLogger(__name__)


# =============================================================================
# 用户技能目录
# =============================================================================

def get_user_skills_dir() -> Path:
    """
    =============================================================================
    函数文档: get_user_skills_dir - 获取用户技能目录

    返回值:
        Path - 用户技能目录的Path对象

    作用说明:
        返回用户技能的配置目录，默认位于配置目录下。
        如果目录不存在，会创建它。

    目录结构:
        ~/.openharness/skills/
        ├── my-skill/
        │   └── SKILL.md
        └── another-skill/
            └── SKILL.md
    =============================================================================
    """
    path = get_config_dir() / "skills"
    path.mkdir(parents=True, exist_ok=True)
    return path


# =============================================================================
# 技能注册表加载
# =============================================================================

def load_skill_registry(
    cwd: str | Path | None = None,
    *,
    extra_skill_dirs: Iterable[str | Path] | None = None,
    extra_plugin_roots: Iterable[str | Path] | None = None,
    settings=None,
) -> SkillRegistry:
    """
    =============================================================================
    函数文档: load_skill_registry - 加载技能注册表

    参数说明:
        cwd: 当前工作目录（用于插件加载）
        extra_skill_dirs: 额外的技能目录列表
        extra_plugin_roots: 额外的插件根目录
        settings: 配置对象（可选）

    返回值:
        SkillRegistry - 填充好的技能注册表

    作用说明:
        从多个来源加载所有技能，合并到一个注册表中。
        加载优先级：bundled -> user -> extra -> plugin

    为什么需要多个来源:
        1. bundled: 提供开箱即用的内置技能
        2. user: 允许用户自定义技能
        3. extra: 支持额外的技能目录（临时加载）
        4. plugin: 允许插件提供技能

    示例:
        registry = load_skill_registry(cwd="/path/to/project")
    =============================================================================
    """
    registry = SkillRegistry()

    # 1. 内置技能
    for skill in get_bundled_skills():
        registry.register(skill)

    # 2. 用户技能
    for skill in load_user_skills():
        registry.register(skill)

    # 3. 额外目录中的技能
    for skill in load_skills_from_dirs(extra_skill_dirs):
        registry.register(skill)

    # 4. 插件中的技能
    if cwd is not None:
        from openharness.plugins.loader import load_plugins

        resolved_settings = settings or load_settings()
        for plugin in load_plugins(resolved_settings, cwd, extra_roots=extra_plugin_roots):
            if not plugin.enabled:
                continue
            for skill in plugin.skills:
                registry.register(skill)

    return registry


# =============================================================================
# 用户技能加载
# =============================================================================

def load_user_skills() -> list[SkillDefinition]:
    """
    =============================================================================
    函数文档: load_user_skills - 加载用户技能

    返回值:
        list[SkillDefinition] - 用户技能列表

    作用说明:
        从用户配置目录加载所有用户创建的技能。

    目录结构:
        <user_skills_dir>/
        ├── skill-name-1/
        │   └── SKILL.md
        └── skill-name-2/
            └── SKILL.md
    =============================================================================
    """
    return load_skills_from_dirs([get_user_skills_dir()], source="user")


# =============================================================================
# 通用目录加载
# =============================================================================

def load_skills_from_dirs(
    directories: Iterable[str | Path] | None,
    *,
    source: str = "user",
) -> list[SkillDefinition]:
    """
    =============================================================================
    函数文档: load_skills_from_dirs - 从目录列表加载技能

    参数说明:
        directories: 技能目录的可迭代对象
        source: 技能来源标识

    返回值:
        list[SkillDefinition] - 加载的技能列表

    作用说明:
        扫描多个目录，查找所有技能定义文件并解析它们。

    支持的目录布局:
        <root>/
        ├── <skill-dir>/
        │   └── SKILL.md
        └── <another-skill>/
            └── SKILL.md

    去重机制:
        使用seen集合记录已处理的技能文件路径，
        避免同一技能被多次加载。

    解析流程:
        1. 遍历目录
        2. 查找子目录中的SKILL.md文件
        3. 读取文件内容
        4. 解析name和description
        5. 创建SkillDefinition对象
    =============================================================================
    """
    skills: list[SkillDefinition] = []
    if not directories:
        return skills

    seen: set[Path] = set()  # 去重集合
    for directory in directories:
        root = Path(directory).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)

        # 查找所有技能文件
        candidates: list[Path] = []
        for child in sorted(root.iterdir()):
            if child.is_dir():
                skill_path = child / "SKILL.md"
                if skill_path.exists():
                    candidates.append(skill_path)

        # 解析每个技能
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)

            content = path.read_text(encoding="utf-8")
            # 默认名称取自目录名
            default_name = path.parent.name
            name, description = _parse_skill_markdown(default_name, content)

            skills.append(
                SkillDefinition(
                    name=name,
                    description=description,
                    content=content,
                    source=source,
                    path=str(path),
                )
            )

    return skills


# =============================================================================
# Markdown解析
# =============================================================================

def _parse_skill_markdown(default_name: str, content: str) -> tuple[str, str]:
    """
    =============================================================================
    函数文档: _parse_skill_markdown - 解析技能Markdown

    参数说明:
        default_name: 默认技能名称（来自目录名）
        content: Markdown文件内容

    返回值:
        tuple[str, str] - (name, description)

    作用说明:
        从Markdown文件中提取技能名称和描述。

    支持两种格式:

    格式1: YAML Frontmatter (优先)
        ---
        name: My Skill
        description: This skill does something useful
        ---
        # Skill Content
        ...

    格式2: 降级解析
        # My Skill

        This skill does something useful.
        It can help you with...

    为什么需要两种格式:
        YAML frontmatter提供明确的数据结构，
        但不是所有技能文件都有。
        降级解析尝试从标题和首段提取信息。
    """
    name = default_name
    description = ""

    lines = content.splitlines()

    # 尝试YAML frontmatter
    if content.startswith("---\n"):
        end_index = content.find("\n---\n", 4)
        if end_index != -1:
            try:
                metadata = yaml.safe_load(content[4:end_index])
                if isinstance(metadata, dict):
                    # 提取name
                    val = metadata.get("name")
                    if isinstance(val, str) and val.strip():
                        name = val.strip()
                    # 提取description
                    val = metadata.get("description")
                    if isinstance(val, str) and val.strip():
                        description = val.strip()
            except yaml.YAMLError:
                logger.debug("Failed to parse YAML frontmatter for skill %s", default_name)

    # 降级：从标题和首段解析
    if not description:
        for line in lines:
            stripped = line.strip()
            # 跳过空行和frontmatter标记
            if not stripped or stripped.startswith("---"):
                continue
            # 第一个#开头的行是标题
            if stripped.startswith("# "):
                if not name or name == default_name:
                    name = stripped[2:].strip() or default_name
                continue
            # 第一段非标题内容是描述
            description = stripped[:200]
            break

    if not description:
        description = f"Skill: {name}"

    return name, description
