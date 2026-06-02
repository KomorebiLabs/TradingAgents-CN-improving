"""
模块文档: agent_definitions.py - Agent定义系统

================================================================================
特殊Python语法说明:
1. Pydantic BaseModel:
   数据验证和序列化库，提供自动类型转换和验证。

2. Field(default_factory=list):
   Pydantic字段选项，default_factory在每次创建实例时生成新的默认值。

3. Literal["builtin", "user", "plugin"]:
   字符串字面量类型，限制值为指定枚举值之一。

4. frozenset:
   不可变集合，用于定义常量集合，比set更高效且线程安全。
================================================================================

功能说明:
    Agent定义加载系统，负责：
    1. 定义Agent的数据模型
    2. 提供内置Agent定义
    3. 从Markdown文件加载用户自定义Agent
    4. 管理所有Agent定义的注册表
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from openharness.config.paths import get_config_dir

logger = logging.getLogger(__name__)


# =============================================================================
# 常量定义
# =============================================================================

# Agent颜色常量 - 用于UI显示
AGENT_COLORS: frozenset[str] = frozenset(
    {
        "red", "green", "blue", "yellow", "purple",
        "orange", "cyan", "magenta", "white", "gray",
    }
)

# 努力级别常量
EFFORT_LEVELS: tuple[str, ...] = ("low", "medium", "high")

# 权限模式常量
PERMISSION_MODES: tuple[str, ...] = (
    "default", "acceptEdits", "bypassPermissions", "plan", "dontAsk",
)

# 记忆作用域常量
MEMORY_SCOPES: tuple[str, ...] = ("user", "project", "local")

# 隔离模式常量
ISOLATION_MODES: tuple[str, ...] = ("worktree", "remote")


# =============================================================================
# Agent定义模型
# =============================================================================

class AgentDefinition(BaseModel):
    """
    =============================================================================
    类文档: AgentDefinition - Agent定义模型

    作用说明:
        代表一个完整的Agent定义，包含配置AI行为所需的所有字段。

    为什么需要Agent定义:
        1. 专业化：不同任务需要不同的AI配置
        2. 可复用：一次定义，多次使用
        3. 可配置：支持丰富的参数调整

    字段分类:

    必需字段:
        - name: Agent类型标识符
        - description: 使用场景描述

    提示词和工具:
        - system_prompt: 系统提示词模板
        - tools: 允许的工具列表
        - disallowed_tools: 禁止的工具列表

    模型和努力:
        - model: 模型选择/覆盖
        - effort: 任务努力级别

    权限控制:
        - permission_mode: 权限模式

    Agent循环控制:
        - max_turns: 最大推理轮数

    技能和MCP:
        - skills: 可用技能列表
        - mcp_servers: MCP服务器配置
        - required_mcp_servers: 必需的MCP服务器

    钩子:
        - hooks: 会话级钩子

    UI相关:
        - color: 显示颜色

    生命周期:
        - background: 是否后台运行
        - initial_prompt: 初始提示
        - memory: 记忆作用域
        - isolation: 隔离模式

    元数据:
        - filename: 原始文件名
        - base_dir: 加载来源目录
        - critical_system_reminder: 关键提醒
        - omit_claude_md: 是否跳过CLAUDE.md

    Python特有:
        - permissions: 额外权限规则
        - subagent_type: 路由键
        - source: 来源标识
    =============================================================================
    """

    # --- 必需 ---
    name: str
    description: str

    # --- 提示词/工具 ---
    system_prompt: str | None = None
    tools: list[str] | None = None
    disallowed_tools: list[str] | None = None

    # --- 模型/努力 ---
    model: str | None = None
    effort: str | int | None = None

    # --- 权限 ---
    permission_mode: str | None = None

    # --- Agent循环控制 ---
    max_turns: int | None = None

    # --- 技能/MCP ---
    skills: list[str] = Field(default_factory=list)
    mcp_servers: list[Any] | None = None
    required_mcp_servers: list[str] | None = None

    # --- 钩子 ---
    hooks: dict[str, Any] | None = None

    # --- UI ---
    color: str | None = None

    # --- 生命周期 ---
    background: bool = False
    initial_prompt: str | None = None
    memory: str | None = None
    isolation: str | None = None

    # --- 元数据 ---
    filename: str | None = None
    base_dir: str | None = None
    critical_system_reminder: str | None = None
    pending_snapshot_update: dict[str, Any] | None = None
    omit_claude_md: bool = False

    # --- Python特有 ---
    permissions: list[str] = Field(default_factory=list)
    subagent_type: str = "general-purpose"
    source: Literal["builtin", "user", "plugin"] = "builtin"


# =============================================================================
# 内置Agent系统提示词
# =============================================================================

# 共享Agent前缀
_SHARED_AGENT_PREFIX = (
    "You are an agent for Claude Code, Anthropic's official CLI for Claude. "
    "Given the user's message, you should use the tools available to complete the task. "
    "Complete the task fully — don't gold-plate, but don't leave it half-done."
)

# 共享Agent指南
_SHARED_AGENT_GUIDELINES = """Your strengths:
- Searching for code, configurations, and patterns across large codebases
- Analyzing multiple files to understand system architecture
- Investigating complex questions that require exploring many files
- Performing multi-step research tasks

