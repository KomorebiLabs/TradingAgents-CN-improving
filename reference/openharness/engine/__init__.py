"""
模块文档: __init__.py - 引擎模块导出

================================================================================
特殊Python语法说明:
1. TYPE_CHECKING:
   仅在类型检查阶段导入，避免运行时循环导入。
   typing.TYPE_CHECKING 在运行时应为False，在类型检查时为True。

2. __getattr__ 延迟导入:
   这是Python的模块级__getattr__特性（Python 3.7+）。
   当访问模块中不存在的属性时，会调用此函数。
   用于实现延迟导入，优化启动性能。

3. if TYPE_CHECKING块内导入:
   这些导入仅在类型检查器（如mypy、pyright）运行时生效，
   实际代码中不会执行，节省运行时开销。

4. 字符串类型注解 (PEP 563):
   from __future__ import annotations 使所有类型注解延迟求值，
   避免循环引用时的ImportError。
================================================================================

功能说明:
    本模块作为engine包的公共接口，定义了对外导出的类型和类。
    通过延迟导入机制，客户端代码可以从这里导入而不触发底层模块的立即加载。

为什么使用延迟导入:
    openharness.engine 包含多个较大的模块（query.py、query_engine.py等），
    全部立即导入会拖慢启动时间。通过__getattr__实现按需加载。

使用示例:
    # 客户端代码可以这样导入
    from openharness.engine import (
        ConversationMessage,
        TextBlock,
        QueryEngine,
        StreamEvent,
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    # 仅类型检查时导入，这些类型用于类型注解
    from openharness.engine.messages import (
        ConversationMessage,
        ImageBlock,
        TextBlock,
        ToolResultBlock,
        ToolUseBlock,
    )
    from openharness.engine.query_engine import QueryEngine
    from openharness.engine.stream_events import (
        AssistantTextDelta,
        AssistantTurnComplete,
        ToolExecutionCompleted,
        ToolExecutionStarted,
    )


# =============================================================================
# 模块级公共API定义
# =============================================================================

# __all__ 定义了 from openharness.engine import * 时会导入的内容
# 但由于本模块使用__getattr__延迟导入，import * 不会触发真正的导入
__all__ = [
    "AssistantTextDelta",
    "AssistantTurnComplete",
    "ConversationMessage",
    "ImageBlock",
    "QueryEngine",
    "TextBlock",
    "ToolExecutionCompleted",
    "ToolExecutionStarted",
    "ToolResultBlock",
    "ToolUseBlock",
]


# =============================================================================
# __getattr__ 延迟导入实现
# =============================================================================

def __getattr__(name: str):
    """
    =============================================================================
    函数文档: __getattr__ - 模块级属性访问拦截

    参数说明:
        name: 访问的属性名称

    返回值:
        动态导入的类或对象

    作用说明:
        这是Python 3.7+引入的模块级__getattr__特性。
        当代码访问本模块中不存在的属性时（如openharness.engine.QueryEngine），
        Python会调用此函数。

    实现逻辑:
        1. 检查属性名是否在预定义列表中
        2. 如果是，执行真正的模块导入
        3. 返回导入的对象
        4. 如果属性不存在，抛出AttributeError

    为什么这样做:
        # 传统方式（立即导入）
        from openharness.engine.messages import ConversationMessage
        # 问题：每次import openharness.engine都会加载messages.py

        # 延迟导入方式（__getattr__）
        from openharness.engine import ConversationMessage
        # 优点：只在实际使用时才导入messages.py

    好处:
        1. 加快模块初始化速度
        2. 减少内存占用（未使用的模块不加载）
        3. 解决循环导入问题
    =============================================================================
    """

    # 消息相关的类型 - 统一从messages模块导入
    if name in {"ConversationMessage", "ImageBlock", "TextBlock", "ToolResultBlock", "ToolUseBlock"}:
        from openharness.engine.messages import (
            ConversationMessage,
            ImageBlock,
            TextBlock,
            ToolResultBlock,
            ToolUseBlock,
        )

        return {
            "ConversationMessage": ConversationMessage,
            "ImageBlock": ImageBlock,
            "TextBlock": TextBlock,
            "ToolResultBlock": ToolResultBlock,
            "ToolUseBlock": ToolUseBlock,
        }[name]

    # QueryEngine - 从query_engine模块导入
    if name == "QueryEngine":
        from openharness.engine.query_engine import QueryEngine

        return QueryEngine

    # 事件类型 - 从stream_events模块导入
    if name in {
        "AssistantTextDelta",
        "AssistantTurnComplete",
        "ToolExecutionCompleted",
        "ToolExecutionStarted",
    }:
        from openharness.engine.stream_events import (
            AssistantTextDelta,
            AssistantTurnComplete,
            ToolExecutionCompleted,
            ToolExecutionStarted,
        )

        return {
            "AssistantTextDelta": AssistantTextDelta,
            "AssistantTurnComplete": AssistantTurnComplete,
            "ToolExecutionCompleted": ToolExecutionCompleted,
            "ToolExecutionStarted": ToolExecutionStarted,
        }[name]

    # 属性不存在 - 抛出标准AttributeError
    raise AttributeError(name)
