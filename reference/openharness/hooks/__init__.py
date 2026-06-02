"""
模块文档: hooks/__init__.py - 钩子模块导出

================================================================================
特殊Python语法说明:
1. TYPE_CHECKING:
   仅类型检查时导入，避免循环依赖。

2. __getattr__ 延迟导入:
   Python 3.7+模块级延迟加载机制。

3. __all__ 定义公共API:
   明确列出模块的公共接口。
================================================================================

功能说明:
    作为hooks包的公共接口，提供钩子系统的所有关键类型和函数。
    使用延迟导入优化启动性能。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from openharness.hooks.events import HookEvent
    from openharness.hooks.executor import HookExecutionContext, HookExecutor
    from openharness.hooks.loader import HookRegistry
    from openharness.hooks.types import AggregatedHookResult, HookResult

__all__ = [
    "AggregatedHookResult",
    "HookEvent",
    "HookExecutionContext",
    "HookExecutor",
    "HookRegistry",
    "HookResult",
    "load_hook_registry",
]


def __getattr__(name: str):
    """
    =============================================================================
    函数文档: __getattr__ - 延迟导入实现

    按类别分组导入，避免单个大字典。
    每个导入块处理一组相关的类型/函数。
    =============================================================================
    """
    # 事件类型
    if name == "HookEvent":
        from openharness.hooks.events import HookEvent
        return HookEvent
    
    # 执行器相关
    if name in {"HookExecutionContext", "HookExecutor"}:
        from openharness.hooks.executor import HookExecutionContext, HookExecutor
        return {
            "HookExecutionContext": HookExecutionContext,
            "HookExecutor": HookExecutor,
        }[name]
    
    # 注册和加载
    if name in {"HookRegistry", "load_hook_registry"}:
        from openharness.hooks.loader import HookRegistry, load_hook_registry
        return {
            "HookRegistry": HookRegistry,
            "load_hook_registry": load_hook_registry,
        }[name]
    
    # 结果类型
    if name in {"AggregatedHookResult", "HookResult"}:
        from openharness.hooks.types import AggregatedHookResult, HookResult
        return {
            "AggregatedHookResult": AggregatedHookResult,
            "HookResult": HookResult,
        }[name]

    raise AttributeError(name)