Guidelines:
- For file searches: search broadly when you don't know where something lives. Use Read when you know the specific file path.
- For analysis: Start broad and narrow down. Use multiple search strategies if the first doesn't yield results.
- Be thorough: Check multiple locations, consider different naming conventions, look for related files.
- NEVER create files unless they're absolutely necessary for achieving your goal. ALWAYS prefer editing an existing file to creating a new one.
- NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested."""

# 通用Agent提示词
_GENERAL_PURPOSE_SYSTEM_PROMPT = (
    f"{_SHARED_AGENT_PREFIX} When you complete the task, respond with a concise report covering "
    "what was done and any key findings — the caller will relay this to the user, so it only needs "
    f"the essentials.\n\n{_SHARED_AGENT_GUIDELINES}"
)

# 探索Agent提示词
_EXPLORE_SYSTEM_PROMPT = """You are a file search specialist for Claude Code, Anthropic's official CLI for Claude. You excel at rapidly navigating and exploring codebases.

=== CRITICAL: READ-ONLY MODE ===
This is a READ-ONLY exploration task. You are STRICTLY PROHIBITED from:
- Creating new files (no Write, touch, or file creation of any kind)
- Modifying existing files (no Edit operations)
- Deleting files (no rm or deletion)
- Running ANY commands that change system state

Your role is EXCLUSIVELY to search and analyze existing code."""

# 计划Agent提示词
_PLAN_SYSTEM_PROMPT = """You are a software architect and planning specialist for Claude Code.

=== CRITICAL: READ-ONLY MODE ===
This is a READ-ONLY planning task. You are STRICTLY PROHIBITED from modifying any files.

