"""
================================================================================
tradingagents/graph/propagation.py - 状态初始化与流转
================================================================================

【模块职责】
    Propagator 是整个 DAG 的"状态工厂"和"启动器"。

    1. create_initial_state() → 创建初始状态字典（State 的起点）
    2. get_graph_args() → 返回图执行时的配置参数

【核心概念】
    • 初始状态：Graph 执行前，所有字段必须预先初始化
    • 递归限制：防止无限循环，默认 100 步上限
    • Stream 模式："values" 模式会输出每个节点的完整状态快照

【LangGraph 视角】
    这个文件对应 LangGraph 的 "State 初始化阶段"。
    在 LangGraph 中，你可以用 @entrypoint 装饰器简化这部分，
    但 TradingAgents 选择手动管理，展示了对底层机制的掌控力。

================================================================================
"""

from typing import Dict, Any, List, Optional
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
    STATE_SCHEMA_VERSION,
)
from tradingagents.agents.utils.agent_utils import build_instrument_profile, validate_semantic_prompt_slots
from tradingagents.default_config import DEFAULT_CONFIG


class Propagator:
    """
    状态传播器 - 负责状态的初始化和流转配置

    在 DAG 执行前，创建干净的初始状态；
    在 DAG 执行时，提供必要的配置参数。
    """

    def __init__(self, max_recur_limit=100, config: Optional[Dict[str, Any]] = None):
        """
        初始化传播器

        Args:
            max_recur_limit: 最大递归深度限制，防止 Agent 陷入死循环
                             默认 100 步，对于大多数交易分析场景足够
        """
        self.max_recur_limit = max_recur_limit
        self.config = config or {}

    def create_initial_state(
        self, company_name: str, trade_date: str, selected_analysts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        创建 AgentState 初始状态

        这是整个 Graph 执行的起点！所有后续节点都会基于这个状态继续演进。

        Args:
            company_name: 目标公司/股票代码，如 "AAPL", "TSLA"
            trade_date: 交易分析日期，格式 "YYYY-MM-DD"

        Returns:
            包含所有必需字段的初始状态字典

        状态字段说明：
        ┌────────────────────────────────────────────────────────────┐
        │ 【元数据】                                                   │
        │   • messages         → 初始消息列表，以 human 角色开始       │
        │   • company_of_interest → 目标公司                          │
        │   • trade_date       → 交易日期                            │
        ├────────────────────────────────────────────────────────────┤
        │ 【分析报告】 - 初始为空字符串，等待 Analyst 节点填充         │
        │   • market_report    → 市场技术分析                        │
        │   • fundamentals_report → 基本面分析                        │
        │   • sentiment_report → 社交媒体情绪                         │
        │   • news_report      → 新闻舆情                            │
        ├────────────────────────────────────────────────────────────┤
        │ 【投资辩论状态】 - 嵌套状态，初始化为空结构                  │
        │   • bull_history     → 多头辩论历史（初始为空）              │
        │   • bear_history    → 空头辩论历史（初始为空）              │
        │   • history          → 综合对话历史                         │
        │   • current_response → 最新响应（初始为空）                  │
        │   • judge_decision  → 裁判裁决（初始为空）                  │
        │   • count            → 辩论轮次（初始为 0）                 │
        ├────────────────────────────────────────────────────────────┤
        │ 【风险辩论状态】 - 嵌套状态，三方辩论                        │
        │   • aggressive_history  → 激进派历史                       │
        │   • conservative_history → 保守派历史                       │
        │   • neutral_history    → 中立派历史                        │
        │   • history            → 综合对话历史                       │
        │   • latest_speaker     → 上一轮发言者                       │
        │   • current_*_response → 各方最新响应                       │
        │   • judge_decision    → 裁判裁决                           │
        │   • count             → 辩论轮次                            │
        └────────────────────────────────────────────────────────────┘
        """
        selected_analysts = selected_analysts or [
            "market",
            "social",
            "news",
            "fundamentals",
        ]

        investment_debate_state = InvestDebateState(
            {
                "bull_history": "",
                "bear_history": "",
                "history": "",
                "current_response": "",
                "judge_decision": "",
                "count": 0,
                "latest_speaker": "",
            }
        )

        risk_debate_state = RiskDebateState(
            {
                "aggressive_history": "",
                "conservative_history": "",
                "neutral_history": "",
                "history": "",
                "latest_speaker": "",
                "current_aggressive_response": "",
                "current_conservative_response": "",
                "current_neutral_response": "",
                "judge_decision": "",
                "count": 0,
            }
        )
        instrument_profile = build_instrument_profile(company_name, self.config)
        screener_context = dict(self.config.get("screener_context", {}))
        semantic_prompt_slots = validate_semantic_prompt_slots(
            screener_context.get("semantic_prompt_slots", {})
        )
        screener_context["semantic_prompt_slots"] = semantic_prompt_slots
        route_decision = dict(screener_context.get("route_decision", {}))
        semantic_execution_profile = dict(
            screener_context.get("semantic_execution_profile", {})
            or self.config.get("semantic_execution_profile", {})
        )
        semantic_flow_controls = dict(self.config.get("semantic_flow_controls", {}))

        return {
            "schema_version": STATE_SCHEMA_VERSION,
            # ─────────────────────────────────────────────────────────
            # 【元数据字段】
            # ─────────────────────────────────────────────────────────
            "messages": [("human", company_name)],  # 初始消息，human 角色发起
            "company_of_interest": company_name,    # 目标公司名称
            "trade_date": str(trade_date),          # 交易日期（转字符串）
            "sender": "Human",
            "screener_context": screener_context,
            "historical_context": None,  # Loaded at graph init time by TradingAgentsGraph
            "semantic_prompt_slots": semantic_prompt_slots,
            "semantic_execution_profile": semantic_execution_profile,
            "route_decision": route_decision,
            "ticker_info": {
                "symbol": company_name,
                "trade_date": str(trade_date),
                "instrument_context": "",
                "selected_analysts": selected_analysts,
                "semantic_flow_controls": semantic_flow_controls,
                "semantic_execution_profile": semantic_execution_profile,
                "route_decision": route_decision,
                "market": instrument_profile["market"],
                "exchange": instrument_profile["exchange"],
                "is_cn_equity": instrument_profile["is_cn_equity"],
                "segment": instrument_profile["segment"],
                "style_bucket": instrument_profile["style_bucket"],
                "skills": instrument_profile["skills"],
            },
            "orchestration": {
                "stage": "analysis",
                "phase": "analyst",
                "next_stage": "analyst",
                "completed": False,
                "final_route": "",
                "final_reason": "",
                "context_budget_tokens": 24000,
                "compression_threshold_chars": DEFAULT_CONFIG.get("orchestration_compression_threshold_chars", 36000),
                "compression_notes": "",
                "compression_required": False,
                "selected_analysts": selected_analysts,
                "semantic_flow_controls": semantic_flow_controls,
                "route_decision": route_decision,
                "semantic_execution_profile": semantic_execution_profile,
                "enable_confidence_score": bool(
                    self.config.get("enable_confidence_score", False)
                ),
                "event_trail": [],
            },

            # ─────────────────────────────────────────────────────────
            # 【嵌套状态】投资辩论状态 (InvestDebateState)
            # ─────────────────────────────────────────────────────────
            "investment_debate_state": investment_debate_state,

            # ─────────────────────────────────────────────────────────
            # 【嵌套状态】风险辩论状态 (RiskDebateState)
            # ─────────────────────────────────────────────────────────
            "risk_debate_state": risk_debate_state,
            "debate_blocks": {
                "investment": investment_debate_state,
                "risk": risk_debate_state,
            },

            # ─────────────────────────────────────────────────────────
            # 【分析报告字段】- 初始为空，等待 Analyst 节点填充
            # ─────────────────────────────────────────────────────────
            "market_report": "",          # 市场技术分析报告
            "fundamentals_report": "",    # 基本面财务分析报告
            "sentiment_report": "",       # 社交媒体情绪报告
            "news_report": "",           # 新闻舆情报告
            "analyst_reports": {
                "market": "",
                "fundamentals": "",
                "sentiment": "",
                "news": "",
            },
            "investment_plan": "",
            "trader_investment_plan": "",
            "final_trade_decision": "",
            "decision_blocks": {
                "investment_plan": "",
                "trader_plan": "",
                "final_trade_decision": "",
            },
        }

    def get_graph_args(self, callbacks: Optional[List] = None) -> Dict[str, Any]:
        """
        获取图执行的参数配置

        这些参数会在调用 graph.invoke() 或 graph.stream() 时传入。

        Args:
            callbacks: 可选的回调处理器列表
                       用于追踪 LLM 调用和 Tool 执行统计

        Returns:
            包含执行配置的字典，包含：
            • stream_mode: "values" - 输出每个节点的完整状态
            • config: 包含递归限制和回调的配置

        【LangGraph 知识点】
            • stream_mode="values" vs "updates":
              - "values": 返回每个节点执行后的完整状态快照
              - "updates": 只返回状态中有变化的字段

            • recursion_limit:
              - 防止 Agent 陷入无限循环
              - 每次节点执行（无论是否使用 Tool）都算 1 步
              - 100 步对于复杂的多 Agent 辩论足够
        """
        # 构建 config 字典
        config = {"recursion_limit": self.max_recur_limit}

        # 如果提供了回调处理器，加入配置
        # 注意：LLM 回调在 LLM 构造函数中单独处理
        if callbacks:
            config["callbacks"] = callbacks

        return {
            "stream_mode": "values",  # 输出完整状态快照
            "config": config,         # 执行配置
        }
