"""
模块文档: scan.py - 记忆文件扫描

================================================================================
特殊Python语法说明:
1. Path.glob("*.md"):
   查找所有Markdown文件

2. glob()返回生成器:
   惰性遍历文件，需要list()转换为列表

3. path.stat().st_mtime:
   获取文件最后修改时间
================================================================================

功能说明:
    扫描项目记忆目录，提取记忆文件的元数据。
    生成MemoryHeader列表供UI展示和搜索使用。
"""

from __future__ import annotations

from pathlib import Path

from openharness.memory.paths import get_project_memory_dir
from openharness.memory.types import MemoryHeader


def scan_memory_files(cwd: str | Path, *, max_files: int = 50) -> list[MemoryHeader]:
    """
    =============================================================================
    函数文档: scan_memory_files - 扫描记忆文件

    参数说明:
        cwd: 项目根目录
        max_files: 返回的最大文件数量

    返回值:
        list[MemoryHeader] - 按修改时间倒序排列的记忆头列表

    作用说明:
        扫描项目的记忆目录，收集所有记忆文件的元数据。
        结果按最近修改时间排序，最新的在前。

    为什么排除MEMORY.md:
        MEMORY.md是入口/索引文件，不是一个独立的记忆。
        独立的记忆存放在单独的.md文件中。

    为什么限制数量:
        1. 性能：大目录可能有很多文件
        2. 实用性：UI通常只需要显示最近的几个
    =============================================================================
    """
    memory_dir = get_project_memory_dir(cwd)
    headers: list[MemoryHeader] = []

    # 遍历所有.md文件
    for path in memory_dir.glob("*.md"):
        # 排除入口文件
        if path.name == "MEMORY.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        # 解析文件头
        header = _parse_memory_file(path, text)
        headers.append(header)

    # 按修改时间倒序排序
    headers.sort(key=lambda item: item.modified_at, reverse=True)
    return headers[:max_files]


def _parse_memory_file(path: Path, content: str) -> MemoryHeader:
    """
    =============================================================================
    函数文档: _parse_memory_file - 解析记忆文件

    参数说明:
        path: 文件路径（用于提取默认标题和修改时间）
        content: 文件内容

    返回值:
        MemoryHeader - 解析得到的记忆头

    作用说明:
        从记忆文件的YAML frontmatter和内容中提取元数据。

    解析内容:
        1. YAML frontmatter: name, description, type
        2. 降级：文件名作为标题，首段作为描述
        3. 内容预览：去除标题后的前几行

    为什么需要预览:
        搜索结果需要展示记忆的摘要内容。
        预览应该是实际内容，不包含标题。
    """
    lines = content.splitlines()
    title = path.stem
    description = ""
    memory_type = ""
    body_start = 0

    # 解析YAML frontmatter
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                # 解析frontmatter内容
                for fm_line in lines[1:i]:
                    key, _, value = fm_line.partition(":")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    if not value:
                        continue
                    if key == "name":
                        title = value
                    elif key == "description":
                        description = value
                    elif key == "type":
                        memory_type = value
                body_start = i + 1
                break

    # 降级：从内容解析描述
    desc_line_idx: int | None = None
    if not description:
        for idx, line in enumerate(lines[body_start:body_start + 10], body_start):
            stripped = line.strip()
            if stripped and stripped != "---" and not stripped.startswith("#"):
                description = stripped[:200]
                desc_line_idx = idx
                break

    # 构建内容预览
    body_lines = [
        line.strip()
        for idx, line in enumerate(lines[body_start:], body_start)
        if line.strip()
        and not line.strip().startswith("#")
        and idx != desc_line_idx  # 排除已用作描述的行
    ]
    body_preview = " ".join(body_lines)[:300]

    return MemoryHeader(
        path=path,
        title=title,
        description=description,
        modified_at=path.stat().st_mtime,
        memory_type=memory_type,
        body_preview=body_preview,
    )
