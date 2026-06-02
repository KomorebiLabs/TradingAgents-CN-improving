"""
模块文档: permissions/__init__.py - 权限模块导出

================================================================================
特殊Python语法说明:
1. TYPE_CHECKING:
   仅在类型检查阶段导入，用于类型注解，避免循环导入。
   在运行时，TYPE_CHECKING块内的导入不会执行。

2. __getattr__ 延迟导入:
   Python 3.7+特性，当访问模块属性时调用此函数。
   用于延迟加载子模块，优化启动性能。

3. if name in {...}:
   使用字典映射实现条件导入，避免多个if-elif链。
================================================================================

功能说明:
    作为permissions包的公共接口，提供PermissionChecker、PermissionDecision
    和PermissionMode的延迟导入。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from openharness.permissions.checker import PermissionChecker, PermissionDecision
    from openharness.permissions.modes import PermissionMode

__all__ = ["PermissionChecker", "PermissionDecision", "PermissionMode"]


def __getattr__(name: str):
    """
    =============================================================================
    函数文档: __getattr__ - 模块级属性访问拦截

    参数说明:
        name: 访问的属性名

    返回值:
        动态导入的类或对象

    作用说明:
        实现延迟导入模式。当客户端代码访问：
        from openharness.permissions import PermissionChecker
        
        Python会调用此函数，从checker模块导入真正的类。
        这样避免在import openharness.permissions时就加载所有子模块。

    为什么需要延迟导入:
        1. 加快模块初始化速度
        2. 减少不必要的依赖加载
        3. 避免循环导入问题
    =============================================================================
    """
    # 权限检查器相关类型
    if name in {"PermissionChecker", "PermissionDecision"}:
        from openharness.permissions.checker import PermissionChecker, PermissionDecision

        return {
            "PermissionChecker": PermissionChecker,
            "PermissionDecision": PermissionDecision,
        }[name]
    
    # 权限模式枚举
    if name == "PermissionMode":
        from openharness.permissions.modes import PermissionMode

        return PermissionMode

    # 属性不存在
    raise AttributeError(name)
