"""
TradingAgents 状态机 (State Machine) 定义

============================================================
                    STATE 架构总览
============================================================

AgentState 是整个框架的"全局上下文"，贯穿整个 DAG 执行流程。

它包含以下层次：

┌─────────────────────────────────────────────────────────┐
│                    AgentState (主状态)                    │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 元数据字段    │  │ 分析报告字段  │  │ 决策字段      │  │
│  │ (覆盖模式)    │  │ (覆盖模式)   │  │ (覆盖模式)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              嵌套状态 (Nested State)              │   │
│  │  ┌─────────────────┐    ┌─────────────────────┐  │   │
│  │  │ InvestDebateState│    │ RiskDebateState    │  │   │
│  │  │ (投资辩论状态)    │    │ (风险辩论状态)      │  │   │
│  │  │ - 追加聚合模式    │    │ - 追加聚合模式      │  │   │
│  │  └─────────────────┘    └─────────────────────┘  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              历史上下文字段                       │   │
│  │  historical_context (TTL 窗口内跨会话结论注入)     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘

============================================================
                    字段分类详解
============================================================

【第一层：元数据字段】 - 记录交易上下文信息
  • company_of_interest: 目标公司/股票代码
  • trade_date: 交易日期
  • sender: 当前执行节点的名称（用于追踪）

【第二层：分析报告字段】 - 四个 Analyst 并行/串行生成
  • market_report: 市场技术分析报告
  • sentiment_report: 社交媒体情绪报告
  • news_report: 新闻舆情报告
  • fundamentals_report: 基本面财务报告

【第三层：投资决策字段】 - Research Team 输出
  • investment_debate_state: 多空辩论状态（嵌套）
  • investment_plan: Research Manager 综合决策

【第四层：交易执行字段】 - Trading Team 输出
  • trader_investment_plan: Trader 制定的具体交易计划

【第五层：风险管控字段】 - Risk Management Team 输出
  • risk_debate_state: 三方风险辩论状态（嵌套）
  • final_trade_decision: Portfolio Manager 最终决策

【第六层：历史结论上下文】 - 跨会话注入
  • historical_context: 同 ticker 在 TTL 窗口内的历史分析结论

============================================================
                    聚合模式说明
============================================================

• 覆盖模式：直接赋值，后来的值覆盖前面的值
  → 用于：元数据、分析报告、最终决策

• 追加模式：通过 Annotated[str, "..."] + operator.add 或拼接
  → 用于：辩论历史 (bull_history, bear_history 等)

============================================================
"""

from typing import Annotated, Dict, Any, List, Optional
from typing_extensions import TypedDict

try:  # pragma: no cover - optional runtime dependency
    from langgraph.graph import MessagesState
except Exception:  # pragma: no cover
    class MessagesState(TypedDict, total=False):
        messages: List[Any]


# =============================================================================
# Canonical State Policy (declared 2026-08-16, schema v2)
# =============================================================================
# The STRUCTURED blocks below are the single source of truth ("canonical"):
#
#     analyst_reports   <- canonical analyst outputs
#     debate_blocks     <- canonical debate states
#     decision_blocks   <- canonical downstream decisions
#     ticker_info       <- canonical instrument metadata
#
# The legacy FLAT fields (market_report, investment_debate_state,
# final_trade_decision, ...) are read-compatibility mirrors only.
#
# Rules for new code:
#   1. WRITE structured blocks (via state_helpers.sync_* dual-write helpers
#      during the migration window). Never write flat-only.
#   2. READ from structured blocks. Flat reads are legacy
#      (graph/setup.py routers and graph/reflection.py still read flat —
#      they are backfilled by TradingAgentsGraph._ensure_structured_state).
#   3. Reconciliation direction: on conflict, STRUCTURED WINS.
#
# Retirement plan:
#   v2 (now)      - dual-write everywhere, structured declared canonical
#   v2.1 (TBD)    - nodes stop writing flat fields (remove from sync_* helpers)
#   v3.0 (TBD)    - flat fields removed from AgentState; legacy readers migrated
# =============================================================================

