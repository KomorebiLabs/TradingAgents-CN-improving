"""
模块文档: local_agent_task.py - 本地Agent任务门面

================================================================================
功能说明:
    提供异步启动本地Agent子进程的便捷函数。
    封装了TaskManager的create_agent_task方法。
"""

from __future__ import annotations

from pathlib import Path

from openharness.tasks.manager import get_task_manager
from openharness.tasks.types import TaskRecord


async def spawn_local_agent_task(
    *,
    prompt: str,
    description: str,
    cwd: str | Path,
    model: str | None = None,
    api_key: str | None = None,
    command: str | None = None,
) -> TaskRecord:
    """
    =============================================================================
    函数文档: spawn_local_agent_task - 启动本地Agent任务

    参数说明:
        prompt: Agent的初始提示词
        description: 任务描述
        cwd: 工作目录
        model: 可选的模型名称
        api_key: 可选的API密钥
        command: 可选的命令覆盖

    返回值:
        TaskRecord: 创建的任务记录

    作用说明:
        在子进程中启动一个OpenHarness Agent实例。
        Agent会执行prompt中指定的任务。

    示例:
        task = await spawn_local_agent_task(
            prompt="帮我写一个排序算法",
            description="编写排序算法",
            cwd="/path/to/project",
        )
    """
    return await get_task_manager().create_agent_task(
        prompt=prompt,
        description=description,
        cwd=cwd,
        model=model,
        api_key=api_key,
        command=command,
    )
