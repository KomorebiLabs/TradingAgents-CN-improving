"""
模块文档: types.py - 技能数据模型

================================================================================
特殊Python语法说明:
1. @dataclass(frozen=True):
   不可变数据类，用于表示已加载的技能定义。
   frozen=True确保实例创建后不可修改，保证数据一致性。
================================================================================

功能说明:
    定义了技能(Skill)的数据结构。
    技能是一组指令和元数据，可以被AI加载以增强其能力。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillDefinition:
    """
    =============================================================================
    类文档: SkillDefinition - 技能定义

    作用说明:
        代表一个已加载的技能（Skill）的元数据和内容。
        技能是可被AI加载的指令集，用于增强AI在特定领域的能力。

    为什么需要技能系统:
        1. 专业化：让AI在不同领域表现更好
        2. 可复用：一次编写，多次使用
        3. 可扩展：用户可以自定义技能

    字段说明:
        name: 技能名称，用于引用和显示
        description: 简短描述，说明技能用途
        content: 技能的完整内容（Markdown格式）
        source: 来源标识 ("bundled", "user", "plugin")
        path: 技能文件路径（如果有）

    source字段的作用:
        - bundled: 内置技能，随OpenHarness分发
        - user: 用户创建的技能，存放在用户配置目录
        - plugin: 通过插件系统加载的技能
    =============================================================================
    """
    name: str
    description: str
    content: str
    source: str
    path: str | None = None
