"""
模块文档: loader.py - 钩子注册与加载

================================================================================
特殊Python语法说明:
1. defaultdict(list):
   当访问不存在的键时，自动创建默认值（这里是空列表）。
   简化了按事件类型分组存储钩子的逻辑。

2. from collections import defaultdict:
   defaultdict是dict的子类，在__getitem__被访问但不存在的键时，
   会调用工厂函数生成默认值，而不是抛出KeyError。

3. getattr() with None default:
   getattr(hook, "matcher", None) 安全获取属性，
   如果属性不存在返回None，避免AttributeError。
================================================================================

功能说明:
    负责钩子的注册、存储和加载。
    HookRegistry按事件类型组织钩子，
    load_hook_registry从配置中加载钩子定义。
"""

from __future__ import annotations

from collections import defaultdict
from openharness.hooks.events import HookEvent
from openharness.hooks.schemas import HookDefinition


class HookRegistry:
    """
    =============================================================================
    类文档: HookRegistry - 钩子注册表

    作用说明:
        内存中的钩子存储结构，按事件类型分组管理所有已注册的钩子。
        当事件触发时，从这里获取需要执行的钩子列表。

    为什么需要按事件分组:
        1. 高效查找：知道每个事件对应哪些钩子
        2. 避免遍历：不需要检查每个钩子是否响应某个事件
        3. 清晰组织：天然按事件类型分类
    =============================================================================
    """

    def __init__(self) -> None:
        """
        初始化说明:
            创建空的钩子字典。
            defaultdict(list) 确保即使事件没有钩子也不会报错。
        """
        self._hooks: dict[HookEvent, list[HookDefinition]] = defaultdict(list)

    def register(self, event: HookEvent, hook: HookDefinition) -> None:
        """
        =============================================================================
        方法文档: register - 注册钩子

        参数说明:
            event: 钩子响应的事件类型
            hook: 钩子定义对象

        实现逻辑:
            简单地将钩子追加到对应事件类型的列表末尾。
            defaultdict会自动创建列表如果不存在。
        =============================================================================
        """
        self._hooks[event].append(hook)

    def get(self, event: HookEvent) -> list[HookDefinition]:
        """
        =============================================================================
        方法文档: get - 获取事件的钩子

        参数说明:
            event: 事件类型

        返回值:
            list[HookDefinition] - 钩子列表的副本（防止外部修改）

        为什么返回副本:
            防止调用方修改列表内容影响内部状态。
        =============================================================================
        """
        return list(self._hooks.get(event, []))

    def summary(self) -> str:
        """
        =============================================================================
        方法文档: summary - 生成人类可读的钩子摘要

        返回值:
            str - 格式化的问题字符串

        用途:
            用于调试和显示当前注册的钩子配置。

        输出示例:
            pre_tool_use:
              - command matcher=bash: /path/to/hook.sh
              - prompt matcher=*: Security check
        =============================================================================
        """
        lines: list[str] = []
        for event in HookEvent:
            hooks = self.get(event)
            if not hooks:
                continue
            lines.append(f"{event.value}:")
            for hook in hooks:
                matcher = getattr(hook, "matcher", None)
                # 提取钩子的标识信息（command/prompt/url）
                detail = getattr(hook, "command", None) or getattr(hook, "prompt", None) or getattr(hook, "url", None) or ""
                suffix = f" matcher={matcher}" if matcher else ""
                lines.append(f"  - {hook.type}{suffix}: {detail}")
        return "\n".join(lines)


def load_hook_registry(settings, plugins=None) -> HookRegistry:
    """
    =============================================================================
    函数文档: load_hook_registry - 从配置加载钩子

    参数说明:
        settings: 配置对象，包含hooks字典
        plugins: 可选的插件列表，每个插件可能有hooks

    返回值:
        HookRegistry - 填充好的钩子注册表

    作用说明:
        扫描配置和插件，注册所有定义的钩子到注册表中。

    配置格式期望:
        settings.hooks = {
            "pre_tool_use": [
                {"type": "command", "command": "/path/to/hook.sh"},
                {"type": "prompt", "prompt": "Validate: $ARGUMENTS"},
            ],
            ...
        }

    为什么支持插件:
        允许通过插件系统扩展钩子，无需修改主配置。

    加载顺序:
        1. 从主配置加载
        2. 从每个启用的插件加载
        3. 后续加载的同名事件钩子会追加到列表中
    =============================================================================
    """
    registry = HookRegistry()
    
    # 从主配置加载
    for raw_event, hooks in settings.hooks.items():
        try:
            event = HookEvent(raw_event)
        except ValueError:
            # 跳过无效的事件名
            continue
        for hook in hooks:
            registry.register(event, hook)
    
    # 从插件加载
    for plugin in plugins or []:
        if not plugin.enabled:
            continue
        for raw_event, hooks in plugin.hooks.items():
            try:
                event = HookEvent(raw_event)
            except ValueError:
                continue
            for hook in hooks:
                registry.register(event, hook)
    
    return registry
