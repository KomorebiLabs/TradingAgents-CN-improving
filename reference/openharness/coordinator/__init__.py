"""
模块文档: coordinator/__init__.py - 协调器模块导出

功能说明:
    作为coordinator包的公共接口，导出Agent定义和团队管理相关类型。
"""

from openharness.coordinator.agent_definitions import AgentDefinition, get_builtin_agent_definitions
from openharness.coordinator.coordinator_mode import TeamRecord, TeamRegistry, get_team_registry

__all__ = [
    "AgentDefinition",
    "TeamRecord",
    "TeamRegistry",
    "get_builtin_agent_definitions",
    "get_team_registry",
]
