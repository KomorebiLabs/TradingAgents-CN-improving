"""
模块文档: stream_events.py - 流式事件定义

================================================================================
特殊Python语法说明:
1. @dataclass(frozen=True):
   frozen=True 使数据类实例不可变，所有字段在创建后无法修改。
   这是为了确保事件对象在多线程环境下是线程安全的，不会被意外修改。
   注意：不可变对象可以作为dict的key或放入set中。

2. Union类型简写 "|" 运算符 (Python 3.10+):
   StreamEvent = AssistantTextDelta | AssistantTurnComplete | ...
   等价于 Union[AssistantTextDelta, AssistantTurnComplete, ...]

3. Literal类型字面量:
   用于限制字符串只能是特定的字面量值，如 Literal["auto", "manual", "reactive"]
   确保参数只能是预定义的几 个值之一。
================================================================================

功能说明:
    这个模块定义了查询引擎在执行过程中产生的各种事件类型。
    这些事件通过异步迭代器(AsyncIterator)逐个产出，前端可以实时监听这些事件
    来更新UI显示，如显示AI正在输入、工具开始执行、执行结果等。

为什么需要事件系统:
    1. 实时反馈：AI生成文本时逐字显示，而不是等待完整响应
    2. 进度感知：用户能看到AI正在执行什么操作
    3. 异步解耦：引擎和UI分离，通过事件通信
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from openharness.api.usage import UsageSnapshot
from openharness.engine.messages import ConversationMessage


# =============================================================================
# 事件类型定义
# =============================================================================

@dataclass(frozen=True)
class AssistantTextDelta:
    """
    =============================================================================
    类文档: AssistantTextDelta - AI文本增量事件

    数据结构说明:
        表示AI回复文本的增量（delta）部分。每次AI输出新的文本片段时，
        都会产生一个新的Delta事件。

    字段说明:
        - text: 新增的文本片段（非完整句子，可能是几个字或几个词）

    为什么叫"增量"而不是"完整文本":
        1. 实时性：收到一个字符就发一个事件，客户端立即显示
        2. 流量优化：不需要等完整句子，延迟更低
        3. 打字机效果：实现逐字显示的视觉效果

    使用场景:
        前端监听此事件，将text累加到显示区域，实现实时打字效果。
    =============================================================================
    """
    text: str


@dataclass(frozen=True)
class AssistantTurnComplete:
    """
    =============================================================================
    类文档: AssistantTurnComplete - AI回合完成事件

    数据结构说明:
        当AI完成一次完整的回复（可能包含多个tool_use调用）时产生。
        包含完整的回复消息和本次API调用的使用量统计。

    字段说明:
        - message: ConversationMessage - 完整的助手回复消息
        - usage: UsageSnapshot - 本次调用的token消耗统计

    触发时机:
        - AI回复完成且没有工具调用请求时
        - AI回复完成且所有工具调用都有结果后

    为什么需要这个事件:
        通知前端这一轮对话结束，可以进行一些收尾操作，
        如保存会话、显示完成状态、记录使用量等。
    =============================================================================
    """
    message: ConversationMessage
    usage: UsageSnapshot


@dataclass(frozen=True)
class ToolExecutionStarted:
    """
    =============================================================================
    类文档: ToolExecutionStarted - 工具开始执行事件

    数据结构说明:
        在执行工具之前发出，通知前端即将执行某个工具。
        包含工具名称和输入参数，但不包含执行结果。

    字段说明:
        - tool_name: 要执行的工具名称
        - tool_input: 工具的输入参数

    为什么需要这个事件:
        1. UI反馈：告诉用户"AI正在使用XX工具"
        2. 参数展示：让用户能看到AI给工具传递了什么参数
        3. 日志记录：用于审计和调试

    典型使用:
        前端显示 "正在读取文件...", "正在执行bash命令..." 等状态。
    =============================================================================
    """
    tool_name: str
    tool_input: dict[str, Any]


@dataclass(frozen=True)
class ToolExecutionCompleted:
    """
    =============================================================================
    类文档: ToolExecutionCompleted - 工具执行完成事件

    数据结构说明:
        工具执行完成后产生，包含执行结果和错误状态。

    字段说明:
        - tool_name: 执行的工具名称
        - output: 工具的输出内容（字符串格式）
        - is_error: 是否执行出错的标志

    为什么需要这个事件:
        1. 结果展示：将工具输出显示给用户
        2. 错误处理：is_error标志让用户知道执行失败
        3. 流程继续：触发下一轮AI推理

    注意事项:
        如果输出过长，可能会被截断并保存到文件（通过_offload_tool_output_if_needed），
        output中会包含指向完整输出的提示信息。
    =============================================================================
    """
    tool_name: str
    output: str
    is_error: bool = False


@dataclass(frozen=True)
class ErrorEvent:
    """
    =============================================================================
    类文档: ErrorEvent - 错误事件

    数据结构说明:
        当发生不应该发生的错误时产生，如API调用失败、权限被拒绝等。

    字段说明:
        - message: 错误描述信息
        - recoverable: 是否可恢复的错误，默认True

    recoverable字段的作用:
        - True: 可能是暂时的（如网络抖动），可以重试
        - False: 严重错误（如认证失败），不建议重试

    为什么需要这个事件:
        统一的错误传播机制，让UI层能够一致地处理和显示各种错误。
    =============================================================================
    """
    message: str
    recoverable: bool = True


@dataclass(frozen=True)
class StatusEvent:
    """
    =============================================================================
    类文档: StatusEvent - 状态消息事件

    数据结构说明:
        用于传达系统级的状态信息，不是用户和AI之间的对话内容。

    字段说明:
        - message: 状态消息文本

    使用场景:
        - "正在压缩对话历史以节省token..."
        - "正在转换图片为文本..."
        - "请求失败，3秒后重试..."

    为什么需要这个事件:
        让用户了解系统正在做什么后台操作，提高透明度。
        不同于对话内容，这些是系统内部的状态更新。
    =============================================================================
    """
    message: str


@dataclass(frozen=True)
class CompactProgressEvent:
    """
    =============================================================================
    类文档: CompactProgressEvent - 对话压缩进度事件

    数据结构说明:
        当对话历史过长需要压缩（总结）时，产生一系列进度事件来报告压缩过程。

    字段说明:
        - phase: 当前阶段，是一个枚举值
        - trigger: 触发压缩的原因 ("auto"/"manual"/"reactive")
        - message: 可选的阶段描述
        - attempt: 重试次数（如果有）
        - checkpoint: 检查点标识
        - metadata: 额外的元数据

    phase枚举值详解:
        - "hooks_start": 开始执行hook
        - "context_collapse_start/end": 上下文折叠开始/结束
        - "session_memory_start/end": 会话记忆处理开始/结束
        - "compact_start": 开始执行压缩（LLM总结）
        - "compact_retry": 重试压缩
        - "compact_end": 压缩完成
        - "compact_failed": 压缩失败

    trigger值说明:
        - "auto": 自动触发（token接近阈值）
        - "manual": 手动触发（用户请求）
        - "reactive": 被动触发（收到"prompt too long"错误后）

    为什么需要这个事件:
        压缩操作可能耗时较长，需要让用户知道进度，
        而不是让界面看起来像卡住了。
    =============================================================================
    """
    phase: Literal[
        "hooks_start",
        "context_collapse_start",
        "context_collapse_end",
        "session_memory_start",
        "session_memory_end",
        "compact_start",
        "compact_retry",
        "compact_end",
        "compact_failed",
    ]
    trigger: Literal["auto", "manual", "reactive"]
    message: str | None = None
    attempt: int | None = None
    checkpoint: str | None = None
    metadata: dict[str, Any] | None = None


# =============================================================================
# 联合类型别名
# =============================================================================

# StreamEvent类型别名：包含所有可能的事件类型
# 使用Union语法让类型检查器知道这些类型都是合法的返回值
# 前端代码可以根据 isinstance(event, AssistantTextDelta) 来区分不同事件
StreamEvent = (
    AssistantTextDelta
    | AssistantTurnComplete
    | ToolExecutionStarted
    | ToolExecutionCompleted
    | ErrorEvent
    | StatusEvent
    | CompactProgressEvent
)
