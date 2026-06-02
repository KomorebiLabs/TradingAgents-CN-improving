"""
模块文档: memdir.py - 记忆提示词生成

================================================================================
特殊Python语法说明:
1. list切片 [start:end]:
   获取列表的子集，这里用于限制行数。

2. "\n".join():
   将字符串列表合并为一个字符串，用换行符分隔。
================================================================================

功能说明:
    生成注入到系统提示词中的记忆相关上下文。
    帮助AI了解项目的记忆情况和访问方式。
"""

from __future__ import annotations

from pathlib import Path

from openharness.memory.paths import get_memory_entrypoint, get_project_memory_dir


def load_memory_prompt(cwd: str | Path, *, max_entrypoint_lines: int = 200) -> str | None:
    """
    =============================================================================
    函数文档: load_memory_prompt - 加载记忆提示文本

    参数说明:
        cwd: 项目根目录
        max_entrypoint_lines: MEMORY.md的最大行数

    返回值:
        str | None - 格式化的记忆提示文本

    作用说明:
        生成一段包含项目记忆信息的Markdown文本，
        用于注入到系统提示词中，让AI知道如何使用记忆系统。

    返回内容结构:
        # Memory
        - Persistent memory directory: <路径>
        - 使用说明...
        
        ## MEMORY.md
        (如果存在，显示入口文件内容)

    为什么需要这个函数:
        AI需要知道：
        1. 记忆存储在哪里
        2. 如何创建和访问记忆
        3. 当前有哪些记忆（通过入口文件）

    示例输出:
        # Memory
        - Persistent memory directory: /data/memory/project-abc
        - Use this directory to store durable user or project context...
        
        ## MEMORY.md
        - [Auth Design](auth-design.md)
        - [API Decisions](api-decisions.md)
    =============================================================================
    """
    memory_dir = get_project_memory_dir(cwd)
    entrypoint = get_memory_entrypoint(cwd)

    # 构建提示文本
    lines = [
        "# Memory",
        f"- Persistent memory directory: {memory_dir}",
        "- Use this directory to store durable user or project context that should survive future sessions.",
        "- Prefer concise topic files plus an index entry in MEMORY.md.",
    ]

    # 如果入口文件存在，读取其内容
    if entrypoint.exists():
        content_lines = entrypoint.read_text(encoding="utf-8").splitlines()[:max_entrypoint_lines]
        if content_lines:
            lines.extend(["", "## MEMORY.md", "```md", *content_lines, "```"])
    else:
        lines.extend(
            [
                "",
                "## MEMORY.md",
                "(not created yet)",
            ]
        )

    return "\n".join(lines)
