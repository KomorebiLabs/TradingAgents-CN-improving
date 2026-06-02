"""
模块文档: types.py - 钩子结果类型定义

================================================================================
特殊Python语法说明:
1. @dataclass(frozen=True):
   不可变数据类，所有字段在创建后不可修改。
   用于确保结果对象在多线程环境下是安全的。

2. field(default_factory=dict):
   dataclasses模块的字段选项，default_factory是工厂函数，
   每次创建实例时调用它生成默认值（这里是空字典）。
================================================================================

功能说明:
    定义了钩子系统运行时使用的返回类型。
    HookResult表示单个钩子的执行结果，
    AggregatedHookResult表示一个事件触发所有钩子后的聚合结果。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HookResult:
    """
    =============================================================================
    类文档: HookResult - 单个钩子执行结果

    作用说明:
        封装单个钩子执行后的状态和输出信息。
        引擎根据这个结果决定如何继续处理。

    字段说明:
        hook_type: 钩子类型标识（"command", "prompt", "http", "agent"）
        success: 钩子是否执行成功
        output: 钩子的输出内容
        blocked: 是否阻止后续操作（当success=False且block_on_failure=True时为True）
        reason: 失败原因或输出摘要
        metadata: 额外的元数据（如HTTP状态码、进程返回码等）

    为什么blocked字段很重要:
        PRE_TOOL_USE钩子可以返回blocked=True来阻止工具执行。
        这是一种安全控制机制。
    =============================================================================
    """
    hook_type: str
    success: bool
    output: str = ""
    blocked: bool = False
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AggregatedHookResult:
    """
    =============================================================================
    类文档: AggregatedHookResult - 聚合钩子结果

    作用说明:
        当一个事件触发多个钩子时，需要聚合所有钩子的结果。
        这个类提供统一的接口来检查是否有任何钩子阻止了操作。

    为什么需要聚合:
        1. 一个事件可能触发多个钩子
        2. 每个钩子独立执行
        3. 需要判断是否应该阻止后续操作

    设计模式:
        使用属性方法（@property）动态计算聚合结果，
        而不是存储中间状态，保持数据不可变性。
    =============================================================================
    """
    results: list[HookResult] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        """
        =============================================================================
        属性文档: blocked - 是否有任何钩子阻止了操作

        返回值:
            bool - True表示至少有一个钩子阻止了操作

        实现逻辑:
            检查results列表中是否有任何HookResult的blocked=True。
            any()在找到第一个True时会短路返回，性能高效。
        =============================================================================
        """
        return any(result.blocked for result in self.results)

    @property
    def reason(self) -> str:
        """
        =============================================================================
        属性文档: reason - 获取第一个阻止的原因

        返回值:
            str - 第一个blocked=True的钩子的reason或output

        实现逻辑:
            遍历results列表，返回第一个blocked=True的钩子的reason。
            如果没有阻止，返回空字符串。
        =============================================================================
        """
        for result in self.results:
            if result.blocked:
                return result.reason or result.output
        return ""
