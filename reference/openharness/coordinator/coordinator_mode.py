"""
模块文档: coordinator_mode.py - 协调器模式支持

================================================================================
特殊Python语法说明:
1. @dataclass:
   数据类，自动生成__init__等方法。

2. dataclasses.field(default_factory=list):
   每次创建实例时调用list()生成新的空列表。
   避免多个实例共享同一个列表对象的问题。

3. xml.sax.saxutils.escape/unescape:
   XML转义/反转义工具，防止XML注入。

4. re模块正则表达式:
   re.search() 在字符串中搜索模式匹配。

5. os.environ:
   访问和修改环境变量字典。

6. str.lower() in {"1", "true", "yes"}:
   集合成员检查，比多个or更高效。
================================================================================

功能说明:
    协调器(Coordinator)是一种多智能体协作模式的管理模块。
    支持：
    1. 团队注册表 - 管理多个Agent团队
    2. 任务通知 - Agent任务完成时发送通知
    3. 协调器模式检测 - 判断当前是否运行在协调器模式
    4. 协调器系统提示 - 生成协调器专用的系统提示词
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional
from xml.sax.saxutils import escape, unescape


# =============================================================================
# 团队注册表（向后兼容）
# =============================================================================

@dataclass
class TeamRecord:
    """
    =============================================================================
    类文档: TeamRecord - 团队记录

    作用说明:
        表示一个轻量级的内存团队记录。
        包含团队名称、描述、成员和消息。

    为什么需要团队概念:
        在复杂任务中，可能需要多个Agent协同工作。
        团队提供了一种组织和追踪Agent组的方式。
    """
    name: str
    description: str = ""
    agents: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


class TeamRegistry:
    """
    =============================================================================
    类文档: TeamRegistry - 团队注册表

    作用说明:
        管理所有创建的团队及其成员。
        提供团队的创建、删除、添加成员和发送消息功能。

    使用场景:
        协调器可以为特定任务创建团队，
        将相关的Agent加入团队，便于管理和通信。
    """

    def __init__(self) -> None:
        """初始化空的团队字典。"""
        self._teams: dict[str, TeamRecord] = {}

    def create_team(self, name: str, description: str = "") -> TeamRecord:
        """
        创建新团队。
        
        异常:
            ValueError - 如果团队已存在
        """
        if name in self._teams:
            raise ValueError(f"Team '{name}' already exists")
        team = TeamRecord(name=name, description=description)
        self._teams[name] = team
        return team

    def delete_team(self, name: str) -> None:
        """删除团队。"""
        if name not in self._teams:
            raise ValueError(f"Team '{name}' does not exist")
        del self._teams[name]

    def add_agent(self, team_name: str, task_id: str) -> None:
        """向团队添加Agent。"""
        team = self._require_team(team_name)
        if task_id not in team.agents:
            team.agents.append(task_id)

    def send_message(self, team_name: str, message: str) -> None:
        """向团队发送消息。"""
        self._require_team(team_name).messages.append(message)

    def list_teams(self) -> list[TeamRecord]:
        """列出所有团队。"""
        return sorted(self._teams.values(), key=lambda item: item.name)

    def _require_team(self, name: str) -> TeamRecord:
        """获取团队，不存在则抛出异常。"""
        team = self._teams.get(name)
        if team is None:
            raise ValueError(f"Team '{name}' does not exist")
        return team


# 单例注册表
_DEFAULT_TEAM_REGISTRY: TeamRegistry | None = None


def get_team_registry() -> TeamRegistry:
    """
    =============================================================================
    函数文档: get_team_registry - 获取团队注册表单例

    返回值:
        TeamRegistry - 全局唯一的团队注册表实例

    为什么使用单例:
        团队信息需要在整个进程生命周期内持久化。
        使用单例确保所有代码访问同一个注册表。
    """
    global _DEFAULT_TEAM_REGISTRY
    if _DEFAULT_TEAM_REGISTRY is None:
        _DEFAULT_TEAM_REGISTRY = TeamRegistry()
    return _DEFAULT_TEAM_REGISTRY


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class TaskNotification:
    """
    =============================================================================
    类文档: TaskNotification - 任务完成通知

    作用说明:
        表示一个Agent任务完成时的结构化通知。
        包含任务ID、状态、摘要和可选的结果/使用量信息。

    用途:
        协调器接收子Agent完成通知，解析后决定下一步操作。
    """
    task_id: str
    status: str
    summary: str
    result: Optional[str] = None
    usage: Optional[dict[str, int]] = None


@dataclass
class WorkerConfig:
    """
    =============================================================================
    类文档: WorkerConfig - 工作器配置

    作用说明:
        表示启动工作器(Worker) Agent所需的配置信息。
    """
    agent_id: str
    name: str
    prompt: str
    model: Optional[str] = None
    color: Optional[str] = None
    team: Optional[str] = None


# =============================================================================
# XML辅助函数
# =============================================================================

# 使用量统计字段
_USAGE_FIELDS = ("total_tokens", "tool_uses", "duration_ms")


def format_task_notification(n: TaskNotification) -> str:
    """
    =============================================================================
    函数文档: format_task_notification - 序列化为XML

    参数说明:
        n: TaskNotification对象

    返回值:
        str - XML格式的通知字符串

    作用说明:
        将任务通知转换为XML格式，用于在协调器和Worker之间传输。

    为什么使用XML:
        1. 结构清晰，易于解析
        2. 可以嵌入到消息中传输
        3. 支持嵌套数据（usage）

    输出格式:
        <task-notification>
        <task-id>...</task-id>
        <status>...</status>
        <summary>...</summary>
        <result>...</result>
        <usage>
          <total_tokens>...</total_tokens>
        </usage>
        </task-notification>
    """
    parts = [
        "<task-notification>",
        f"<task-id>{escape(n.task_id)}</task-id>",
        f"<status>{escape(n.status)}</status>",
        f"<summary>{escape(n.summary)}</summary>",
    ]
    if n.result is not None:
        parts.append(f"<result>{escape(n.result)}</result>")
    if n.usage:
        parts.append("<usage>")
        for key in _USAGE_FIELDS:
            if key in n.usage:
                parts.append(f"  <{key}>{n.usage[key]}</{key}>")
        parts.append("</usage>")
    parts.append("</task-notification>")
    return "\n".join(parts)


def parse_task_notification(xml: str) -> TaskNotification:
    """
    =============================================================================
    函数文档: parse_task_notification - 解析XML为对象

    参数说明:
        xml: XML格式的通知字符串

    返回值:
        TaskNotification - 解析后的通知对象

    实现说明:
        使用正则表达式提取XML标签内容。
        处理可选字段（result、usage）的缺失情况。
    """
    def _extract(tag: str) -> Optional[str]:
        m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)
        return unescape(m.group(1).strip()) if m else None

    task_id = _extract("task-id") or ""
    status = _extract("status") or ""
    summary = _extract("summary") or ""
    result = _extract("result")

    # 解析usage块
    usage: Optional[dict[str, int]] = None
    usage_block = re.search(r"<usage>(.*?)</usage>", xml, re.DOTALL)
    if usage_block:
        usage = {}
        for key in _USAGE_FIELDS:
            m = re.search(rf"<{key}>(\d+)</{key}>", usage_block.group(1))
            if m:
                usage[key] = int(m.group(1))

    return TaskNotification(
        task_id=task_id,
        status=status,
        summary=summary,
        result=result,
        usage=usage,
    )


# =============================================================================
# 协调器模式支持
# =============================================================================

# 工具名称常量
_AGENT_TOOL_NAME = "agent"
_SEND_MESSAGE_TOOL_NAME = "send_message"
_TASK_STOP_TOOL_NAME = "task_stop"

# 工作器可用的工具列表
_WORKER_TOOLS = [
    "bash", "file_read", "file_edit", "file_write",
    "glob", "grep", "web_fetch", "web_search",
    "task_create", "task_get", "task_list", "task_output",
    "skill",
]

# 简化模式的工作器工具
_SIMPLE_WORKER_TOOLS = ["bash", "file_read", "file_edit"]


def is_coordinator_mode() -> bool:
    """
    =============================================================================
    函数文档: is_coordinator_mode - 检测协调器模式

    返回值:
        bool - True表示运行在协调器模式

    实现说明:
        检查环境变量 CLAUDE_CODE_COORDINATOR_MODE。
        支持多种真值格式：1, true, yes（大小写不敏感）。
    """
    val = os.environ.get("CLAUDE_CODE_COORDINATOR_MODE", "")
    return val.lower() in {"1", "true", "yes"}


def match_session_mode(session_mode: Optional[str]) -> Optional[str]:
    """
    =============================================================================
    函数文档: match_session_mode - 匹配会话模式

    参数说明:
        session_mode: 会话中存储的模式标识

    返回值:
        Optional[str] - 警告消息，如果模式发生切换

    作用说明:
        当恢复一个保存的会话时，确保环境变量与保存的模式一致。
        例如保存时是协调器模式，恢复后也应切换到协调器模式。
    """
    if not session_mode:
        return None

    current_is_coordinator = is_coordinator_mode()
    session_is_coordinator = session_mode == "coordinator"

    # 模式相同，无需切换
    if current_is_coordinator == session_is_coordinator:
        return None

    # 需要切换
    if session_is_coordinator:
        os.environ["CLAUDE_CODE_COORDINATOR_MODE"] = "1"
    else:
        os.environ.pop("CLAUCE_CODE_COORDINATOR_MODE", None)

    if session_is_coordinator:
        return "Entered coordinator mode to match resumed session."
    return "Exited coordinator mode to match resumed session."


def get_coordinator_tools() -> list[str]:
    """
    =============================================================================
    函数文档: get_coordinator_tools - 获取协调器专用工具

    返回值:
        list[str] - 协调器保留的工具名称列表

    作用说明:
        返回只有协调器才能使用的工具。
        工作器不能使用这些工具。
    """
    return [_AGENT_TOOL_NAME, _SEND_MESSAGE_TOOL_NAME, _TASK_STOP_TOOL_NAME]


def get_coordinator_user_context(
    mcp_clients: list[dict[str, str]] | None = None,
    scratchpad_dir: Optional[str] = None,
) -> dict[str, str]:
    """
    =============================================================================
    函数文档: get_coordinator_user_context - 获取协调器用户上下文

    参数说明:
        mcp_clients: MCP服务器客户端列表
        scratchpad_dir: 便签目录路径

    返回值:
        dict[str, str] - 包含workerToolsContext的字典

    作用说明:
        构建注入到协调器用户回合的上下文信息。
        告知协调器工作器有哪些工具可用。

    为什么需要这个上下文:
        协调器需要知道工作器的能力边界，
        以便正确地分配任务和期望结果。
    """
    if not is_coordinator_mode():
        return {}

    is_simple = os.environ.get("CLAUCE_CODE_SIMPLE", "").lower() in {"1", "true", "yes"}
    tools = sorted(_SIMPLE_WORKER_TOOLS if is_simple else _WORKER_TOOLS)
    worker_tools_str = ", ".join(tools)

    content = (
        f"Workers spawned via the {_AGENT_TOOL_NAME} tool have access to these tools: "
        f"{worker_tools_str}"
    )

    if mcp_clients:
        server_names = ", ".join(c["name"] for c in mcp_clients)
        content += f"\n\nWorkers also have access to MCP tools from connected MCP servers: {server_names}"

    if scratchpad_dir:
        content += (
            f"\n\nScratchpad directory: {scratchpad_dir}\n"
            "Workers can read and write here without permission prompts. "
            "Use this for durable cross-worker knowledge — structure files however fits the work."
        )

    return {"workerToolsContext": content}


def get_coordinator_system_prompt() -> str:
    """
    =============================================================================
    函数文档: get_coordinator_system_prompt - 获取协调器系统提示

    返回值:
        str - 协调器模式的系统提示词

    作用说明:
        生成运行在协调器模式时使用的系统提示词。
        包含协调器的角色定义、工具使用指南和工作流程。

    为什么协调器需要专用提示:
        1. 角色定义：协调器是任务管理者
        2. 工具限制：只能使用Agent管理工具
        3. 工作流程：研究->综合->实现->验证
    """
    is_simple = os.environ.get("CLAUCE_CODE_SIMPLE", "").lower() in {"1", "true", "yes"}

    if is_simple:
        worker_capabilities = (
            "Workers have access to Bash, Read, and Edit tools, "
            "plus MCP tools from configured MCP servers."
        )
    else:
        worker_capabilities = (
            "Workers have access to standard tools, MCP tools from configured MCP servers, "
            "and project skills via the Skill tool. "
            "Delegate skill invocations (e.g. /commit, /verify) to workers."
        )

    # 返回完整的协调器系统提示词
    return f"""You are Claude Code, an AI assistant that orchestrates software engineering tasks across multiple workers.

## 1. Your Role

You are a **coordinator**. Your job is to:
- Help the user achieve their goal
- Direct workers to research, implement and verify code changes
- Synthesize results and communicate with the user
- Answer questions directly when possible — don't delegate work that you can handle without tools

## 2. Your Tools

- **{_AGENT_TOOL_NAME}** - Spawn a new worker
- **{_SEND_MESSAGE_TOOL_NAME}** - Continue an existing worker
- **{_TASK_STOP_TOOL_NAME}** - Stop a running worker

## 3. Workers

{worker_capabilities}

## 4. Task Workflow

Most tasks can be broken down into phases:
- Research: Workers investigate codebase
- Synthesis: You understand findings and plan
- Implementation: Workers make changes
- Verification: Workers test changes
"""
