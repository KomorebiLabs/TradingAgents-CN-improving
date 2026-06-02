"""
模块文档: paths.py - 记忆路径管理

================================================================================
特殊Python语法说明:
1. hashlib.sha1:
   SHA-1哈希算法，用于生成唯一标识符。
   接收bytes输入，返回摘要。

2. hexdigest():
   返回十六进制格式的摘要字符串。

3. Path.resolve():
   返回绝对路径，解析所有符号链接。
================================================================================

功能说明:
    管理项目记忆存储的路径。
    每个项目有独立的记忆目录，使用路径哈希确保唯一性。
"""

from __future__ import annotations

from hashlib import sha1
from pathlib import Path

from openharness.config.paths import get_data_dir


def get_project_memory_dir(cwd: str | Path) -> Path:
    """
    =============================================================================
    函数文档: get_project_memory_dir - 获取项目记忆目录

    参数说明:
        cwd: 项目根目录路径

    返回值:
        Path - 项目专用的记忆目录

    作用说明:
        为每个项目创建或获取一个独立的记忆存储目录。
        目录名包含项目名和路径哈希，确保不同项目不会冲突。

    目录结构:
        <data_dir>/memory/
        ├── my-project-a1b2c3d4e5f6/
        └── another-project-7g8h9i0j1k2l/

    为什么需要路径哈希:
        1. 唯一性：不同路径的项目可能有相同名称
        2. 隔离：确保一个项目的记忆不会影响另一个
        3. 持久化：记忆跨会话保存

    示例:
        # 获取项目的记忆目录
        memory_dir = get_project_memory_dir("/path/to/my-project")
        # 返回: <data_dir>/memory/my-project-a1b2c3d4e5f6/
    =============================================================================
    """
    path = Path(cwd).resolve()
    # 生成路径的哈希，取前12个字符
    digest = sha1(str(path).encode("utf-8")).hexdigest()[:12]
    # 目录名: 项目名-哈希值
    memory_dir = get_data_dir() / "memory" / f"{path.name}-{digest}"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


def get_memory_entrypoint(cwd: str | Path) -> Path:
    """
    =============================================================================
    函数文档: get_memory_entrypoint - 获取记忆入口文件

    参数说明:
        cwd: 项目根目录路径

    返回值:
        Path - MEMORY.md入口文件的路径

    作用说明:
        返回项目记忆目录中的主入口文件（MEMORY.md）。
        这个文件作为所有记忆的索引目录。

    入口文件的作用:
        1. 索引：列出所有记忆文件的链接
        2. 概览：提供项目记忆的整体视图
        3. 快速访问：打开一个文件即可看到所有记忆

    示例:
        # 获取入口文件路径
        entrypoint = get_memory_entrypoint("/path/to/project")
        # 返回: <memory_dir>/MEMORY.md
    =============================================================================
    """
    return get_project_memory_dir(cwd) / "MEMORY.md"
