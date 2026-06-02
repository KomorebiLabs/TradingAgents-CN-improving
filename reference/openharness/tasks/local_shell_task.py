"""
模块文档: local_shell_task.py - 本地Shell任务门面

================================================================================
功能说明:
    提供异步启动本地Shell命令的便捷函数。
    封装了TaskManager的create_shell_task方法。
"""

from __future__ import annotations

from pathlib import Path

from openharness.tasks.manager import get_task_manager
from openharness.tasks.types import TaskRecord


async def spawn_shell_task(command: str, description: str, cwd: str | Path) -> TaskRecord:
    """
    =============================================================================
    函数文档: spawn_shell_task - 启动Shell任务

    参数说明:
        command: 要执行的Shell命令
        description: 任务描述
        cwd: 工作目录

    返回值:
        TaskRecord: 创建的任务记录

    作用说明:
        在后台启动一个Shell命令。
        任务会异步执行，输出被收集到日志文件。

    示例:
        task = await spawn_shell_task(
            command="python -m pytest tests/",
            description="运行测试",
            cwd="/path/to/project",
        )
    """
    return await get_task_manager().create_shell_task(
        command=command,
        description=description,
        cwd=cwd,
    )