STATE_SCHEMA_VERSION = 2


# =============================================================================
# 嵌套状态类 (Nested State Classes)
# =============================================================================

# -----------------------------------------------------------------------------
# 投资辩论状态 (InvestDebateState)
# -----------------------------------------------------------------------------
# 用途：管理 Bull Researcher 和 Bear Researcher 之间的多空辩论
# 位置：Graph 执行流程中的 "Research Team" 阶段
#
# 字段说明：
#   • bull_history    → Bull (看多) 研究员的辩论历史（追加模式）
#   • bear_history    → Bear (看空) 研究员的辩论历史（追加模式）
#   • history         → 综合对话历史（追加模式）
#   • current_response → 最新的单轮响应
#   • judge_decision  → Research Manager 的裁决决策
#   • count           → 当前辩论轮次计数
# -----------------------------------------------------------------------------
class InvestDebateState(TypedDict):
    bull_history: Annotated[
        str, "Bullish Conversation history"  # 看多方（多头）的辩论历史
    ]
    bear_history: Annotated[
        str, "Bearish Conversation history"  # 看空方（空头）的辩论历史
    ]
    history: Annotated[str, "Conversation history"]  # 综合对话历史
    current_response: Annotated[str, "Latest response"]  # 最新一轮的响应内容
    judge_decision: Annotated[str, "Final judge decision"]  # 裁判（Research Manager）的最终裁决
    count: Annotated[int, "Length of the current conversation"]  # 辩论轮次计数器
    latest_speaker: Annotated[str, "Last speaker: Bull Researcher or Bear Researcher"]  # 追踪最后发言者
    # A2 收敛判定（Debate Convergence Check 节点写入；字段缺失时回退纯轮数逻辑）
    convergence_score: Annotated[int, "Latest convergence score 1-5 (3 = neutral/unknown)"]
    convergence_divergences: Annotated[str, "Unanswered core rebuttals listed by the convergence judge"]
    convergence_consensus: Annotated[str, "Agreed points (attached to Research Manager on early stop)"]
    convergence_log: Annotated[list, "Per-round convergence judgments for audit"]


# -----------------------------------------------------------------------------
# 风险辩论状态 (RiskDebateState)
# -----------------------------------------------------------------------------
# 用途：管理 Aggressive / Conservative / Neutral 三方风险辩论
# 位置：Graph 执行流程中的 "Risk Management" 阶段
#
# 字段说明：
#   • aggressive_history    → 激进派分析师的辩论历史
#   • conservative_history → 保守派分析师的辩论历史
#   • neutral_history      → 中立派分析师的辩论历史
#   • history              → 综合对话历史
#   • latest_speaker       → 上一轮发言的分析师名称
#   • current_*_response   → 各方最新响应
#   • judge_decision       → Portfolio Manager 的最终决策
#   • count                → 辩论轮次计数器
# -----------------------------------------------------------------------------
class RiskDebateState(TypedDict):
    aggressive_history: Annotated[
        str, "Aggressive Agent's Conversation history"  # 激进派分析师的辩论历史
    ]
    conservative_history: Annotated[
        str, "Conservative Agent's Conversation history"  # 保守派分析师的辩论历史
    ]
    neutral_history: Annotated[
        str, "Neutral Agent's Conversation history"  # 中立派分析师的辩论历史
    ]
    history: Annotated[str, "Conversation history"]  # 综合对话历史
    latest_speaker: Annotated[str, "Analyst that spoke last"]  # 上一轮发言者

    current_aggressive_response: Annotated[
        str, "Latest response by the aggressive analyst"  # 激进派最新响应
    ]
    current_conservative_response: Annotated[
        str, "Latest response by the conservative analyst"  # 保守派最新响应
    ]
    current_neutral_response: Annotated[
        str, "Latest response by the neutral analyst"  # 中立派最新响应
    ]
    judge_decision: Annotated[str, "Judge's decision"]  # 裁判（Portfolio Manager）的决策
    count: Annotated[int, "Length of the current conversation"]  # 辩论轮次计数器


