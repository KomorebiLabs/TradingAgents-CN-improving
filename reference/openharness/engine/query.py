"""
模块文档: query.py - 核心工具感知查询循环

================================================================================
特殊Python语法说明:
1. @dataclass:
   数据类装饰器，自动生成 __init__, __repr__, __eq__ 等方法。
   配合 field() 可以精细控制字段行为。
   支持 default_factory 动态默认值（如 list/dict）。

2. async/await 异步语法:
   - async def: 定义协程函数，调用时返回协程对象
   - await: 等待协程执行完成，暂停当前协程
   - AsyncIterator[T]: 异步迭代器协议，返回值为异步生成器

3. asyncio 模块:
   - asyncio.Queue: 线程安全的异步队列
   - asyncio.create_task(): 创建后台任务
   - asyncio.wait_for(): 超时等待
   - asyncio.gather(): 并发执行多个协程
   - asyncio.TimeoutError: asyncio超时异常

4. re 正则表达式:
   re.search() 在字符串中搜索模式
   re.sub() 替换匹配内容

5. logging 模块:
   log.debug/info/warning/error 记录不同级别的日志

6. nonlocal 关键字:
   在嵌套函数中引用外层函数的变量，用于修改闭包变量

================================================================================

功能说明:
    这是整个引擎最核心的模块，负责：
    1. run_query: 主查询循环，协调AI调用和工具执行
    2. _execute_tool_call: 单个工具调用的完整生命周期
    3. 工具输出管理：超大输出自动分流到文件
    4. 图片预处理：非多模态模型的图片转文字
    5. 错误处理：上下文过长、token限制等API错误恢复
    6. 工具元数据：追踪工具使用历史供上下文使用

架构理解:
    QueryEngine (query_engine.py) 调用 run_query()
    run_query() 管理循环，调用 _execute_tool_call() 执行工具
    两者通过 AsyncIterator[StreamEvent] 通信，产生事件给上层
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable
from uuid import uuid4

from openharness.api.client import (
    ApiMessageCompleteEvent,
    ApiMessageRequest,
    ApiRetryEvent,
    ApiTextDeltaEvent,
    SupportsStreamingMessages,
)
from openharness.api.provider import is_model_multimodal
from openharness.api.usage import UsageSnapshot
from openharness.config.paths import get_data_dir
from openharness.engine.messages import (
    ConversationMessage,
    ImageBlock,
    TextBlock,
    ToolResultBlock,
)
from openharness.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    CompactProgressEvent,
    ErrorEvent,
    StatusEvent,
    StreamEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)
from openharness.hooks import HookEvent, HookExecutor
from openharness.permissions.checker import PermissionChecker
from openharness.services.tool_outputs import tool_output_inline_chars, tool_output_preview_chars
from openharness.tools.base import ToolExecutionContext
from openharness.tools.base import ToolRegistry


# =============================================================================
# 模块级常量定义
# =============================================================================

# 对话压缩状态消息 - 告诉用户正在做什么
AUTO_COMPACT_STATUS_MESSAGE = "Auto-compacting conversation memory to keep things fast and focused."
REACTIVE_COMPACT_STATUS_MESSAGE = "Prompt too long; compacting conversation memory and retrying."

# 最大安全输出token数 - 某些API限制单次最大输出
# 选择128000作为保守上限，覆盖大多数模型的限制
MAX_SAFE_COMPLETION_TOKENS = 128_000

# 日志记录器 - 用于调试和监控
log = logging.getLogger(__name__)


# =============================================================================
# 类型别名定义
# =============================================================================

# PermissionPrompt: 权限请求回调函数类型
# 参数1: 工具名称
# 参数2: 权限原因/描述
# 返回: bool (用户是否授权)
PermissionPrompt = Callable[[str, str], Awaitable[bool]]

# AskUserPrompt: 向用户提问的回调函数类型
# 参数: 提问内容
# 返回: 用户输入的字符串
AskUserPrompt = Callable[[str], Awaitable[str]]


# =============================================================================
# 工具元数据追踪常量 - 限制各类历史记录的数量
# =============================================================================

# 防止工具元数据无限增长，限制各类记录的容量
MAX_TRACKED_READ_FILES = 6        # 最近读取的文件数量上限
MAX_TRACKED_SKILLS = 8            # 最近调用的技能数量上限
MAX_TRACKED_ASYNC_AGENT_EVENTS = 8  # 异步Agent活动事件上限
MAX_TRACKED_ASYNC_AGENT_TASKS = 12 # 异步Agent任务数量上限
MAX_TRACKED_WORK_LOG = 10         # 工作日志条目上限
MAX_TRACKED_USER_GOALS = 5        # 用户目标历史上限
MAX_TRACKED_ACTIVE_ARTIFACTS = 8  # 活跃产物（如打开的文件、URL等）上限
MAX_TRACKED_VERIFIED_WORK = 10     # 已验证工作记录上限


# =============================================================================
# 错误检测辅助函数
# =============================================================================

def _is_prompt_too_long_error(exc: Exception) -> bool:
    """
    =============================================================================
    函数文档: _is_prompt_too_long_error - 检测上下文过长错误

    参数说明:
        exc: API抛出的异常对象

    返回值:
        bool - True表示是上下文/提示过长错误

    作用说明:
        不同API提供商返回错误信息的方式不同：
        - Anthropic: "prompt too long"
        - OpenAI: "context_length_exceeded", "maximum context"
        - 本地模型: 各种自定义错误信息

        这个函数用多个模式匹配来检测是否是"太长"错误，
        因为我们需要对这类错误尝试自动压缩（compact）恢复。

    为什么需要这个函数:
        当上下文太长时，API会拒绝请求。
        我们需要区分这是"太长"错误还是其他错误（如认证失败）。
        对于"太长"错误，可以尝试压缩历史消息后重试。
    =============================================================================
    """
    text = str(exc).lower()
    return any(
        needle in text
        for needle in (
            "prompt too long",
            "context_length_exceeded",
            "context length",
            "maximum context",
            "context window",
            "input tokens exceed",
            "messages resulted in",
            "reduce the length of the messages",
            "configured limit",
            "too many tokens",
            "too large for the model",
            "maximum context length",
            "exceed_context",
            "exceeds the available context size",
            "available context size",
        )
    )


def _bounded_completion_tokens(max_tokens: int, context_window_tokens: int | None = None) -> int:
    """
    =============================================================================
    函数文档: _bounded_completion_tokens - 计算安全的输出token上限

    参数说明:
        max_tokens: 用户配置的期望最大输出token数
        context_window_tokens: 模型上下文窗口大小（可选）

    返回值:
        int - 最终使用的安全token上限

    作用说明:
        某些OpenAI兼容API（如某些本地模型）会拒绝过大的max_tokens参数。
        例如用户配置了max_tokens=100000，但模型只支持128000的总上下文，
        如果已有90000 tokens的输入，输出就不能超过38000。

        这个函数计算一个保守的上限：
        1. 如果提供了context_window_tokens，取其和MAX_SAFE_COMPLETION_TOKENS的较小值
        2. 最终结果不能超过用户配置值

    为什么需要这个函数:
        防止用户配置过大的max_tokens导致每个请求都失败。
        同时保持合理的默认值（不限制时用MAX_SAFE_COMPLETION_TOKENS）。
    =============================================================================
    """
    limit = MAX_SAFE_COMPLETION_TOKENS
    if context_window_tokens is not None and context_window_tokens > 0:
        limit = min(limit, int(context_window_tokens))
    return max(1, min(int(max_tokens), limit))


def _extract_completion_token_limit(exc: Exception) -> int | None:
    """
    =============================================================================
    函数文档: _extract_completion_token_limit - 从错误信息中提取token限制

    参数说明:
        exc: 异常对象

    返回值:
        int | None - 解析出的token限制，如果无法解析则返回None

    作用说明:
        当API报错说"max_tokens太大"时，错误信息通常会包含模型支持的具体数值。
        例如: "Model supports at most 128000 completion tokens"
        这个函数用正则表达式从错误信息中提取这个数值。

    为什么需要这个函数:
        自动从错误中学习API的限制，调整max_tokens后重试。
        提供更好的用户体验，而不是让用户手动修改配置。

    正则表达式说明:
        - r"supports at most\s+(\d+)\s+completion tokens"
        - 匹配 "supports at most 128000 completion tokens"
        - (\d+) 捕获数字部分
    =============================================================================
    """
    text = str(exc).lower().replace(",", "")
    patterns = (
        r"supports at most\s+(\d+)\s+completion tokens",
        r"at most\s+(\d+)\s+completion tokens",
        r"max(?:imum)?(?:_completion)?[_\s-]tokens.*?(?:<=|less than or equal to|at most)\s+(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return max(1, int(match.group(1)))
            except ValueError:
                return None
    return None


def _is_completion_token_limit_error(exc: Exception) -> bool:
    """
    =============================================================================
    函数文档: _is_completion_token_limit_error - 检测max_tokens限制错误

    作用说明:
        检测错误是否是因为max_tokens参数超过了API限制。
        需要同时满足两个条件：
        1. 错误信息包含 "max_tokens" 或 "max_completion_tokens"
        2. 错误信息包含 "too large" 或 "at most" 或 "completion tokens"
    """
    text = str(exc).lower()
    return (
        ("max_tokens" in text or "max_completion_tokens" in text)
        and ("too large" in text or "at most" in text or "completion tokens" in text)
    )


# =============================================================================
# 异常类定义
# =============================================================================

class MaxTurnsExceeded(RuntimeError):
    """
    =============================================================================
    类文档: MaxTurnsExceeded - 最大轮数超出异常

    继承关系:
        RuntimeError -> Exception -> BaseException -> object

    作用说明:
        当AI的推理轮数超过用户配置的限制时抛出。
        例如用户设置max_turns=8，但AI连续调用了10次工具，此异常会触发。

    为什么需要这个异常:
        1. 防止AI进入无限循环（工具调用死循环）
        2. 控制计算资源消耗
        3. 给用户一个明确的终止信号

    属性说明:
        max_turns: 用户配置的最大轮数值，用于错误信息展示
    """
    def __init__(self, max_turns: int) -> None:
        super().__init__(f"Exceeded maximum turn limit ({max_turns})")
        self.max_turns = max_turns


# =============================================================================
# 查询上下文数据类
# =============================================================================

@dataclass
class QueryContext:
    """
    =============================================================================
    类文档: QueryContext - 查询运行上下文

    数据结构说明:
        这是一个数据类，包含执行一次查询所需的所有配置和依赖。
        它在QueryEngine和run_query之间传递，封装了所有必要的状态。

    字段说明:
        api_client: API客户端，负责与AI模型通信
        tool_registry: 工具注册表，提供可用工具列表和执行接口
        permission_checker: 权限检查器，决定操作是否被允许
        cwd: 当前工作目录，用于解析相对文件路径
        model: AI模型标识符
        system_prompt: 系统提示词
        max_tokens: 最大输出token数
        context_window_tokens: 模型上下文窗口大小（可选）
        auto_compact_threshold_tokens: 自动压缩触发阈值（可选）
        permission_prompt: 权限请求回调（可选）
        ask_user_prompt: 用户提问回调（可选）
        max_turns: 最大推理轮数，默认200
        hook_executor: 钩子执行器（可选）
        tool_metadata: 工具元数据存储（可选）

    为什么需要这个类:
        1. 参数传递：将大量相关参数封装成一个对象
        2. 清晰接口：run_query只需接收一个context参数
        3. 可扩展性：新增参数只需修改此数据类
    """

    api_client: SupportsStreamingMessages
    tool_registry: ToolRegistry
    permission_checker: PermissionChecker
    cwd: Path
    model: str
    system_prompt: str
    max_tokens: int
    context_window_tokens: int | None = None
    auto_compact_threshold_tokens: int | None = None
    permission_prompt: PermissionPrompt | None = None
    ask_user_prompt: AskUserPrompt | None = None
    max_turns: int | None = 200
    hook_executor: HookExecutor | None = None
    tool_metadata: dict[str, object] | None = None


# =============================================================================
# 工具元数据追踪函数
# =============================================================================

def _append_capped_unique(bucket: list[Any], value: Any, *, limit: int) -> None:
    """
    =============================================================================
    函数文档: _append_capped_unique - 添加带上限的去重元素

    参数说明:
        bucket: 目标列表
        value: 要添加的值
        limit: 列表最大容量

    作用说明:
        将值添加到列表末尾，但如果列表已满：
        1. 先移除旧的最早元素
        2. 如果值已存在，先移除旧位置
        3. 添加到末尾

    算法步骤:
        1. 如果value已在列表中，先移除它（更新位置）
        2. 添加到列表末尾
        3. 如果超过限制，删除最老的元素

    为什么需要这个函数:
        工具元数据需要保持"最近使用"的历史，
        但又不能无限增长。使用这个函数确保：
        - 最新使用的在末尾
        - 超出限制时删除最早的
    """
    if value in bucket:
        bucket.remove(value)
    bucket.append(value)
    if len(bucket) > limit:
        del bucket[:-limit]


def _task_focus_state(tool_metadata: dict[str, object] | None) -> dict[str, object]:
    """
    =============================================================================
    函数文档: _task_focus_state - 获取或创建任务焦点状态

    参数说明:
        tool_metadata: 工具元数据字典

    返回值:
        dict[str, object] - 任务焦点状态字典

    作用说明:
        管理"任务焦点"相关的状态数据结构。
        这是一种元编程模式：确保字典中始终存在需要的键，
        如果不存在则创建默认值。

    task_focus_state包含的字段:
        - goal: 当前用户目标/任务
        - recent_goals: 最近的目标历史
        - active_artifacts: 活跃产物（如正在编辑的文件）
        - verified_state: 已验证的工作状态
        - next_step: 下一步计划

    为什么需要这个结构:
        帮助AI记住当前在做什么、已经做了什么、接下来要做什么。
        这些信息可以注入到系统提示词中，增强AI的记忆能力。
    """
    if tool_metadata is None:
        return {}
    value = tool_metadata.setdefault(
        "task_focus_state",
        {
            "goal": "",
            "recent_goals": [],
            "active_artifacts": [],
            "verified_state": [],
            "next_step": "",
        },
    )
    if isinstance(value, dict):
        value.setdefault("goal", "")
        value.setdefault("recent_goals", [])
        value.setdefault("active_artifacts", [])
        value.setdefault("verified_state", [])
        value.setdefault("next_step", "")
        return value
    # 如果被意外覆盖为非字典值，重置
    replacement = {
        "goal": "",
        "recent_goals": [],
        "active_artifacts": [],
        "verified_state": [],
        "next_step": "",
    }
    tool_metadata["task_focus_state"] = replacement
    return replacement


def _summarize_focus_text(text: str) -> str:
    """
    =============================================================================
    函数文档: _summarize_focus_text - 文本摘要化

    参数说明:
        text: 原始文本

    返回值:
        str - 规范化后的摘要文本

    作用说明:
        1. 规范化空白：多个空格/换行合并为一个
        2. 长度限制：截断到240字符
        3. 空文本处理：返回空字符串

    为什么需要这个函数:
        用户输入可能很长，但我们只需要保存关键信息。
        240字符是一个平衡值：足够保存意图，又不会占用太多上下文。
    """
    normalized = " ".join(text.split())
    if not normalized:
        return ""
    return normalized[:240]


def remember_user_goal(
    tool_metadata: dict[str, object] | None,
    prompt: str,
) -> None:
    """
    =============================================================================
    函数文档: remember_user_goal - 记录用户目标

    作用说明:
        当用户发送新消息时，提取并保存其意图/目标。
        这个目标会被追踪，供后续上下文使用。

    数据更新:
        1. 更新当前goal为用户输入的摘要
        2. 将新目标添加到recent_goals历史
        3. 使用_append_capped_unique保持历史在限制内
    """
    state = _task_focus_state(tool_metadata)
    summary = _summarize_focus_text(prompt)
    if not summary:
        return
    recent_goals = state.setdefault("recent_goals", [])
    if isinstance(recent_goals, list):
        _append_capped_unique(recent_goals, summary, limit=MAX_TRACKED_USER_GOALS)
    state["goal"] = summary


def _remember_active_artifact(
    tool_metadata: dict[str, object] | None,
    artifact: str,
) -> None:
    """
    =============================================================================
    函数文档: _remember_active_artifact - 记录活跃产物

    参数说明:
        artifact: 产物标识，如文件路径、URL、技能名等

    作用说明:
        追踪用户正在操作或最近操作的"产物"。
        这帮助AI记住当前会话中涉及的文件、页面等。

    示例产物:
        - 文件路径: /project/src/main.py
        - URL: https://api.example.com
        - 技能名: skill:my-custom-skill
    """
    normalized = artifact.strip()
    if not normalized:
        return
    state = _task_focus_state(tool_metadata)
    artifacts = state.setdefault("active_artifacts", [])
    if isinstance(artifacts, list):
        _append_capped_unique(artifacts, normalized[:240], limit=MAX_TRACKED_ACTIVE_ARTIFACTS)


def _remember_verified_work(
    tool_metadata: dict[str, object] | None,
    entry: str,
) -> None:
    """
    =============================================================================
    函数文档: _remember_verified_work - 记录已验证工作

    参数说明:
        entry: 工作描述

    作用说明:
        记录AI已经完成并验证的工作。
        这帮助AI记住已经做过什么，避免重复工作。
    """
    normalized = entry.strip()
    if not normalized:
        return
    bucket = _tool_metadata_bucket(tool_metadata, "recent_verified_work")
    _append_capped_unique(bucket, normalized[:320], limit=MAX_TRACKED_VERIFIED_WORK)
    state = _task_focus_state(tool_metadata)
    verified_state = state.setdefault("verified_state", [])
    if isinstance(verified_state, list):
        _append_capped_unique(verified_state, normalized[:320], limit=MAX_TRACKED_VERIFIED_WORK)


def _tool_metadata_bucket(
    tool_metadata: dict[str, object] | None,
    key: str,
) -> list[Any]:
    """
    =============================================================================
    函数文档: _tool_metadata_bucket - 获取或创建元数据桶

    参数说明:
        tool_metadata: 工具元数据字典
        key: 桶的键名

    返回值:
        list[Any] - 对应的列表

    作用说明:
        通用工具元数据访问模式：
        获取指定键的列表，如果不存在则创建空列表。
        如果值存在但不是列表类型，重置为空列表。

    为什么需要这个函数:
        tool_metadata是动态字典，字段可能不存在或类型错误。
        这个函数提供安全访问，避免KeyError或TypeError。
    """
    if tool_metadata is None:
        return []
    value = tool_metadata.setdefault(key, [])
    if isinstance(value, list):
        return value
    replacement: list[Any] = []
    tool_metadata[key] = replacement
    return replacement


def _remember_read_file(
    tool_metadata: dict[str, object] | None,
    *,
    path: str,
    offset: int,
    limit: int,
    output: str,
) -> None:
    """
    =============================================================================
    函数文档: _remember_read_file - 记录文件读取操作

    参数说明:
        tool_metadata: 工具元数据
        path: 文件路径
        offset: 读取的起始行
        limit: 读取的行数
        output: 文件内容

    作用说明:
        追踪最近读取的文件，包含：
        - 文件路径
        - 行范围（lines 1-100格式）
        - 内容预览（前6行的主要内容）
        - 时间戳

    为什么记录文件读取:
        1. 避免重复读取：知道哪些文件已被查看
        2. 上下文注入：将读取过的文件信息提供给AI
        3. 工作追踪：记录AI在查看什么文件

    预览生成逻辑:
        1. 按行分割输出
        2. 取前6行
        3. 去除空白
        4. 用"|"连接
        5. 限制总长度320字符
    """
    bucket = _tool_metadata_bucket(tool_metadata, "read_file_state")
    preview_lines = [line.strip() for line in output.splitlines()[:6] if line.strip()]
    entry = {
        "path": path,
        "span": f"lines {offset + 1}-{offset + limit}",
        "preview": " | ".join(preview_lines)[:320],
        "timestamp": time.time(),
    }
    if isinstance(bucket, list):
        # 去重：移除同路径的旧记录
        bucket[:] = [
            existing
            for existing in bucket
            if not isinstance(existing, dict) or str(existing.get("path") or "") != path
        ]
        bucket.append(entry)
        if len(bucket) > MAX_TRACKED_READ_FILES:
            del bucket[:-MAX_TRACKED_READ_FILES]


def _remember_skill_invocation(
    tool_metadata: dict[str, object] | None,
    *,
    skill_name: str,
) -> None:
    """
    =============================================================================
    函数文档: _remember_skill_invocation - 记录技能调用
    """
    bucket = _tool_metadata_bucket(tool_metadata, "invoked_skills")
    normalized = skill_name.strip()
    if not normalized:
        return
    if normalized in bucket:
        bucket.remove(normalized)
    bucket.append(normalized)
    if len(bucket) > MAX_TRACKED_SKILLS:
        del bucket[:-MAX_TRACKED_SKILLS]


def _remember_async_agent_activity(
    tool_metadata: dict[str, object] | None,
    *,
    tool_name: str,
    tool_input: dict[str, object],
    output: str,
) -> None:
    """
    =============================================================================
    函数文档: _remember_async_agent_activity - 记录异步Agent活动

    作用说明:
        当使用agent工具启动子Agent或发送消息时记录活动。
        生成活动摘要，格式如：
        - "Spawned async agent. 帮我写测试代码"
        - "Sent follow-up message to async agent abc123"
    """
    bucket = _tool_metadata_bucket(tool_metadata, "async_agent_state")
    if tool_name == "agent":
        description = str(tool_input.get("description") or tool_input.get("prompt") or "").strip()
        summary = f"Spawned async agent. {description}".strip()
        if output.strip():
            summary = f"{summary} [{output.strip()[:180]}]".strip()
    elif tool_name == "send_message":
        target = str(tool_input.get("task_id") or "").strip()
        summary = f"Sent follow-up message to async agent {target}".strip()
    else:
        summary = output.strip()[:220] or f"Async agent activity via {tool_name}"
    bucket.append(summary)
    if len(bucket) > MAX_TRACKED_ASYNC_AGENT_EVENTS:
        del bucket[:-MAX_TRACKED_ASYNC_AGENT_EVENTS]


def _parse_spawned_agent_identity(
    output: str,
    metadata: dict[str, object] | None = None,
) -> tuple[str, str] | None:
    """
    =============================================================================
    函数文档: _parse_spawned_agent_identity - 解析Agent身份信息

    返回值:
        tuple[str, str] | None - (agent_id, task_id) 或 None

    作用说明:
        从agent工具的输出中提取新创建的Agent的身份信息。
        可以从两个来源获取：
        1. result_metadata中的agent_id和task_id
        2. 输出文本中的匹配模式: "Spawned agent xxx (task_id=yyy)"

    为什么需要这个函数:
        异步Agent启动后，主Agent需要知道如何与其通信。
        通过追踪agent_id和task_id，可以发送后续消息或查询状态。
    """
    if isinstance(metadata, dict):
        agent_id = str(metadata.get("agent_id") or "").strip()
        task_id = str(metadata.get("task_id") or "").strip()
        if agent_id and task_id:
            return agent_id, task_id
    match = re.search(r"Spawned agent (.+?) \(task_id=(\S+?)(?:[,)]|$)", output.strip())
    if match is None:
        return None
    return match.group(1).strip(), match.group(2).strip()


def _remember_async_agent_task(
    tool_metadata: dict[str, object] | None,
    *,
    tool_name: str,
    tool_input: dict[str, object],
    output: str,
    result_metadata: dict[str, object] | None = None,
) -> None:
    """
    =============================================================================
    函数文档: _remember_async_agent_task - 记录异步Agent任务
    """
    if tool_name != "agent":
        return
    identity = _parse_spawned_agent_identity(output, result_metadata)
    if identity is None:
        return
    agent_id, task_id = identity
    bucket = _tool_metadata_bucket(tool_metadata, "async_agent_tasks")
    description = str(tool_input.get("description") or tool_input.get("prompt") or "").strip()
    entry = {
        "agent_id": agent_id,
        "task_id": task_id,
        "description": description[:240],
        "status": "spawned",
        "notification_sent": False,
        "spawned_at": time.time(),
    }
    # 去重：移除同task_id的旧记录
    bucket[:] = [
        existing
        for existing in bucket
        if not isinstance(existing, dict) or str(existing.get("task_id") or "") != task_id
    ]
    bucket.append(entry)
    if len(bucket) > MAX_TRACKED_ASYNC_AGENT_TASKS:
        del bucket[:-MAX_TRACKED_ASYNC_AGENT_TASKS]


def _remember_work_log(
    tool_metadata: dict[str, object] | None,
    *,
    entry: str,
) -> None:
    """
    =============================================================================
    函数文档: _remember_work_log - 记录工作日志
    """
    bucket = _tool_metadata_bucket(tool_metadata, "recent_work_log")
    normalized = entry.strip()
    if not normalized:
        return
    bucket.append(normalized[:320])
    if len(bucket) > MAX_TRACKED_WORK_LOG:
        del bucket[:-MAX_TRACKED_WORK_LOG]


def _update_plan_mode(tool_metadata: dict[str, object] | None, mode: str) -> None:
    """
    =============================================================================
    函数文档: _update_plan_mode - 更新计划模式状态
    """
    if tool_metadata is None:
        return
    tool_metadata["permission_mode"] = mode


def _record_tool_carryover(
    context: QueryContext,
    *,
    tool_name: str,
    tool_input: dict[str, object],
    tool_output: str,
    tool_result_metadata: dict[str, object] | None,
    is_error: bool,
    resolved_file_path: str | None,
) -> None:
    """
    =============================================================================
    函数文档: _record_tool_carryover - 记录工具执行信息到元数据

    参数说明:
        context: 查询上下文
        tool_name: 工具名称
        tool_input: 工具输入参数
        tool_output: 工具输出
        tool_result_metadata: 工具返回的元数据
        is_error: 是否出错
        resolved_file_path: 解析后的文件路径

    作用说明:
        这是工具执行的"收尾"工作。
        每当工具执行完成（无论成功还是失败），调用此函数记录：
        1. 读取的文件 -> 记录到read_file_state
        2. 调用的技能 -> 记录到invoked_skills
        3. 异步Agent活动 -> 记录到async_agent_state
        4. 各种操作 -> 记录到recent_verified_work和recent_work_log

    为什么需要这个函数:
        这些元数据会被注入到系统提示词中，让AI"记住"：
        - 最近读取了哪些文件
        - 最近调用了哪些工具
        - 当前正在执行什么任务
        从而提供更好的上下文感知能力。

    为什么is_error的工具不记录:
        出错可能意味着操作没有实际执行成功，
        记录未成功的操作会误导后续决策。
    """
    if is_error:
        return

    # 文件相关操作
    if resolved_file_path is not None:
        _remember_active_artifact(context.tool_metadata, resolved_file_path)
    if tool_name == "read_file" and resolved_file_path is not None:
        offset = int(tool_input.get("offset") or 0)
        limit = int(tool_input.get("limit") or 200)
        _remember_read_file(
            context.tool_metadata,
            path=resolved_file_path,
            offset=offset,
            limit=limit,
            output=tool_output,
        )
        _remember_verified_work(
            context.tool_metadata,
            f"Inspected file {resolved_file_path} (lines {offset + 1}-{offset + limit})",
        )

    # 技能相关操作
    elif tool_name == "skill":
        _remember_skill_invocation(
            context.tool_metadata,
            skill_name=str(tool_input.get("name") or ""),
        )
        skill_name = str(tool_input.get("name") or "").strip()
        if skill_name:
            _remember_active_artifact(context.tool_metadata, f"skill:{skill_name}")
            _remember_verified_work(context.tool_metadata, f"Loaded skill {skill_name}")

    # 异步Agent相关操作
    elif tool_name in {"agent", "send_message"}:
        _remember_async_agent_activity(
            context.tool_metadata,
            tool_name=tool_name,
            tool_input=tool_input,
            output=tool_output,
        )
        _remember_async_agent_task(
            context.tool_metadata,
            tool_name=tool_name,
            tool_input=tool_input,
            output=tool_output,
            result_metadata=tool_result_metadata,
        )
        description = str(tool_input.get("description") or tool_input.get("prompt") or tool_name).strip()
        _remember_verified_work(
            context.tool_metadata,
            f"Confirmed async-agent activity via {tool_name}: {description[:180]}",
        )

    # 模式切换
    elif tool_name == "enter_plan_mode":
        _update_plan_mode(context.tool_metadata, "plan")
    elif tool_name == "exit_plan_mode":
        _update_plan_mode(context.tool_metadata, "default")

    # 网络相关操作
    elif tool_name == "web_fetch":
        url = str(tool_input.get("url") or "").strip()
        if url:
            _remember_active_artifact(context.tool_metadata, url)
            _remember_verified_work(context.tool_metadata, f"Fetched remote content from {url}")
    elif tool_name == "web_search":
        query = str(tool_input.get("query") or "").strip()
        if query:
            _remember_verified_work(context.tool_metadata, f"Ran web search for {query[:180]}")
    elif tool_name == "glob":
        pattern = str(tool_input.get("pattern") or "").strip()
        if pattern:
            _remember_verified_work(context.tool_metadata, f"Expanded glob pattern {pattern[:180]}")
    elif tool_name == "grep":
        pattern = str(tool_input.get("pattern") or "").strip()
        if pattern:
            _remember_verified_work(context.tool_metadata, f"Checked repository matches for grep pattern {pattern[:180]}")
    elif tool_name == "bash":
        command = str(tool_input.get("command") or "").strip()
        summary = tool_output.splitlines()[0].strip() if tool_output.strip() else "no output"
        _remember_verified_work(
            context.tool_metadata,
            f"Ran bash command {command[:160]} [{summary[:120]}]",
        )

    # 工作日志记录
    if tool_name == "read_file" and resolved_file_path is not None:
        _remember_work_log(
            context.tool_metadata,
            entry=f"Read file {resolved_file_path}",
        )
    elif tool_name == "bash":
        command = str(tool_input.get("command") or "").strip()
        summary = tool_output.splitlines()[0].strip() if tool_output.strip() else "no output"
        _remember_work_log(
            context.tool_metadata,
            entry=f"Ran bash: {command[:160]} [{summary[:120]}]",
        )
    elif tool_name == "grep":
        pattern = str(tool_input.get("pattern") or "").strip()
        _remember_work_log(
            context.tool_metadata,
            entry=f"Searched with grep pattern={pattern[:160]}",
        )
    elif tool_name == "skill":
        _remember_work_log(
            context.tool_metadata,
            entry=f"Loaded skill {str(tool_input.get('name') or '').strip()}",
        )
    elif tool_name in {"agent", "send_message"}:
        _remember_work_log(
            context.tool_metadata,
            entry=f"Async agent action via {tool_name}",
        )
    elif tool_name == "enter_plan_mode":
        _remember_work_log(context.tool_metadata, entry="Entered plan mode")
    elif tool_name == "exit_plan_mode":
        _remember_work_log(context.tool_metadata, entry="Exited plan mode")


# =============================================================================
# 工具输出分流函数
# =============================================================================

def _tool_artifact_dir() -> Path:
    """
    =============================================================================
    函数文档: _tool_artifact_dir - 获取工具产物目录

    返回值:
        Path - 工具产物目录的Path对象

    作用说明:
        获取或创建保存大体积工具输出的目录。
        路径: data_dir/tool_artifacts/

    为什么需要这个目录:
        当工具输出非常大时（如读取大文件），不适合放在对话历史中。
        会保存到文件，只在对话中保留预览。
    """
    artifact_dir = get_data_dir() / "tool_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


def _safe_tool_artifact_name(tool_name: str) -> str:
    """
    =============================================================================
    函数文档: _safe_tool_artifact_name - 生成安全的产物文件名

    参数说明:
        tool_name: 工具名称

    返回值:
        str - 安全化的文件名

    作用说明:
        1. 移除或替换工具名中的非法字符（只保留A-Za-z0-9_.-）
        2. 限制长度为80字符

    为什么需要这个函数:
        工具名可能包含特殊字符，但文件系统对文件名有要求。
        如 bash -> "bash"，但 git commit -m "fix" -> "git_commit_-m__fix"
    """
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", tool_name.strip())
    return (normalized or "tool")[:80]


def _offload_tool_output_if_needed(
    *,
    tool_name: str,
    tool_use_id: str,
    output: str,
) -> tuple[str, Path | None]:
    """
    =============================================================================
    函数文档: _offload_tool_output_if_needed - 按需分流工具输出

    参数说明:
        tool_name: 工具名称
        tool_use_id: 工具调用ID
        output: 原始输出

    返回值:
        tuple[str, Path | None] - (处理后的输出, 文件路径或None)

    作用说明:
        当工具输出超过阈值时，将完整内容保存到文件，只返回预览。
        这避免了对话历史过长导致上下文超出限制。

    分流逻辑:
        1. 检查输出长度是否超过inline_limit
        2. 如果没超过，直接返回原输出
        3. 如果超过：
           a. 生成带时间戳的唯一文件名
           b. 将完整内容写入文件
           c. 返回预览文本，告知用户完整内容已保存

    为什么需要这个函数:
        某些工具（如cat读取大文件、grep大量匹配）可能产生巨大输出。
        如果全部放入对话历史，token消耗会急剧增加。
        通过分流，保持对话轻量的同时不丢失信息。
    """
    inline_limit = tool_output_inline_chars()
    if len(output) <= inline_limit:
        return output, None

    # 生成文件路径: 时间戳-工具名-唯一ID.txt
    artifact_path = (
        _tool_artifact_dir()
        / f"{time.strftime('%Y%m%d-%H%M%S')}-{_safe_tool_artifact_name(tool_name)}-{uuid4().hex[:12]}.txt"
    )
    artifact_path.write_text(output, encoding="utf-8", errors="replace")

    # 构建预览文本
    preview = output[:tool_output_preview_chars()]
    omitted = max(0, len(output) - len(preview))
    inline = (
        "[Tool output truncated]\n"
        f"Tool: {tool_name}\n"
        f"Tool use id: {tool_use_id}\n"
        f"Original size: {len(output)} chars\n"
        f"Full output saved to: {artifact_path}\n"
        f"Inline preview: first {len(preview)} chars"
    )
    if omitted:
        inline += f" ({omitted} chars omitted)"
    if preview:
        inline += f"\n\nPreview:\n{preview}"
    return inline, artifact_path


# =============================================================================
# 图片预处理函数
# =============================================================================

_IMAGE_PREPROCESS_STATUS = "Converting image to text description via vision model…"


async def _preprocess_images_in_messages(
    messages: list[ConversationMessage],
    context: QueryContext,
) -> AsyncIterator[StreamEvent]:
    """
    =============================================================================
    函数文档: _preprocess_images_in_messages - 图片预处理（转文字）

    参数说明:
        messages: 对话消息列表
        context: 查询上下文

    返回值:
        AsyncIterator[StreamEvent] - 状态事件流

    作用说明:
        当使用不支持多模态的模型时，将用户上传的图片转换为文字描述。
        这使得非视觉模型也能"理解"图片内容。

    为什么需要这个功能:
        1. 兼容性：不是所有模型都支持图片输入
        2. 经济性：视觉模型通常更贵
        3. 优雅降级：通过文字描述让非视觉模型也能处理图片

    实现逻辑:
        1. 检查模型是否支持多模态，不支持则跳过
        2. 检查是否配置了vision_model_config，没有则跳过
        3. 扫描消息中的ImageBlock
        4. 并行调用image_to_text工具转换为描述
        5. 用TextBlock替换ImageBlock

    image_to_text工具:
        一个特殊的内置工具，调用视觉模型生成图片描述。
        配置在vision_model_config中。
    """
    if is_model_multimodal(context.model):
        return

    vision_config = context.tool_metadata.get("vision_model_config")
    if not vision_config:
        return

    # 收集所有图片块
    pending: list[tuple[int, int, ImageBlock]] = []
    for msg_idx, msg in enumerate(messages):
        if msg.role != "user":
            continue
        for blk_idx, block in enumerate(msg.content):
            if isinstance(block, ImageBlock):
                pending.append((msg_idx, blk_idx, block))

    if not pending:
        return

    yield StatusEvent(message=_IMAGE_PREPROCESS_STATUS)

    # 并行处理所有图片
    async def _describe(msg_idx: int, blk_idx: int, block: ImageBlock) -> tuple[int, int, str]:
        tool = context.tool_registry.get("image_to_text")
        if tool is None:
            return msg_idx, blk_idx, "[Image: could not describe — image_to_text tool not available]"

        # 构建工具输入
        tool_input_data: dict[str, object] = {
            "image_data": block.data,
            "media_type": block.media_type,
            "prompt": "Describe this image in detail, including any text, "
                      "UI elements, code, diagrams, or visual information present.",
        }

        try:
            parsed = tool.input_model.model_validate(tool_input_data)
        except Exception:
            return msg_idx, blk_idx, "[Image: could not parse image data]"

        # 执行工具
        exec_context = ToolExecutionContext(
            cwd=context.cwd,
            metadata={
                "vision_model_config": vision_config,
                **(context.tool_metadata or {}),
            },
        )
        result = await tool.execute(parsed, exec_context)
        if result.is_error:
            return msg_idx, blk_idx, f"[Image description failed: {result.output}]"
        return msg_idx, blk_idx, result.output

    # asyncio.gather: 并行执行所有图片描述任务
    results = await asyncio.gather(*[_describe(mi, bi, blk) for mi, bi, blk in pending])

    # 原地替换ImageBlock为TextBlock
    for msg_idx, blk_idx, description in results:
        msg = messages[msg_idx]
        msg.content[blk_idx] = TextBlock(text=description)


# =============================================================================
# 核心查询运行函数
# =============================================================================

async def run_query(
    context: QueryContext,
    messages: list[ConversationMessage],
) -> AsyncIterator[tuple[StreamEvent, UsageSnapshot | None]]:
    """
    =============================================================================
    核心函数文档: run_query - 执行查询循环

    参数说明:
        context: QueryContext - 查询上下文
        messages: list[ConversationMessage] - 对话消息历史

    返回值:
        AsyncIterator[tuple[StreamEvent, UsageSnapshot | None]] - 事件和使用量对

    作用说明:
        这是整个引擎最核心的函数，负责：
        1. 管理对话循环（while turn < max_turns）
        2. 调用AI API获取响应
        3. 处理AI的工具调用请求
        4. 自动压缩过长的对话历史
        5. 处理各种错误和恢复

    循环流程:
        ┌─────────────────────────────────────────────────┐
        │                  开始循环                         │
        └─────────────────┬───────────────────────────────┘
                          ▼
        ┌─────────────────────────────────────────────────┐
        │  1. 自动压缩检查 (auto-compact)                  │
        │     如果token过多，压缩历史消息                   │
        └─────────────────┬───────────────────────────────┘
                          ▼
        ┌─────────────────────────────────────────────────┐
        │  2. 图片预处理 (preprocess_images)              │
        │     非多模态模型转图片为文字                     │
        └─────────────────┬───────────────────────────────┘
                          ▼
        ┌─────────────────────────────────────────────────┐
        │  3. 调用API (stream_message)                    │
        │     发送请求到AI模型                            │
        │     - 流式接收文本片段                           │
        │     - 接收完整消息                               │
        └─────────────────┬───────────────────────────────┘
                          ▼
        ┌─────────────────────────────────────────────────┐
        │  4. 错误处理                                    │
        │     - 超长错误 -> 压缩重试                       │
        │     - token限制 -> 调整重试                      │
        │     - 网络错误 -> 报告                           │
        └─────────────────┬───────────────────────────────┘
                          ▼
        ┌─────────────────────────────────────────────────┐
        │  5. 检查工具调用                                │
        │     - 无工具调用 -> 结束                         │
        │     - 有工具调用 -> 执行工具                     │
        └─────────────────┬───────────────────────────────┘
                          ▼
        ┌─────────────────────────────────────────────────┐
        │  6. 执行工具                                    │
        │     - 权限检查                                  │
        │     - 工具执行                                  │
        │     - 结果转换                                  │
        └─────────────────┬───────────────────────────────┘
                          ▼
        ┌─────────────────────────────────────────────────┐
        │  7. 添加工具结果到消息                          │
        │     回到步骤3继续下一轮                          │
        └─────────────────────────────────────────────────┘

    事件产出:
        - AssistantTextDelta: AI输出的文本片段
        - AssistantTurnComplete: AI一轮回复完成
        - ToolExecutionStarted: 工具开始执行
        - ToolExecutionCompleted: 工具执行完成
        - StatusEvent: 状态消息
        - CompactProgressEvent: 压缩进度
        - ErrorEvent: 错误

    异常:
        - MaxTurnsExceeded: 超过最大轮数
        - RuntimeError: 异常退出
    """
    from openharness.services.compact import (
        AutoCompactState,
        auto_compact_if_needed,
    )

    compact_state = AutoCompactState()
    reactive_compact_attempted = False
    last_compaction_result: tuple[list[ConversationMessage], bool] = (messages, False)

    # 计算安全的max_tokens
    effective_max_tokens = _bounded_completion_tokens(
        context.max_tokens,
        context.context_window_tokens,
    )
    reported_token_clamp = False

    # 压缩任务的内部生成器
    async def _stream_compaction(
        *,
        trigger: str,
        force: bool = False,
    ) -> AsyncIterator[tuple[StreamEvent, UsageSnapshot | None]]:
        """
        内部函数: _stream_compaction - 执行压缩并产出事件
        """
        nonlocal last_compaction_result
        # 使用队列传递进度事件
        progress_queue: asyncio.Queue[CompactProgressEvent] = asyncio.Queue()

        async def _progress(event: CompactProgressEvent) -> None:
            await progress_queue.put(event)

        # 创建后台压缩任务
        task = asyncio.create_task(
            auto_compact_if_needed(
                messages,
                api_client=context.api_client,
                model=context.model,
                system_prompt=context.system_prompt,
                state=compact_state,
                progress_callback=_progress,
                force=force,
                trigger=trigger,
                hook_executor=context.hook_executor,
                carryover_metadata=context.tool_metadata,
                context_window_tokens=context.context_window_tokens,
                auto_compact_threshold_tokens=context.auto_compact_threshold_tokens,
            )
        )

        # 消费进度队列，直到任务完成
        while True:
            try:
                event = await asyncio.wait_for(progress_queue.get(), timeout=0.05)
                yield event, None
            except asyncio.TimeoutError:
                if task.done():
                    break
                continue

        # 消费剩余事件
        while not progress_queue.empty():
            yield progress_queue.get_nowait(), None
        last_compaction_result = await task

    # 主循环
    turn_count = 0
    while context.max_turns is None or turn_count < context.max_turns:
        turn_count += 1

        # 如果max_tokens被调整过，报告一次
        if effective_max_tokens != context.max_tokens and not reported_token_clamp:
            reported_token_clamp = True
            yield StatusEvent(
                message=(
                    "Requested max_tokens="
                    f"{context.max_tokens} exceeds the safe per-request output cap; "
                    f"using {effective_max_tokens}."
                )
            ), None

        # 步骤1: 自动压缩检查
        async for event, usage in _stream_compaction(trigger="auto"):
            yield event, usage
        messages, was_compacted = last_compaction_result

        # 步骤2: 图片预处理
        async for event in _preprocess_images_in_messages(messages, context):
            yield event, None

        # 准备API请求
        final_message: ConversationMessage | None = None
        usage = UsageSnapshot()

        # 步骤3: 调用API
        try:
            async for event in context.api_client.stream_message(
                ApiMessageRequest(
                    model=context.model,
                    messages=messages,
                    system_prompt=context.system_prompt,
                    max_tokens=effective_max_tokens,
                    tools=context.tool_registry.to_api_schema(),
                )
            ):
                if isinstance(event, ApiTextDeltaEvent):
                    yield AssistantTextDelta(text=event.text), None
                    continue
                if isinstance(event, ApiRetryEvent):
                    yield StatusEvent(
                        message=(
                            f"Request failed; retrying in {event.delay_seconds:.1f}s "
                            f"(attempt {event.attempt + 1} of {event.max_attempts}): {event.message}"
                        )
                    ), None
                    continue

                if isinstance(event, ApiMessageCompleteEvent):
                    final_message = event.message
                    usage = event.usage

        except Exception as exc:
            # 步骤4: 错误处理
            error_msg = str(exc)

            # 情况1: max_tokens太大
            if _is_completion_token_limit_error(exc):
                supported_limit = _extract_completion_token_limit(exc)
                if supported_limit is not None and effective_max_tokens > supported_limit:
                    previous_max_tokens = effective_max_tokens
                    effective_max_tokens = supported_limit
                    yield StatusEvent(
                        message=(
                            f"Model rejected max_tokens={previous_max_tokens}; "
                            f"retrying with provider limit {effective_max_tokens}."
                        )
                    ), None
                    # 重试当前轮（不计入turn_count）
                    turn_count = max(0, turn_count - 1)
                    continue

            # 情况2: 上下文太长
            if not reactive_compact_attempted and _is_prompt_too_long_error(exc):
                reactive_compact_attempted = True
                yield StatusEvent(message=REACTIVE_COMPACT_STATUS_MESSAGE), None
                async for event, usage in _stream_compaction(trigger="reactive", force=True):
                    yield event, usage
                messages, was_compacted = last_compaction_result
                if was_compacted:
                    continue

            # 情况3: 网络错误
            if "connect" in error_msg.lower() or "timeout" in error_msg.lower() or "network" in error_msg.lower():
                yield ErrorEvent(message=f"Network error: {error_msg}. Check your internet connection and try again."), None
            else:
                yield ErrorEvent(message=f"API error: {error_msg}"), None
            return

        # 验证响应
        if final_message is None:
            raise RuntimeError("Model stream finished without a final message")

        # 协调器上下文处理
        coordinator_context_message: ConversationMessage | None = None
        if context.system_prompt.startswith("You are a **coordinator**."):
            if messages and messages[-1].role == "user" and messages[-1].text.startswith("# Coordinator User Context"):
                coordinator_context_message = messages.pop()

        # 检查空消息
        if final_message.role == "assistant" and final_message.is_effectively_empty():
            log.warning("dropping empty assistant message from provider response")
            yield ErrorEvent(
                message=(
                    "Model returned an empty assistant message. "
                    "The turn was ignored to keep the session healthy."
                )
            ), usage
            return

        # 添加消息到历史
        messages.append(final_message)
        yield AssistantTurnComplete(message=final_message, usage=usage), usage

        # 恢复协调器上下文
        if coordinator_context_message is not None:
            messages.append(coordinator_context_message)

        # 检查是否有工具调用
        if not final_message.tool_uses:
            # 无工具调用，查询完成
            if context.hook_executor is not None:
                await context.hook_executor.execute(
                    HookEvent.STOP,
                    {
                        "event": HookEvent.STOP.value,
                        "stop_reason": "tool_uses_empty",
                    },
                )
            return

        # 步骤5-6: 执行工具
        tool_calls = final_message.tool_uses

        if len(tool_calls) == 1:
            # 单工具：顺序执行，立即产出事件
            tc = tool_calls[0]
            yield ToolExecutionStarted(tool_name=tc.name, tool_input=tc.input), None
            result = await _execute_tool_call(context, tc.name, tc.id, tc.input)
            yield ToolExecutionCompleted(
                tool_name=tc.name,
                output=result.content,
                is_error=result.is_error,
            ), None
            tool_results = [result]
        else:
            # 多工具：并发执行
            for tc in tool_calls:
                yield ToolExecutionStarted(tool_name=tc.name, tool_input=tc.input), None

            async def _run(tc):
                return await _execute_tool_call(context, tc.name, tc.id, tc.input)

            # return_exceptions=True: 单个工具失败不影响其他工具
            # 这是关键设计：如果一个工具失败就放弃所有工具，
            # 会导致对话中缺少tool_result，API会拒绝下一轮请求
            raw_results = await asyncio.gather(
                *[_run(tc) for tc in tool_calls], return_exceptions=True
            )
            tool_results = []
            for tc, result in zip(tool_calls, raw_results):
                if isinstance(result, BaseException):
                    log.exception(
                        "tool execution raised: name=%s id=%s",
                        tc.name,
                        tc.id,
                        exc_info=result,
                    )
                    result = ToolResultBlock(
                        tool_use_id=tc.id,
                        content=f"Tool {tc.name} failed: {type(result).__name__}: {result}",
                        is_error=True,
                    )
                tool_results.append(result)

            # 产出所有工具完成事件
            for tc, result in zip(tool_calls, tool_results):
                yield ToolExecutionCompleted(
                    tool_name=tc.name,
                    output=result.content,
                    is_error=result.is_error,
                ), None

        # 步骤7: 添加工具结果到消息，继续循环
        messages.append(ConversationMessage(role="user", content=tool_results))

    # 循环结束：超出最大轮数
    if context.max_turns is not None:
        raise MaxTurnsExceeded(context.max_turns)
    raise RuntimeError("Query loop exited without a max_turns limit or final response")


# =============================================================================
# 工具执行函数
# =============================================================================

async def _execute_tool_call(
    context: QueryContext,
    tool_name: str,
    tool_use_id: str,
    tool_input: dict[str, object],
) -> ToolResultBlock:
    """
    =============================================================================
    核心函数文档: _execute_tool_call - 执行单个工具调用

    参数说明:
        context: QueryContext - 查询上下文
        tool_name: str - 工具名称
        tool_use_id: str - 工具调用ID
        tool_input: dict - 工具输入参数

    返回值:
        ToolResultBlock - 工具执行结果

    作用说明:
        执行AI请求的单个工具调用，包含完整的生命周期：

        1. 前置Hook执行 (PRE_TOOL_USE)
        2. 输入验证
        3. 权限检查
        4. 用户确认（如需要）
        5. 工具执行
        6. 输出分流（如需要）
        7. 元数据记录
        8. 后置Hook执行 (POST_TOOL_USE)

    错误处理:
        - 工具不存在 -> 返回错误结果
        - 输入验证失败 -> 返回错误结果
        - 权限被拒绝 -> 返回错误结果
        - 工具执行异常 -> 捕获并返回错误结果

    为什么返回ToolResultBlock而不是抛出异常:
        即使工具执行出错，也要返回一个有效的ToolResultBlock。
        这样AI可以"看到"错误信息，决定如何处理。
        如果抛出异常，会导致对话中断。
    """

    
    # 前置Hook
    if context.hook_executor is not None:
        pre_hooks = await context.hook_executor.execute(
            HookEvent.PRE_TOOL_USE,
            {"tool_name": tool_name, "tool_input": tool_input, "event": HookEvent.PRE_TOOL_USE.value},
        )
        if pre_hooks.blocked:
            return ToolResultBlock(
                tool_use_id=tool_use_id,
                content=pre_hooks.reason or f"pre_tool_use hook blocked {tool_name}",
                is_error=True,
            )

    log.debug("tool_call start: %s id=%s", tool_name, tool_use_id)

    # 获取工具
    tool = context.tool_registry.get(tool_name)
    if tool is None:
        log.warning("unknown tool: %s", tool_name)
        return ToolResultBlock(
            tool_use_id=tool_use_id,
            content=f"Unknown tool: {tool_name}",
            is_error=True,
        )

    # 输入验证
    try:
        parsed_input = tool.input_model.model_validate(tool_input)
    except Exception as exc:
        log.warning("invalid input for %s: %s", tool_name, exc)
        return ToolResultBlock(
            tool_use_id=tool_use_id,
            content=f"Invalid input for {tool_name}: {exc}",
            is_error=True,
        )

    # 提取权限检查所需的路径和命令
    _file_path = _resolve_permission_file_path(context.cwd, tool_input, parsed_input)
    _command = _extract_permission_command(tool_input, parsed_input)

    log.debug("permission check: %s read_only=%s path=%s cmd=%s",
              tool_name, tool.is_read_only(parsed_input), _file_path, _command and _command[:80])

    # 权限检查
    decision = context.permission_checker.evaluate(
        tool_name,
        is_read_only=tool.is_read_only(parsed_input),
        file_path=_file_path,
        command=_command,
    )
    if not decision.allowed:
        if decision.requires_confirmation and context.permission_prompt is not None:
            # 需要用户确认
            log.debug("permission prompt for %s: %s", tool_name, decision.reason)
            if context.hook_executor is not None:
                await context.hook_executor.execute(
                    HookEvent.NOTIFICATION,
                    {
                        "event": HookEvent.NOTIFICATION.value,
                        "notification_type": "permission_prompt",
                        "tool_name": tool_name,
                        "reason": decision.reason,
                    },
                )
            confirmed = await context.permission_prompt(tool_name, decision.reason)
            if not confirmed:
                log.debug("permission denied by user for %s", tool_name)
                return ToolResultBlock(
                    tool_use_id=tool_use_id,
                    content=decision.reason or f"Permission denied for {tool_name}",
                    is_error=True,
                )
        else:
            # 直接拒绝
            log.debug("permission blocked for %s: %s", tool_name, decision.reason)
            return ToolResultBlock(
                tool_use_id=tool_use_id,
                content=decision.reason or f"Permission denied for {tool_name}",
                is_error=True,
            )

    # 执行工具
    log.debug("executing %s ...", tool_name)
    t0 = time.monotonic()
    result = await tool.execute(
        parsed_input,
        ToolExecutionContext(
            cwd=context.cwd,
            metadata={
                "tool_registry": context.tool_registry,
                "ask_user_prompt": context.ask_user_prompt,
                **(context.tool_metadata or {}),
            },
            hook_executor=context.hook_executor,
        ),
    )
    elapsed = time.monotonic() - t0
    log.debug("executed %s in %.2fs err=%s output_len=%d",
              tool_name, elapsed, result.is_error, len(result.output or ""))

    # 输出分流
    inline_output, artifact_path = _offload_tool_output_if_needed(
        tool_name=tool_name,
        tool_use_id=tool_use_id,
        output=result.output,
    )
    if artifact_path is not None:
        _remember_active_artifact(context.tool_metadata, str(artifact_path))

    # 构建结果
    tool_result = ToolResultBlock(
        tool_use_id=tool_use_id,
        content=inline_output,
        is_error=result.is_error,
    )

    # 记录元数据
    _record_tool_carryover(
        context,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_result.content,
        tool_result_metadata=result.metadata,
        is_error=tool_result.is_error,
        resolved_file_path=_file_path,
    )

    # 后置Hook
    if context.hook_executor is not None:
        await context.hook_executor.execute(
            HookEvent.POST_TOOL_USE,
            {
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_output": tool_result.content,
                "tool_is_error": tool_result.is_error,
                "event": HookEvent.POST_TOOL_USE.value,
            },
        )

    return tool_result


# =============================================================================
# 权限检查辅助函数
# =============================================================================

def _resolve_permission_file_path(
    cwd: Path,
    raw_input: dict[str, object],
    parsed_input: object,
) -> str | None:
    """
    =============================================================================
    函数文档: _resolve_permission_file_path - 解析权限检查的文件路径

    参数说明:
        cwd: 当前工作目录
        raw_input: 原始输入字典
        parsed_input: 解析后的输入对象

    返回值:
        str | None - 解析后的绝对路径

    作用说明:
        从工具输入中提取文件路径，用于权限检查。

    为什么需要解析路径:
        权限检查需要知道操作的文件是什么。
        但不同工具使用不同的参数名：
        - read_file, write_file -> file_path
        - glob, grep -> path 或 root
        - mkdir -> path

    实现逻辑:
        1. 先检查raw_input字典中的常见键
        2. 再检查parsed_input对象的属性
        3. 相对路径转换为绝对路径（基于cwd）
        4. 支持~用户目录展开
    """
    # 从字典中查找
    for key in ("file_path", "path", "root"):
        value = raw_input.get(key)
        if isinstance(value, str) and value.strip():
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = cwd / path
            return str(path.resolve())

    # 从对象属性中查找
    for attr in ("file_path", "path", "root"):
        value = getattr(parsed_input, attr, None)
        if isinstance(value, str) and value.strip():
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = cwd / path
            return str(path.resolve())

    return None


def _extract_permission_command(
    raw_input: dict[str, object],
    parsed_input: object,
) -> str | None:
    """
    =============================================================================
    函数文档: _extract_permission_command - 提取命令参数

    作用说明:
        从工具输入中提取bash命令，用于权限检查。
        bash工具需要特殊处理，因为命令内容影响权限级别。
    """
    value = raw_input.get("command")
    if isinstance(value, str) and value.strip():
        return value

    value = getattr(parsed_input, "command", None)
    if isinstance(value, str) and value.strip():
        return value

    return None



