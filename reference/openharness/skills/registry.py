"""
模块文档: registry.py - 技能注册表

================================================================================
特殊Python语法说明:
1. sorted() with key lambda:
   sorted()函数使用lambda作为排序键。
   lambda skill: skill.name 按名称排序。

2. dict.get()方法:
   dict.get(key, default) 安全获取值，不存在返回默认值。
================================================================================

功能说明:
    管理已加载技能的注册表，提供技能的注册、查询和列表功能。
"""

from __future__ import annotations

from openharness.skills.types import SkillDefinition


class SkillRegistry:
    """
    =============================================================================
    类文档: SkillRegistry - 技能注册表

    作用说明:
        内存中的技能存储结构，通过名称索引管理所有已加载的技能。
        提供统一的技能访问接口。

    为什么需要注册表:
        1. 统一管理：所有技能集中存储
        2. 快速查找：通过名称快速定位技能
        3. 去重：同名技能后者覆盖前者

    使用场景:
        registry = SkillRegistry()
        registry.register(skill1)
        registry.register(skill2)
        
        # 查询
        skill = registry.get("my-skill")
        
        # 列表
        all_skills = registry.list_skills()
    =============================================================================
    """

    def __init__(self) -> None:
        """
        初始化说明:
            创建空的技能字典。
            技能按名称索引。
        """
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        """
        =============================================================================
        方法文档: register - 注册技能

        参数说明:
            skill: 技能定义对象

        实现说明:
            将技能按名称存入字典。
            如果同名技能已存在，会被覆盖。
        =============================================================================
        """
        self._skills[skill.name] = skill

    def get(self, name: str) -> SkillDefinition | None:
        """
        =============================================================================
        方法文档: get - 获取技能

        参数说明:
            name: 技能名称

        返回值:
            SkillDefinition | None - 找到返回技能对象，否则返回None
        =============================================================================
        """
        return self._skills.get(name)

    def list_skills(self) -> list[SkillDefinition]:
        """
        =============================================================================
        方法文档: list_skills - 列出所有技能

        返回值:
            list[SkillDefinition] - 按名称排序的技能列表

        为什么排序:
            提供一致性的输出，方便测试和UI展示。
        =============================================================================
        """
        return sorted(self._skills.values(), key=lambda skill: skill.name)
