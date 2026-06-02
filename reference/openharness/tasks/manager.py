"""
模块文档: manager.py - 后台任务管理器

================================================================================
特殊Python语法说明:
1. asyncio异步编程:
   - asyncio.subprocess: 异步子进程
   - asyncio.Lock: 异步锁
   - asyncio.create_task: 创建异步任务
   - asyncio.wait_for: 超时等待

2. dataclasses.replace:
   创建数据类的副本，可选择性覆盖某些字段。

3. json.loads/json.dumps:
   JSON序列化/反序列化。

4. subprocess.PIPE:
   子进程的标准输入/输出/错误管道。

5. Callback模式:
   使用Callable类型定义回调函数。
================================================================================

功能说明:
    管理后台运行的Shell命令和Agent进程。
    提供任务的创建、监控、停止和输出读取功能。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import time
from dataclasses import replace
from pathlib import Path
from typing import Awaitable, Callable
from uuid import uuid4

from openharness.config.paths import get_tasks_dir
from openharness.tasks.types import TaskRecord, TaskStatus, TaskType
from openharness.utils.shell import create_shell_subprocess

log = logging.getLogger(__name__)

# 重启通知消息
_TASK_RESTART_NOTICE = "[OpenHarness] Agent task restarted; prior interactive context was not preserved.\n"


# =============================================================================
# 类型别名
# =============================================================================

# 任务完成监听器回调函数类型
CompletionListener = Callable[[TaskRecord], Awaitable[None] | None]


# =============================================================================
# 工具函数
# =============================================================================

def _encode_task_worker_payload(data: str) -> bytes:
    """
    =============================================================================
    函数文档: _encode_task_worker_payload - 编码任务工作负载

    参数说明:
        data: 要发送的数据

    返回值:
        bytes: 编码后的数据（JSON行）

    作用说明:
        将数据转换为适合发送给工作进程的格式。
        
        实现逻辑:
        1. 如果已经是JSON对象且包含text字段，保持原样
        2. 如果不含换行符，直接发送
        3. 否则包装成JSON对象
    """
    stripped = data.rstrip("\n")
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict) and isinstance(payload.get("text"), str):
        framed = stripped
    elif "\n" not in stripped and "\r" not in stripped:
        framed = stripped
    else:
        framed = json.dumps({"text": stripped}, ensure_ascii=False)
    return (framed + "\n").encode("utf-8")


def _task_id(task_type: TaskType) -> str:
    """
    =============================================================================
    函数文档: _task_id - 生成任务ID

    实现:
        前缀 + 8位UUID
        b=bash, a=agent, r=remote, t=teammate
    """
    prefixes = {
        "local_bash": "b",
        "local_agent": "a",
        "remote_agent": "r",
        "in_process_teammate": "t",
    }
    return f"{prefixes[task_type]}{uuid4().hex[:8]}"


# =============================================================================
# 后台任务管理器
# =============================================================================

class BackgroundTaskManager:
    """
    =============================================================================
    类文档: BackgroundTaskManager - 后台任务管理器

    作用说明:
        管理所有后台运行的Shell命令和Agent进程。
        提供创建、监控、停止、读取输出等操作。

    为什么需要任务管理器:
        1. 资源管理：追踪所有子进程
        2. 状态追踪：知道任务当前状态
        3. 输出收集：收集并保存任务输出
        4. 生命周期：优雅地启动、停止任务

    核心数据结构:
        _tasks: 任务ID -> TaskRecord
        _processes: 任务ID -> asyncio.subprocess.Process
        _waiters: 任务ID -> asyncio.Task (监控任务)
        _output_locks: 任务ID -> asyncio.Lock (输出写入锁)
        _input_locks: 任务ID -> asyncio.Lock (输入写入锁)
        _completion_listeners: 监听器回调
    =============================================================================
    """

    def __init__(self) -> None:
        """初始化所有数据结构。"""
        self._tasks: dict[str, TaskRecord] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._waiters: dict[str, asyncio.Task[None]] = {}
        self._output_locks: dict[str, asyncio.Lock] = {}
        self._input_locks: dict[str, asyncio.Lock] = {}
        self._generations: dict[str, int] = {}
        self._completion_listeners: dict[str, CompletionListener] = {}

    async def create_shell_task(
        self,
        *,
        command: str,
        description: str,
        cwd: str | Path,
        task_type: TaskType = "local_bash",
    ) -> TaskRecord:
        """
        =============================================================================
        方法文档: create_shell_task - 创建Shell任务

        参数说明:
            command: 要执行的Shell命令
            description: 任务描述
            cwd: 工作目录
            task_type: 任务类型

        返回值:
            TaskRecord: 创建的任务记录

        实现流程:
            1. 生成唯一任务ID
            2. 创建输出文件
            3. 初始化TaskRecord
            4. 创建进程
        """
        task_id = _task_id(task_type)
        output_path = get_tasks_dir() / f"{task_id}.log"
        record = TaskRecord(
            id=task_id,
            type=task_type,
            status="running",
            description=description,
            cwd=str(Path(cwd).resolve()),
            output_file=output_path,
            command=command,
            created_at=time.time(),
            started_at=time.time(),
        )
        output_path.write_text("", encoding="utf-8")
        self._tasks[task_id] = record
        self._output_locks[task_id] = asyncio.Lock()
        self._input_locks[task_id] = asyncio.Lock()
        await self._start_process(task_id)
        return record

    async def create_agent_task(
        self,
        *,
        prompt: str,
        description: str,
        cwd: str | Path,
        task_type: TaskType = "local_agent",
        model: str | None = None,
        api_key: str | None = None,
        command: str | None = None,
    ) -> TaskRecord:
        """
        =============================================================================
        方法文档: create_agent_task - 创建Agent任务

        参数说明:
            prompt: Agent的初始提示词
            description: 任务描述
            cwd: 工作目录
            task_type: 任务类型
            model: 使用的模型
            api_key: API密钥
            command: 可选的命令覆盖

        实现说明:
            如果未提供command，根据api_key构建OpenHarness启动命令。
            创建后发送初始提示词给Agent。
        """
        if command is None:
            effective_api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not effective_api_key:
                raise ValueError(
                    "Local agent tasks require ANTHROPIC_API_KEY or an explicit command override"
                )
            cmd = ["python", "-m", "openharness", "--api-key", effective_api_key]
            if model:
                cmd.extend(["--model", model])
            command = " ".join(shlex.quote(part) for part in cmd)

        # 创建基础Shell任务
        record = await self.create_shell_task(
            command=command,
            description=description,
            cwd=cwd,
            task_type=task_type,
        )
        # 更新记录，添加prompt
        updated = replace(record, prompt=prompt)
        if task_type != "local_agent":
            updated.metadata["agent_mode"] = task_type
        self._tasks[record.id] = updated
        # 发送初始提示词
        await self.write_to_task(record.id, prompt)
        return updated

    def get_task(self, task_id: str) -> TaskRecord | None:
        """获取任务记录。"""
        return self._tasks.get(task_id)

    def list_tasks(self, *, status: TaskStatus | None = None) -> list[TaskRecord]:
        """
        =============================================================================
        方法文档: list_tasks - 列出任务

        参数说明:
            status: 可选的过滤条件

        返回值:
            list[TaskRecord] - 任务列表，按创建时间倒序
        """
        tasks = list(self._tasks.values())
        if status is not None:
            tasks = [task for task in tasks if task.status == status]
        return sorted(tasks, key=lambda item: item.created_at, reverse=True)

    def update_task(
        self,
        task_id: str,
        *,
        description: str | None = None,
        progress: int | None = None,
        status_note: str | None = None,
    ) -> TaskRecord:
        """
        =============================================================================
        方法文档: update_task - 更新任务元数据

        用途:
            更新任务的描述和进度信息，用于协调和UI显示。
        """
        task = self._require_task(task_id)
        if description is not None and description.strip():
            task.description = description.strip()
        if progress is not None:
            task.metadata["progress"] = str(progress)
        if status_note is not None:
            note = status_note.strip()
            if note:
                task.metadata["status_note"] = note
            else:
                task.metadata.pop("status_note", None)
        return task

    async def stop_task(self, task_id: str) -> TaskRecord:
        """
        =============================================================================
        方法文档: stop_task - 停止任务

        实现:
            1. 发送SIGTERM请求优雅终止
            2. 等待3秒
            3. 超时则SIGKILL强制终止
            4. 关闭stdin
        """
        task = self._require_task(task_id)
        process = self._processes.get(task_id)
        if process is None:
            if task.status in {"completed", "failed", "killed"}:
                return task
            raise ValueError(f"Task {task_id} is not running")

        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=3)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
        await _close_process_stdin(process)

        task.status = "killed"
        task.ended_at = time.time()
        return task

    async def write_to_task(self, task_id: str, data: str) -> None:
        """
        =============================================================================
        方法文档: write_to_task - 向任务写入数据

        实现:
            发送数据到任务的stdin。
            如果进程已结束，自动重启Agent任务。
        """
        task = self._require_task(task_id)
        payload = _encode_task_worker_payload(data)
        async with self._input_locks[task_id]:
            process = await self._ensure_writable_process(task)
            process.stdin.write(payload)
            try:
                await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                if task.type not in {"local_agent", "remote_agent", "in_process_teammate"}:
                    raise ValueError(f"Task {task_id} does not accept input") from None
                # 重启Agent任务
                process = await self._restart_agent_task(task)
                process.stdin.write(payload)
                await process.stdin.drain()

    def read_task_output(self, task_id: str, *, max_bytes: int = 12000) -> str:
        """
        =============================================================================
        方法文档: read_task_output - 读取任务输出

        返回值:
            str - 输出内容（截断到max_bytes）

        实现:
            读取输出文件的末尾部分。
            大文件只返回最后的max_bytes字节。
        """
        task = self._require_task(task_id)
        content = task.output_file.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_bytes:
            return content[-max_bytes:]
        return content

    def register_completion_listener(self, listener: CompletionListener) -> Callable[[], None]:
        """
        =============================================================================
        方法文档: register_completion_listener - 注册完成监听器

        返回值:
            Callable - 返回取消注册的函数

        用途:
            注册任务完成时的回调函数。
        """
        listener_id = uuid4().hex
        self._completion_listeners[listener_id] = listener

        def _unregister() -> None:
            self._completion_listeners.pop(listener_id, None)

        return _unregister

    # === 内部方法 ===

    async def _start_process(self, task_id: str) -> asyncio.subprocess.Process:
        """启动子进程。"""
        task = self._require_task(task_id)
        if task.command is None:
            raise ValueError(f"Task {task_id} does not have a command to run")

        generation = self._generations.get(task_id, 0) + 1
        self._generations[task_id] = generation
        process = await create_shell_subprocess(
            task.command,
            cwd=task.cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self._processes[task_id] = process
        self._waiters[task_id] = asyncio.create_task(
            self._watch_process(task_id, process, generation)
        )
        return process

    async def _watch_process(
        self,
        task_id: str,
        process: asyncio.subprocess.Process,
        generation: int,
    ) -> None:
        """
        监控进程执行。
        
        当进程结束时：
        1. 收集剩余输出
        2. 更新任务状态
        3. 通知监听器
        """
        # 异步收集输出
        reader = asyncio.create_task(self._copy_output(task_id, process))
        return_code = await process.wait()
        await reader
        await _close_process_stdin(process)

        # 检查generation是否过期
        current_generation = self._generations.get(task_id)
        if current_generation != generation:
            return

        # 更新任务状态
        task = self._tasks[task_id]
        task.return_code = return_code
        if task.status != "killed":
            task.status = "completed" if return_code == 0 else "failed"
        task.ended_at = time.time()
        await self._notify_completion_listeners(task)
        self._processes.pop(task_id, None)
        self._waiters.pop(task_id, None)

    async def _copy_output(self, task_id: str, process: asyncio.subprocess.Process) -> None:
        """异步复制进程输出到文件。"""
        if process.stdout is None:
            return
        while True:
            chunk = await process.stdout.read(4096)
            if not chunk:
                return
            async with self._output_locks[task_id]:
                with self._tasks[task_id].output_file.open("ab") as handle:
                    handle.write(chunk)

    def _require_task(self, task_id: str) -> TaskRecord:
        """获取任务，不存在则抛异常。"""
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"No task found with ID: {task_id}")
        return task

    async def _ensure_writable_process(self, task: TaskRecord) -> asyncio.subprocess.Process:
        """确保进程可写，不可用则重启。"""
        process = self._processes.get(task.id)
        if process is not None and process.stdin is not None and process.returncode is None:
            return process
        if task.type not in {"local_agent", "remote_agent", "in_process_teammate"}:
            raise ValueError(f"Task {task.id} does not accept input")
        return await self._restart_agent_task(task)

    async def _restart_agent_task(self, task: TaskRecord) -> asyncio.subprocess.Process:
        """重启Agent任务。"""
        if task.command is None:
            raise ValueError(f"Task {task.id} does not have a restart command")

        # 等待现有监控任务
        waiter = self._waiters.get(task.id)
        if waiter is not None and not waiter.done():
            await waiter

        # 更新元数据
        restart_count = int(task.metadata.get("restart_count", "0")) + 1
        task.metadata["restart_count"] = str(restart_count)
        task.metadata["status_note"] = "Task restarted; prior interactive context was not preserved."
        task.status = "running"
        task.started_at = time.time()
        task.ended_at = None
        task.return_code = None

        # 写入重启通知
        with task.output_file.open("ab") as handle:
            handle.write(_TASK_RESTART_NOTICE.encode("utf-8"))

        return await self._start_process(task.id)

    async def _notify_completion_listeners(self, task: TaskRecord) -> None:
        """通知所有完成监听器。"""
        snapshot = replace(task, metadata=dict(task.metadata))
        for listener_id, listener in list(self._completion_listeners.items()):
            try:
                maybe_awaitable = listener(snapshot)
                if maybe_awaitable is not None:
                    await maybe_awaitable
            except Exception:
                log.exception("Task completion listener %s failed for task %s", listener_id, task.id)

    def close(self) -> None:
        """同步关闭，清理所有进程和任务。"""
        for waiter in list(self._waiters.values()):
            waiter.cancel()
        self._waiters.clear()
        for process in list(self._processes.values()):
            stdin = process.stdin
            if stdin is not None and not stdin.is_closing():
                try:
                    stdin.close()
                except RuntimeError:
                    pass
            if process.returncode is None:
                try:
                    process.kill()
                except (ProcessLookupError, RuntimeError):
                    pass
        self._processes.clear()

    async def aclose(self) -> None:
        """异步关闭，等待所有进程和任务完全结束。"""
        processes = list(self._processes.values())
        waiters = list(self._waiters.values())
        for process in processes:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await _close_process_stdin(process)
        for process in processes:
            if process.returncode is None:
                try:
                    await process.wait()
                except ProcessLookupError:
                    pass
        if waiters:
            await asyncio.gather(*waiters, return_exceptions=True)
        self._processes.clear()
        self._waiters.clear()


# =============================================================================
# 单例管理
# =============================================================================

_DEFAULT_MANAGER: BackgroundTaskManager | None = None
_DEFAULT_MANAGER_KEY: str | None = None


def get_task_manager() -> BackgroundTaskManager:
    """
    =============================================================================
    函数文档: get_task_manager - 获取任务管理器单例

    返回值:
        BackgroundTaskManager - 全局唯一的任务管理器

    实现:
        使用tasks目录路径作为key，
        如果路径变化则重新创建管理器。
    """
    global _DEFAULT_MANAGER, _DEFAULT_MANAGER_KEY
    current_key = str(get_tasks_dir().resolve())
    if _DEFAULT_MANAGER is None or _DEFAULT_MANAGER_KEY != current_key:
        if _DEFAULT_MANAGER is not None:
            _DEFAULT_MANAGER.close()
        _DEFAULT_MANAGER = BackgroundTaskManager()
        _DEFAULT_MANAGER_KEY = current_key
    return _DEFAULT_MANAGER


def reset_task_manager() -> None:
    """重置任务管理器单例。"""
    global _DEFAULT_MANAGER, _DEFAULT_MANAGER_KEY
    if _DEFAULT_MANAGER is not None:
        _DEFAULT_MANAGER.close()
    _DEFAULT_MANAGER = None
    _DEFAULT_MANAGER_KEY = None


async def shutdown_task_manager() -> None:
    """异步关闭任务管理器。"""
    global _DEFAULT_MANAGER, _DEFAULT_MANAGER_KEY
    if _DEFAULT_MANAGER is not None:
        await _DEFAULT_MANAGER.aclose()
    _DEFAULT_MANAGER = None
    _DEFAULT_MANAGER_KEY = None


async def _close_process_stdin(process: asyncio.subprocess.Process) -> None:
    """安全关闭进程的stdin。"""
    stdin = process.stdin
    if stdin is None or stdin.is_closing():
        return
    stdin.close()
    try:
        await stdin.wait_closed()
    except (BrokenPipeError, ConnectionResetError):
        pass