# =============================================================================
# 结构化状态块 (Structured State Blocks)
# =============================================================================

class TickerInfoState(TypedDict, total=False):
    symbol: Annotated[str, "Exact ticker symbol being analyzed"]
    trade_date: Annotated[str, "Trading date in YYYY-MM-DD format"]
    instrument_context: Annotated[str, "Canonical instrument description"]
    selected_analysts: Annotated[List[str], "Enabled analyst pipeline"]
    market: Annotated[str, "Primary market classification"]
    exchange: Annotated[str, "Exchange code if available"]
    is_cn_equity: Annotated[bool, "Whether the instrument is a CN equity"]
    segment: Annotated[str, "Instrument market segment classification"]
    style_bucket: Annotated[str, "Heuristic style bucket for skill routing"]
    skills: Annotated[List[str], "Activated instrument skills"]


class AnalystReportsState(TypedDict, total=False):
    market: Annotated[str, "Market analysis report"]
    sentiment: Annotated[str, "Sentiment analysis report"]
    news: Annotated[str, "News analysis report"]
    fundamentals: Annotated[str, "Fundamental analysis report"]


class DebateBlocksState(TypedDict, total=False):
    investment: Annotated[InvestDebateState, "Investment debate block"]
    risk: Annotated[RiskDebateState, "Risk debate block"]


class DecisionBlocksState(TypedDict, total=False):
    investment_plan: Annotated[str, "Research manager output"]
    trader_plan: Annotated[str, "Trader output"]
    final_trade_decision: Annotated[str, "Portfolio manager output"]


class OrchestrationState(TypedDict, total=False):
    stage: Annotated[str, "Current orchestration stage"]
    phase: Annotated[str, "High-level pipeline phase"]
    next_stage: Annotated[str, "Explicit next-stage handoff target"]
    completed: Annotated[bool, "Whether the orchestration finished successfully"]
    final_route: Annotated[str, "Final route taken into completion"]
    final_reason: Annotated[str, "Why the final route was selected"]
    context_budget_tokens: Annotated[int, "Soft token budget for context"]
    compression_threshold_chars: Annotated[int, "Trigger threshold for summarization (chars, not tokens — unit fixed in A3)"]
    compression_notes: Annotated[str, "Compressed debate handoff notes"]
    compression_required: Annotated[bool, "Whether a compression handoff is required before continuing"]
    selected_analysts: Annotated[List[str], "Selected analyst pipeline"]
    enable_confidence_score: Annotated[bool, "Experimental confidence-score output flag"]
    event_trail: Annotated[List[Dict[str, Any]], "Chronological record of orchestration stage transitions"]


class OrchestrationEvent(TypedDict, total=False):
    """单条编排事件记录，用于 event_trail 追溯"""
    timestamp: Annotated[str, "ISO timestamp when this event was recorded"]
    node: Annotated[str, "Name of the node that produced this event"]
    stage: Annotated[str, "Stage at time of event"]
    phase: Annotated[str, "Phase at time of event"]
    next_stage: Annotated[str, "Next stage target at time of event"]
    compression_required: Annotated[bool, "Compression flag at time of event"]
    compression_triggered: Annotated[bool, "Whether compression handoff was triggered"]
    context_estimate: Annotated[int, "Estimated context length in characters"]


# =============================================================================
# 主状态类 (Main State Class)
# =============================================================================

