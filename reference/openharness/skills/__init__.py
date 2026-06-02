"""
模块文档: skills/__init__.py - 技能模块导出

================================================================================
特殊Python语法说明:
1. TYPE_CHECKING: 仅类型检查导入
2. __getattr__: 延迟导入实现
================================================================================

功能说明:
    作为skills包的公共接口，提供技能系统的核心类型和函数。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from openharness.skills.registry import SkillRegistry
    from openharness.skills.types import SkillDefinition

__all__ = ["SkillDefinition", "SkillRegistry", "get_user_skills_dir", "load_skill_registry"]


def __getattr__(name: str):
    """
    =============================================================================
    函数文档: __getattr__ - 延迟导入实现
    =============================================================================
    """
    # 加载器函数
    if name in {"get_user_skills_dir", "load_skill_registry"}:
        from openharness.skills.loader import get_user_skills_dir, load_skill_registry
        return {
            "get_user_skills_dir": get_user_skills_dir,
            "load_skill_registry": load_skill_registry,
        }[name]

    # 注册表
    if name == "SkillRegistry":
        from openharness.skills.registry import SkillRegistry
        return SkillRegistry

    # 技能定义
    if name == "SkillDefinition":
        from openharness.skills.types import SkillDefinition
        return SkillDefinition

    raise AttributeError(name)
