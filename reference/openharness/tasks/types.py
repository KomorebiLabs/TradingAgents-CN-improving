"""
模块文档: types.py - 任务数据类型定义

================================================================================
特殊Python语法说明:
1. Literal类型:
   限制变量只能是指定的几个字符串值之一。
   
2. @dataclass:
   数据类，自动生成__init__、__repr__等方法。

3. field(default_factory=dict):
   每次创建实例时生成新的字典，避免共享引用问题。
================================================================================

功能说明:
    定义了任务系统的核心数据类型。
    任务是在后台运行的异步工作单元。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


# 类型别名 - 使代码更简洁
TaskType = Literal["local_bash", "local_agent", "remote_agent", "in_process_teammate"]
TaskStatus = Literal["pending", "running", "completed", "failed", "killed"]


@dataclass
class TaskRecord:
    """
    =============================================================================
    类文档: TaskRecord - 任务记录

    作用说明:
        表示一个运行时后台任务的完整记录。
        包含任务的所有状态信息和元数据。

    为什么需要任务记录:
        1. 状态追踪：知道任务当前处于什么状态
        2. 输出管理：保存任务输出到文件
        3. 生命周期：记录创建、启动、结束时间
        4. 元数据：存储任务相关的信息

    字段说明:
        id: 任务唯一标识符（如 "a1b2c3d4"）
        type: 任务类型
            - local_bash: 本地Shell命令
            - local_agent: 本地Agent进程
            - remote_agent: 远程Agent
            - in_process_teammate: 进程内队友
        status: 当前状态
            - pending: 等待中
            - running: 运行中
            - completed: 已完成
            - failed: 失败
            - killed: 被终止
        description: 任务描述（用于显示）
        cwd: 任务运行的工作目录
        output_file: 输出日志文件路径
        command: 要执行的命令（bash任务）
        prompt: Agent提示词（agent任务）
        created_at: 创建时间戳
        started_at: 开始执行时间戳
        ended_at: 结束时间戳
        return_code: 进程退出码
        metadata: 额外的键值对元数据
    =============================================================================
    """
    id: str
    type: TaskType
    status: TaskStatus
    description: str
    cwd: str
    output_file: Path
    command: str | None = None
    prompt: str | None = None
    created_at: float = 0.0
    started_at: float | None = None
    ended_at: float | None = None
    return_code: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)