class AgentState(MessagesState):
    """
    交易代理主状态 - 贯穿整个 DAG 执行流程的全局上下文

    继承自 LangGraph 的 MessagesState，自动包含 messages 字段（对话消息历史）
    """

    # -------------------------------------------------------------------------
    # 【第零层】Schema 版本 - 见模块顶部 Canonical State Policy
    # -------------------------------------------------------------------------
    schema_version: Annotated[int, "Canonical state schema version (STATE_SCHEMA_VERSION)"]

    # -------------------------------------------------------------------------
    # 【第一层】元数据字段 - 记录交易上下文
    # -------------------------------------------------------------------------
    company_of_interest: Annotated[str, "Company that we are interested in trading"]  # 目标公司/股票代码，如 "AAPL", "TSLA"
    trade_date: Annotated[str, "What date we are trading at"]  # 交易分析日期，格式 YYYY-MM-DD
    sender: Annotated[str, "Agent that sent this message"]  # 当前执行节点的名称，用于追踪状态流转
    screener_context: Annotated[Dict[str, Any], "Structured Screener context passed from pre-screening"]
    semantic_prompt_slots: Annotated[Dict[str, Any], "Screener semantic slots for downstream prompt routing"]
    ticker_info: Annotated[TickerInfoState, "Structured ticker metadata and execution scope"]
    orchestration: Annotated[OrchestrationState, "Execution control and context handoff metadata"]

    # -------------------------------------------------------------------------
    # 【第二层】分析报告字段 - 四个 Analyst 并行/串行生成
    # -------------------------------------------------------------------------
    # 特点：每个 Analyst 只写入一次，后续覆盖；最终报告是最终的分析结论
    market_report: Annotated[str, "Report from the Market Analyst"]  # 市场技术分析报告（K线、指标、趋势）
    sentiment_report: Annotated[str, "Report from the Social Media Analyst"]  # 社交媒体情绪报告（Twitter、Reddit 等）
    news_report: Annotated[str, "Report from the News Researcher of current world affairs"]  # 全球新闻舆情报告
    fundamentals_report: Annotated[str, "Report from the Fundamentals Researcher"]  # 基本面财务报告（财报、估值）
    analyst_reports: Annotated[AnalystReportsState, "Structured analyst outputs"]
    verification: Annotated[Dict[str, Any], "A4 evidence-verification summary block (claims/verified/unverified/warnings)"]

    # -------------------------------------------------------------------------
    # 【第三层】投资决策字段 - Research Team 输出
    # -------------------------------------------------------------------------
    # investment_debate_state: 嵌套的多空辩论状态（见上方定义）
    investment_debate_state: Annotated[
        InvestDebateState, "Current state of the debate on if to invest or not"  # 多空辩论状态
    ]
    investment_plan: Annotated[str, "Plan generated by the Analyst"]  # Research Manager 综合多方意见后的投资建议
    debate_blocks: Annotated[DebateBlocksState, "Structured debate state blocks"]

    # -------------------------------------------------------------------------
    # 【第四层】交易执行字段 - Trading Team 输出
    # -------------------------------------------------------------------------
    trader_investment_plan: Annotated[str, "Plan generated by the Trader"]  # Trader 基于投资建议制定的具体交易计划（仓位、入场点、风控）

    # -------------------------------------------------------------------------
    # 【第五层】风险管控字段 - Risk Management Team 输出
    # -------------------------------------------------------------------------
    # risk_debate_state: 嵌套的三方风险辩论状态（见上方定义）
    risk_debate_state: Annotated[
        RiskDebateState, "Current state of the debate on evaluating risk"  # 风险辩论状态
    ]
    final_trade_decision: Annotated[str, "Final decision made by the Risk Analysts"]  # Portfolio Manager 的最终交易决策
    decision_blocks: Annotated[DecisionBlocksState, "Structured downstream decisions"]

    # -------------------------------------------------------------------------
    # 【第六层】历史结论上下文 - 跨会话注入
    # -------------------------------------------------------------------------
    historical_context: Annotated[
        Optional[Dict[str, Any]],
        "Historical analysis conclusion for the same ticker within TTL window"
    ]
