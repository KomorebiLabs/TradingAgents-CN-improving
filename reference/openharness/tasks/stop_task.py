"""
模块文档: stop_task.py - 停止任务帮助函数

================================================================================
功能说明:
    提供停止运行中任务的便捷函数。
    封装了TaskManager的stop_task方法。
"""

from __future__ import annotations

from openharness.tasks.manager import get_task_manager
from openharness.tasks.types import TaskRecord


async def stop_task(task_id: str) -> TaskRecord:
    """
    =============================================================================
    函数文档: stop_task - 停止任务

    参数说明:
        task_id: 要停止的任务ID

    返回值:
        TaskRecord: 更新后的任务记录

    作用说明:
        发送终止信号给指定的任务。
        任务会立即停止运行。

    异常:
        ValueError - 如果任务不存在或不在运行中

    示例:
        task = await stop_task("a1b2c3d4")
    """
    return await get_task_manager().stop_task(task_id)
