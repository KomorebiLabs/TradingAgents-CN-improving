"""
模块文档: bundled/__init__.py - 内置技能定义

================================================================================
特殊Python语法说明:
1. Path(__file__).parent:
   __file__是当前模块的路径，
   .parent获取父目录。

2. Path.glob("*.md"):
   查找所有Markdown文件。

3. Path.stem:
   获取文件名（不含扩展名）。
================================================================================

功能说明:
    加载内置于OpenHarness中的技能。
    内置技能存放在 skills/content/ 目录下，
    打包在安装包中随OpenHarness分发。
"""

from __future__ import annotations

from pathlib import Path

from openharness.skills.types import SkillDefinition

# 内置技能目录：skills/content/
_CONTENT_DIR = Path(__file__).parent / "content"


def get_bundled_skills() -> list[SkillDefinition]:
    """
    =============================================================================
    函数文档: get_bundled_skills - 获取所有内置技能

    返回值:
        list[SkillDefinition] - 内置技能列表

    作用说明:
        扫描content目录，加载所有.md文件作为内置技能。

    目录结构:
        skills/content/
        ├── skill-name-1.md
        ├── skill-name-2.md
        └── another-skill.md

    解析说明:
        - 文件名（不含扩展名）作为默认技能名
        - 解析YAML frontmatter获取name和description
        - 文件内容作为技能content

    为什么使用source="bundled":
        标识技能来源，便于管理和调试。
    =============================================================================
    """
    skills: list[SkillDefinition] = []
    if not _CONTENT_DIR.exists():
        return skills

    # 查找所有.md文件
    for path in sorted(_CONTENT_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        name, description = _parse_frontmatter(path.stem, content)
        skills.append(
            SkillDefinition(
                name=name,
                description=description,
                content=content,
                source="bundled",
                path=str(path),
            )
        )

    return skills


def _parse_frontmatter(default_name: str, content: str) -> tuple[str, str]:
    """
    =============================================================================
    函数文档: _parse_frontmatter - 解析frontmatter

    参数说明:
        default_name: 默认名称（来自文件名）
        content: 文件内容

    返回值:
        tuple[str, str] - (name, description)

    作用说明:
        从技能文件的YAML frontmatter中提取元数据。
        支持两种格式：
        1. YAML frontmatter (--- ... ---)
        2. 降级：标题+首段
    """
    name = default_name
    description = ""
    lines = content.splitlines()

    # 尝试解析YAML frontmatter
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                # 解析frontmatter行
                for fm_line in lines[1:i]:
                    fm = fm_line.strip()
                    if fm.startswith("name:"):
                        # 提取name值（去除引号和空格）
                        val = fm[5:].strip().strip("'\"")
                        if val:
                            name = val
                    elif fm.startswith("description:"):
                        val = fm[12:].strip().strip("'\"")
                        if val:
                            description = val
                break

        # 成功解析到description就返回
        if description:
            return name, description

    # 降级：从标题和首段解析
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            # 第一个标题作为名称
            name = stripped[2:].strip() or default_name
            continue
        if stripped and not stripped.startswith("---") and not stripped.startswith("#"):
            # 第一段内容作为描述
            description = stripped[:200]
            break

    return name, description or f"Bundled skill: {name}"
