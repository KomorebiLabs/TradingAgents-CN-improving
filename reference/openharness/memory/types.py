"""
模块文档: types.py - 记忆数据类型定义

================================================================================
特殊Python语法说明:
1. @dataclass(frozen=True):
   不可变数据类，表示记忆文件的元数据。
================================================================================

功能说明:
    定义了记忆系统的数据结构。
    MemoryHeader用于表示单个记忆文件的元信息。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MemoryHeader:
    """
    =============================================================================
    类文档: MemoryHeader - 记忆文件头信息

    作用说明:
        表示单个记忆文件的元数据，包含文件路径、标题、描述等信息。
        用于在列表和搜索结果中展示记忆文件。

    为什么需要这个结构:
        1. 快速预览：不需要读取完整文件就能展示摘要
        2. 搜索支持：为记忆文件提供可搜索的字段
        3. 排序依据：按修改时间排序

    字段说明:
        path: 文件的完整路径
        title: 记忆标题（从文件名或frontmatter提取）
        description: 简短描述（从frontmatter或首段提取）
        modified_at: 最后修改时间（Unix时间戳）
        memory_type: 记忆类型（可选分类标签）
        body_preview: 内容预览（前几行的摘要）
    =============================================================================
    """
    path: Path
    title: str
    description: str
    modified_at: float
    memory_type: str = ""
    body_preview: str = ""
