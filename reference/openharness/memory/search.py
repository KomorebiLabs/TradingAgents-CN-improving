"""
模块文档: search.py - 记忆搜索

================================================================================
特殊Python语法说明:
1. re.findall() with regex:
   正则表达式匹配，返回所有匹配项的列表。

2. Unicode范围匹配:
   r"[\u4e00-\u9fff\u3400-\u4dbf]" 匹配CJK统一表意文字和扩展A区。

3. set union (|):
   合并多个集合，返回所有唯一元素。

4. 启发式评分:
   使用加权分数评估文档与查询的相关性。
================================================================================

功能说明:
    提供记忆文件的简单关键词搜索功能。
    支持英文和中文（汉字）搜索。
"""

from __future__ import annotations

import re
from pathlib import Path

from openharness.memory.scan import scan_memory_files
from openharness.memory.types import MemoryHeader


def find_relevant_memories(
    query: str,
    cwd: str | Path,
    *,
    max_results: int = 5,
) -> list[MemoryHeader]:
    """
    =============================================================================
    函数文档: find_relevant_memories - 查找相关记忆

    参数说明:
        query: 搜索查询词
        cwd: 项目根目录
        max_results: 返回的最大结果数

    返回值:
        list[MemoryHeader] - 相关记忆列表，按相关度排序

    作用说明:
        基于关键词匹配查找与查询相关的记忆文件。

    评分算法:
        1. 将查询分词为搜索token
        2. 对每个记忆文件计算分数:
           - 元数据匹配(title + description): 权重2.0
           - 内容预览匹配: 权重1.0
        3. 分数 > 0 的记忆被保留
        4. 按(分数降序, 修改时间降序)排序
        5. 返回前max_results个

    为什么元数据权重更高:
        标题和描述通常更准确地反映记忆的主题。
        匹配这些字段比匹配正文内容更有意义。

    示例:
        memories = find_relevant_memories("auth login", cwd, max_results=3)
    =============================================================================
    """
    tokens = _tokenize(query)
    if not tokens:
        return []

    scored: list[tuple[float, MemoryHeader]] = []
    for header in scan_memory_files(cwd, max_files=100):
        # 合并元数据和内容用于搜索
        meta = f"{header.title} {header.description}".lower()
        body = header.body_preview.lower()

        # 元数据命中权重2.0，内容预览权重1.0
        meta_hits = sum(1 for t in tokens if t in meta)
        body_hits = sum(1 for t in tokens if t in body)
        score = meta_hits * 2.0 + body_hits

        if score > 0:
            scored.append((score, header))

    # 排序：分数优先，其次按修改时间
    scored.sort(key=lambda item: (-item[0], -item[1].modified_at))
    return [header for _, header in scored[:max_results]]


def _tokenize(text: str) -> set[str]:
    """
    =============================================================================
    函数文档: _tokenize - 分词

    参数说明:
        text: 要分词的文本

    返回值:
        set[str] - 搜索token集合

    作用说明:
        将查询文本转换为搜索token。

    分词策略:
        1. ASCII单词: 3字符以上的[A-Za-z0-9_]+组合
        2. 汉字: 每个汉字作为独立token（中文不分词）

    为什么这样设计:
        - 3字符过滤短词，减少噪音
        - 中文每个字都有含义，作为独立token
        - set去重，避免重复匹配

    示例:
        "login auth" -> {"login", "auth"}
        "用户认证" -> {"用", "户", "认", "证"}
    =============================================================================
    """
    # ASCII单词token（3字符以上）
    ascii_tokens = {t for t in re.findall(r"[A-Za-z0-9_]+", text.lower()) if len(t) >= 3}
    # 汉字（每个字符独立）
    han_chars = set(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))
    return ascii_tokens | han_chars
