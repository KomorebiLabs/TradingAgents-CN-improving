"""
模块文档: hot_reload.py - 钩子热重载器

================================================================================
特殊Python语法说明:
1. Path.stat().st_mtime_ns:
   stat()返回文件状态信息，st_mtime_ns是纳秒级修改时间戳。
   用于精确检测文件是否被修改。

2. os.PathLike协议:
   Path对象实现了__fspath__方法，可以与字符串路径混用。
================================================================================

功能说明:
    监视配置文件的变化，在检测到变化时自动重新加载钩子。
    这允许用户修改钩子配置后无需重启程序即可生效。
"""

from __future__ import annotations

from pathlib import Path

from openharness.config import load_settings
from openharness.hooks.loader import HookRegistry, load_hook_registry


class HookReloader:
    """
    =============================================================================
    类文档: HookReloader - 钩子热重载器

    作用说明:
        监视设置文件的变化，自动重新加载钩子配置。
        实现了"热重载"功能，配置修改即时生效。

    为什么需要热重载:
        1. 开发体验：修改钩子配置后立即生效，无需重启
        2. 生产环境：可以在不中断服务的情况下更新钩子
        3. 调试：快速测试不同的钩子配置

    使用方式:
        reloader = HookReloader(settings_path)
        # 在需要获取最新钩子时调用
        registry = reloader.current_registry()
    =============================================================================
    """

    def __init__(self, settings_path: Path) -> None:
        """
        初始化说明:
            设置监视的文件路径，初始化空的注册表。
            _last_mtime_ns = -1 确保首次调用必定重新加载。
        """
        self._settings_path = settings_path
        self._last_mtime_ns = -1  # 确保首次必定重新加载
        self._registry = HookRegistry()

    def current_registry(self) -> HookRegistry:
        """
        =============================================================================
        方法文档: current_registry - 获取当前（最新）的注册表

        返回值:
            HookRegistry - 当前有效的钩子注册表

        实现逻辑:
            1. 检查文件是否存在（不存在则返回空注册表）
            2. 比较文件修改时间（纳秒精度）
            3. 如果时间变化，重新加载配置
            4. 返回最新的注册表

        为什么比较mtime:
            当文件被修改时，mtime会更新。
            通过比较mtime可以知道文件是否被修改。
        =============================================================================
        """
        try:
            stat = self._settings_path.stat()
        except FileNotFoundError:
            # 文件不存在，重置状态
            self._registry = HookRegistry()
            self._last_mtime_ns = -1
            return self._registry

        # 比较纳秒级修改时间
        if stat.st_mtime_ns != self._last_mtime_ns:
            self._last_mtime_ns = stat.st_mtime_ns
            self._registry = load_hook_registry(load_settings(self._settings_path))
        return self._registry