Your role is EXCLUSIVELY to explore the codebase and design implementation plans."""


# =============================================================================
# 内置Agent定义
# =============================================================================

_BUILTIN_AGENTS: list[AgentDefinition] = [
    # 通用Agent
    AgentDefinition(
        name="general-purpose",
        description=(
            "General-purpose agent for researching complex questions, searching for code, "
            "and executing multi-step tasks."
        ),
        tools=["*"],
        system_prompt=_GENERAL_PURPOSE_SYSTEM_PROMPT,
        subagent_type="general-purpose",
        source="builtin",
        base_dir="built-in",
    ),

    # 探索Agent
    AgentDefinition(
        name="Explore",
        description=(
            "Fast agent specialized for exploring codebases. Use this when you need to "
            "quickly find files by patterns or search code for keywords."
        ),
        disallowed_tools=["agent", "exit_plan_mode", "file_edit", "file_write", "notebook_edit"],
        system_prompt=_EXPLORE_SYSTEM_PROMPT,
        model="inherit",
        omit_claude_md=True,
        subagent_type="Explore",
        source="builtin",
        base_dir="built-in",
    ),

    # 计划Agent
    AgentDefinition(
        name="Plan",
        description=(
            "Software architect agent for designing implementation plans. Use this when you "
            "need to plan the implementation strategy for a task."
        ),
        disallowed_tools=["agent", "exit_plan_mode", "file_edit", "file_write", "notebook_edit"],
        system_prompt=_PLAN_SYSTEM_PROMPT,
        model="inherit",
        omit_claude_md=True,
        subagent_type="Plan",
        source="builtin",
        base_dir="built-in",
    ),

    # 工作器Agent
    AgentDefinition(
        name="worker",
        description=(
            "Implementation-focused worker agent. Use this for concrete coding tasks: "
            "writing features, fixing bugs, refactoring code, and running tests."
        ),
        tools=None,  # 所有工具
        system_prompt=_SHARED_AGENT_PREFIX,
        subagent_type="worker",
        source="builtin",
        base_dir="built-in",
    ),
]


# =============================================================================
# 公共API
# =============================================================================

def get_builtin_agent_definitions() -> list[AgentDefinition]:
    """
    =============================================================================
    函数文档: get_builtin_agent_definitions - 获取内置Agent定义

    返回值:
        list[AgentDefinition] - 内置Agent列表
    """
    return list(_BUILTIN_AGENTS)


def get_all_agent_definitions() -> list[AgentDefinition]:
    """
    =============================================================================
    函数文档: get_all_agent_definitions - 获取所有Agent定义

    返回值:
        list[AgentDefinition] - 所有Agent列表

    加载顺序（后者覆盖前者）:
        1. 内置Agent
        2. 用户Agent (~/.openharness/agents/)
        3. 插件Agent
    """
    agent_map: dict[str, AgentDefinition] = {}

    # 1. 内置Agent
    for agent in get_builtin_agent_definitions():
        agent_map[agent.name] = agent

    # 2. 用户Agent
    user_agents = load_agents_dir(_get_user_agents_dir())
    for agent in user_agents:
        agent_map[agent.name] = agent

    # 3. 插件Agent（懒加载）
    try:
        from openharness.plugins.loader import load_plugins
        from openharness.config.settings import load_settings

        settings = load_settings()
        import os
        cwd = os.getcwd()
        for plugin in load_plugins(settings, cwd):
            if not plugin.enabled:
                continue
            for agent_def in getattr(plugin, "agents", []):
                if isinstance(agent_def, AgentDefinition):
                    agent_map[agent_def.name] = agent_def
    except Exception:
        pass

    return list(agent_map.values())


def get_agent_definition(name: str) -> AgentDefinition | None:
    """
    =============================================================================
    函数文档: get_agent_definition - 按名称获取Agent定义

    参数说明:
        name: Agent名称

    返回值:
        AgentDefinition | None - 找到返回定义，否则返回None
    """
    for agent in get_all_agent_definitions():
        if agent.name == name:
            return agent
    return None


def _get_user_agents_dir() -> Path:
    """获取用户Agent定义目录。"""
    return get_config_dir() / "agents"


def load_agents_dir(directory: Path) -> list[AgentDefinition]:
    """
    =============================================================================
    函数文档: load_agents_dir - 从目录加载Agent定义

    参数说明:
        directory: 包含.md文件的目录

    返回值:
        list[AgentDefinition] - 加载的Agent列表

    目录结构:
        <directory>/
        ├── my-agent.md
        └── another-agent.md

    支持的frontmatter字段:
        - name: Agent名称
        - description: 使用场景描述
        - tools: 允许的工具列表
        - model: 模型选择
        - 等等...
    """
    agents: list[AgentDefinition] = []

    if not directory.is_dir():
        return agents

    for path in sorted(directory.glob("*.md")):
        try:
            content = path.read_text(encoding="utf-8")
            frontmatter, body = _parse_agent_frontmatter(content)

            name = str(frontmatter.get("name", "")).strip() or path.stem
            description = str(frontmatter.get("description", "")).strip()
            if not description:
                description = f"Agent: {name}"

            # 解析各种字段...
            # (简化示例，完整实现见源文件)

            agents.append(
                AgentDefinition(
                    name=name,
                    description=description,
                    system_prompt=body or None,
                    filename=path.stem,
                    base_dir=str(directory),
                    source="user",
                )
            )
        except Exception:
            logger.debug("Failed to parse agent from %s", path, exc_info=True)
            continue

    return agents


def _parse_agent_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    =============================================================================
    函数文档: _parse_agent_frontmatter - 解析Agent Markdown

    参数说明:
        content: Markdown文件内容

    返回值:
        tuple[dict, str] - (frontmatter字典, 剩余body文本)

    支持格式:
        1. YAML frontmatter
        2. 纯Markdown（无frontmatter）
    """
    frontmatter: dict[str, Any] = {}
    body = content

    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return frontmatter, body

    # 查找结束分隔符
    end_index: int | None = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = i
            break

    if end_index is None:
        return frontmatter, body

    # 解析YAML
    fm_text = "\n".join(lines[1:end_index])
    try:
        parsed = yaml.safe_load(fm_text)
        if isinstance(parsed, dict):
            frontmatter = parsed
    except yaml.YAMLError:
        # 降级：简单key:value解析
        for fm_line in lines[1:end_index]:
            if ":" in fm_line:
                key, _, value = fm_line.partition(":")
                frontmatter[key.strip()] = value.strip().strip("'\"")

    # Body是---之后的内容
    body = "\n".join(lines[end_index + 1 :]).strip()
    return frontmatter, body


def has_required_mcp_servers(agent: AgentDefinition, available_servers: list[str]) -> bool:
    """
    =============================================================================
    函数文档: has_required_mcp_servers - 检查必需的MCP服务器

    参数说明:
        agent: Agent定义
        available_servers: 可用的MCP服务器列表

    返回值:
        bool - True表示所有必需的服务器都可用
    """
    if not agent.required_mcp_servers:
        return True
    return all(
        any(pattern.lower() in server.lower() for server in available_servers)
        for pattern in agent.required_mcp_servers
    )


def filter_agents_by_mcp_requirements(
    agents: list[AgentDefinition],
    available_servers: list[str],
) -> list[AgentDefinition]:
    """
    =============================================================================
    函数文档: filter_agents_by_mcp_requirements - 按MCP要求过滤Agent

    返回值:
        list[AgentDefinition] - 只包含MCP要求满足的Agent列表
    """
    return [a for a in agents if has_required_mcp_servers(a, available_servers)]
