"""Memory type definitions (split from memory.py — refactor/merger-pipeline style)."""

from typing import List
from typing_extensions import TypedDict, NotRequired


class OrchestrationMemoryEntry(TypedDict, total=False):
    """Structure化编排记忆条目 schema.

    定义存储在 StructuredMemory 中的编排记忆的结构化字段，
    支持结构化查询和过滤。
    """

    # ===== 核心内容 =====
    situation: str                          # 情境描述（原文）
    recommendation: str                    # 建议/洞察（原文）

    # ===== 编排上下文 - 结构化字段 =====
    stage_sequence: List[str]               # 阶段序列: ["analyst", "research", "trader", "risk"]
    phase_sequence: List[str]               # 相位序列: ["analyst_market", "analyst_news", ...]
    compression_phases: List[str]           # 触发压缩的阶段
    compression_rate: float                 # 压缩比率 (0.0 - 1.0)

    # ===== 工具/上下文 =====
    segment: str                            # 板块: "cn_main_board" | "cn_chinext" | "cn_star" | "cn_bse"
    style_bucket: str                       # 风格: "dividend" | "growth" | "value" | "momentum"
    selected_analysts: List[str]           # 启用的分析师
    skills: List[str]                        # 启用的技能

    # ===== 路由结果 =====
    final_route: str                        # 最终路由: "direct" | "compression_handoff" | "portfolio_handoff"
    final_reason: str                       # 路由选择原因
    route_category: str                     # 路由类别: "normal" | "mixed" | "complex"

    # ===== 事件轨迹统计 =====
    total_events: int                       # 总事件数
    unique_stages: List[str]               # 访问的唯一阶段列表
    bottleneck_stages: List[str]           # 瓶颈阶段（重复访问）

    # ===== 标的 =====
    ticker: str                             # 股票代码
    company_name: str                       # 公司名称

    # ===== 时间戳 =====
    trade_date: str                         # 交易日期 (yyyy-mm-dd)
    created_at: str                         # 创建时间 (ISO format)

    # ===== 结果评估（事后填入）=====
    actual_return: NotRequired[float]           # 实际收益率
    decision_quality: NotRequired[str]         # 决策质量: "good" | "neutral" | "poor"

    # ===== 额外上下文 =====
    sector_tools_used: NotRequired[List[str]]  # 使用的行业工具
    macro_tools_used: NotRequired[List[str]]   # 使用的宏观工具
    event_tools_used: NotRequired[List[str]]    # 使用的事件工具
