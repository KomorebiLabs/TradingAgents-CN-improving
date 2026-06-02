"""
模块文档: manager.py - 记忆文件管理

================================================================================
特殊Python语法说明:
1. re.sub():
   正则表达式替换，用于生成安全的文件名slug。

2. exclusive_file_lock:
   独占文件锁，防止并发写入冲突。

3. atomic_write_text:
   原子写入，防止写入时文件被部分读取。

4. Path.unlink():
   删除文件。
================================================================================

功能说明:
    提供记忆文件的增删改查操作。
    管理记忆目录和入口文件的创建与更新。
"""

from __future__ import annotations

from pathlib import Path
from re import sub

from openharness.memory.paths import get_memory_entrypoint, get_project_memory_dir
from openharness.utils.file_lock import exclusive_file_lock
from openharness.utils.fs import atomic_write_text


# =============================================================================
# 文件路径辅助
# =============================================================================

def _memory_lock_path(cwd: str | Path) -> Path:
    """
    =============================================================================
    函数文档: _memory_lock_path - 获取记忆锁文件路径
    """
    return get_project_memory_dir(cwd) / ".memory.lock"


# =============================================================================
# 记忆文件管理
# =============================================================================

def list_memory_files(cwd: str | Path) -> list[Path]:
    """
    =============================================================================
    函数文档: list_memory_files - 列出记忆文件

    参数说明:
        cwd: 项目根目录

    返回值:
        list[Path] - 按名称排序的记忆文件路径列表
    =============================================================================
    """
    memory_dir = get_project_memory_dir(cwd)
    return sorted(path for path in memory_dir.glob("*.md"))


def add_memory_entry(cwd: str | Path, title: str, content: str) -> Path:
    """
    =============================================================================
    函数文档: add_memory_entry - 添加记忆条目

    参数说明:
        cwd: 项目根目录
        title: 记忆标题
        content: 记忆内容

    返回值:
        Path - 创建的记忆文件路径

    作用说明:
        创建新的记忆文件并更新入口索引。

    实现逻辑:
        1. 将标题转换为安全的文件名slug
        2. 创建记忆文件
        3. 更新MEMORY.md入口文件，添加链接

    文件名slug转换:
        "My Memory Title" -> "my_memory_title.md"

    为什么使用锁:
        防止多个进程同时写入造成数据损坏。

    为什么需要更新入口:
        MEMORY.md作为所有记忆的索引，
        新增记忆需要添加到索引中。
    =============================================================================
    """
    memory_dir = get_project_memory_dir(cwd)
    # 生成安全的文件名
    slug = sub(r"[^a-zA-Z0-9]+", "_", title.strip().lower()).strip("_") or "memory"
    path = memory_dir / f"{slug}.md"

    with exclusive_file_lock(_memory_lock_path(cwd)):
        # 写入记忆文件
        atomic_write_text(path, content.strip() + "\n")

        # 更新入口索引
        entrypoint = get_memory_entrypoint(cwd)
        existing = entrypoint.read_text(encoding="utf-8") if entrypoint.exists() else "# Memory Index\n"
        if path.name not in existing:
            existing = existing.rstrip() + f"\n- [{title}]({path.name})\n"
            atomic_write_text(entrypoint, existing)

    return path


def remove_memory_entry(cwd: str | Path, name: str) -> bool:
    """
    =============================================================================
    函数文档: remove_memory_entry - 删除记忆条目

    参数说明:
        cwd: 项目根目录
        name: 要删除的记忆名称（文件名或slug）

    返回值:
        bool - 是否成功删除

    作用说明:
        删除指定的记忆文件并从入口索引中移除。

    为什么需要更新入口:
        删除文件后，索引中还留有链接会导致404。
        必须同时更新MEMORY.md。
    """
    memory_dir = get_project_memory_dir(cwd)
    # 查找匹配的文件
    matches = [path for path in memory_dir.glob("*.md") if path.stem == name or path.name == name]
    if not matches:
        return False

    path = matches[0]
    with exclusive_file_lock(_memory_lock_path(cwd)):
        # 删除文件
        if path.exists():
            path.unlink()

        # 从入口索引中移除
        entrypoint = get_memory_entrypoint(cwd)
        if entrypoint.exists():
            lines = [
                line
                for line in entrypoint.read_text(encoding="utf-8").splitlines()
                if path.name not in line  # 移除包含该文件的行
            ]
            atomic_write_text(entrypoint, "\n".join(lines).rstrip() + "\n")

    return True
