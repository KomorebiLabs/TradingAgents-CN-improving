"""
================================================================================
                      NEUTRAL_DEBATOR.PY 详解
                         中性风险辩论家节点
================================================================================

【模块定位】
    本文件是 TradingAgents 的"中性风险辩论家"节点。

    Neutral 是激进派和保守派之间的"调停者"：
    → 既不完全支持 Aggressive 的激进策略
    → 也不完全同意 Conservative 的保守立场
    → 试图找出"平衡点"

【中性派的核心思想】

    1. 核心理念：
       → 全面权衡（Balanced Perspective）
       → 考虑上行和下行风险
       → 追求"最优风险调整后收益"

    2. 关注点：
       → 上行空间（Upside）
       → 下行风险（Downside）
       → 市场趋势（Market Trends）
       → 多元化策略（Diversification）

    3. 思维方式：
       → "激进和保守都有道理，关键是比例"
       → "好的策略是动态的，根据情况调整"
       → "没有银弹，只有权衡"

【与其他两方的关系】

    Neutral 扮演的是"批评者"角色：
    → 指出 Aggressive 的"过度乐观"
    → 指出 Conservative 的"过度悲观"
    → 提出"更平衡"的方案

    不同于 Research Manager 层（Bull vs Bear）的是：
    → Bull/Bear 争论的是"方向"（买还是卖）
    → 三位风险辩论家争论的是"程度"（买多少/怎么买）

【Prompt 设计要点】
    • 强调"平衡"而非"站队"
    • 要求指出其他两方的"极端"
    • 提出"可持续的温和策略"

================================================================================
"""

from tradingagents.agents.utils.agent_utils import (
    build_conclusion_template_instruction,
    enforce_execution_profile_output,
    build_screener_semantic_instruction,
    build_semantic_execution_profile,
    enforce_skill_usage,
)
from tradingagents.agents.utils.state_helpers import sync_risk_debate_update
from tradingagents.harness.skills.injector import SkillInjector
from tradingagents.harness.skills.types import DecisionType


def create_neutral_debator(llm, skill_injector=None):
    if skill_injector is None:
        skill_injector = SkillInjector()
    """
    【工厂函数】创建中性风险辩论家节点

    【neutral_node 的工作流程】

        ┌─────────────────────────────────────────────────────────────────────┐
        │                                                                       │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 1: 读取状态                                                │   │
        │   │                                                               │   │
        │   │  • risk_debate_state → 辩论历史                               │   │
        │   │  • 4位分析师的报告                                             │   │
        │   │  • Trader 的交易建议                                           │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                               │                                      │
        │                               ▼                                      │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 2: 构建 Prompt（中性视角）                                │   │
        │   │                                                               │   │
        │   │  核心任务：                                                   │   │
        │   │    • 批判性分析 Aggressive 的激进观点                         │   │
        │   │    • 批判性分析 Conservative 的保守观点                       │   │
        │   │    • 提出"最优平衡"方案                                        │   │
        │   │    • 强调"可持续"而非"极端"                                   │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                               │                                      │
        │                               ▼                                      │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 3: 更新辩论状态                                          │   │
        │   │                                                               │   │
        │   │  • 追加到 history                                             │   │
        │   │  • 追加到 neutral_history                                     │   │
        │   │  • 更新 current_neutral_response                              │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                                                                       │
        └─────────────────────────────────────────────────────────────────────┘
    """

    def neutral_node(state) -> dict:
        """
        【节点函数】中性风险辩论家的核心逻辑
        """

        # ─────────────────────────────────────────────────────────────────
        # 第一步：从 state 读取辩论状态
        # ─────────────────────────────────────────────────────────────────

        risk_debate_state = state["risk_debate_state"]

        # 完整的辩论历史
        history = risk_debate_state.get("history", "")

        # 中性派自己的历史
        neutral_history = risk_debate_state.get("neutral_history", "")

        # 其他两方的最新观点（用于批判性分析）
        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_conservative_response = risk_debate_state.get("current_conservative_response", "")

        # ─────────────────────────────────────────────────────────────────
        # 第二步：读取分析师报告
        # ─────────────────────────────────────────────────────────────────

        market_research_report = state["market_report"]         # 市场技术分析
        sentiment_report = state["sentiment_report"]             # 社交媒体情绪
        news_report = state["news_report"]                     # 新闻分析
        fundamentals_report = state["fundamentals_report"]       # 基本面分析

        # ─────────────────────────────────────────────────────────────────
        # 第三步：读取 Trader 的交易建议
        # ─────────────────────────────────────────────────────────────────

        trader_decision = state["trader_investment_plan"]
        semantic_instruction = build_screener_semantic_instruction(state, "portfolio_manager")
        execution_profile = build_semantic_execution_profile(state, "risk")
        route_decision = state.get("route_decision", {}) or state.get("screener_context", {}).get("route_decision", {}) or {}
        debate_risk_weight = str(route_decision.get("debate_risk_weight", "") or "normal")
        capital_quality = str(route_decision.get("capital_quality", "") or "none")
        policy_role = str(route_decision.get("policy_role", "") or "none")
        trader_plan_char_limit = execution_profile.get("trader_plan_char_limit")
        style = str(execution_profile.get("response_style", "balanced"))
        conclusion_mode = str(execution_profile.get("conclusion_mode", "standard"))
        conclusion_template_instruction = build_conclusion_template_instruction(conclusion_mode)
        must_include = execution_profile.get("evidence_must_include", []) or []
        if trader_plan_char_limit:
            trader_decision = trader_decision[:trader_plan_char_limit]

        # ─────────────────────────────────────────────────────────────────
        # 第四步：注入 Skills
        # ─────────────────────────────────────────────────────────────────

        current_count = risk_debate_state["count"]
        skill_prompt, injected_skill_names = skill_injector.inject(
            decision_type=DecisionType.VALUATION,
            existing_prompt="",
            node_name="neutral",
            debate_round=current_count or 1,
            is_counter_round=bool(current_count >= 1),
            is_adjudication=False,
        )

        # ─────────────────────────────────────────────────────────────────
        # 第五步：构建 Prompt
        # ─────────────────────────────────────────────────────────────────
        # Prompt 强调：
        # 1. 平衡观点
        # 2. 批判性分析其他两方
        # 3. 提出温和可持续的策略

        prompt = skill_prompt + "\n\n" + f"""As the Neutral Risk Analyst, your role is to provide a balanced perspective, weighing both the potential benefits and risks of the trader's decision or plan. You prioritize a well-rounded approach, evaluating the upsides and downsides while factoring in broader market trends, potential economic shifts, and diversification strategies.Here is the trader's decision:

{trader_decision}

Your task is to challenge both the Aggressive and Conservative Analysts, pointing out where each perspective may be overly optimistic or overly cautious. Use insights from the following data sources to support a moderate, sustainable strategy to adjust the trader's decision:
Screener semantic routing guidance: {semantic_instruction}
Semantic execution profile: {execution_profile}
Execution style: {style}
Required evidence: {must_include}
Conclusion template: {conclusion_template_instruction}
Route risk weight: {debate_risk_weight}
Route capital quality: {capital_quality}
Route policy role: {policy_role}

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history} Here is the last response from the aggressive analyst: {current_aggressive_response} Here is the last response from the conservative analyst: {current_conservative_response}. If there are no responses from the other viewpoints yet, present your own argument based on the available data.

Engage actively by analyzing both sides critically, addressing weaknesses in the aggressive and conservative arguments to advocate for a more balanced approach.
If Route risk weight is high, bias toward actionable compromise controls such as staggered entry, smaller sizing, and explicit invalidation levels.
If Route policy role is policy_core_member or policy_top_stock, distinguish between leader-quality continuation and theme-overcrowding failure.
Challenge each of their points to illustrate why a moderate risk strategy might offer the best of both worlds, providing growth potential while safeguarding against extreme volatility. Focus on debating rather than simply presenting data, aiming to show that a balanced view can lead to the most reliable outcomes. Output conversationally as if you are speaking without any special formatting."""

        # ─────────────────────────────────────────────────────────────────
        # 第五步：调用 LLM
        # ─────────────────────────────────────────────────────────────────

        response = llm.invoke(prompt)
        response.content = enforce_execution_profile_output(response.content, execution_profile)

        skill_result = enforce_skill_usage(
            content=response.content,
            injected_skill_names=injected_skill_names,
            node_name="neutral",
            decision_type=DecisionType.VALUATION.value,
            debate_round=current_count or 1,
            is_counter_round=bool(current_count >= 1),
            is_adjudication=False,
        )
        response.content = skill_result["content"]

        # 加上角色标识
        argument = f"Neutral Analyst: {response.content}"

        # ─────────────────────────────────────────────────────────────────
        # 第六步：更新辩论状态
        # ─────────────────────────────────────────────────────────────────

        new_risk_debate_state = {
            # 追加到完整历史
            "history": history + "\n" + argument,

            # 保持其他两方历史不变
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": risk_debate_state.get("conservative_history", ""),

            # 追加到中性派历史
            "neutral_history": neutral_history + "\n" + argument,

            # 标记最新发言
            "latest_speaker": "Neutral",

            # 保持两方最新论点不变
            "current_aggressive_response": risk_debate_state.get("current_aggressive_response", ""),
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),

            # 更新中性派最新论点
            "current_neutral_response": argument,

            # 辩论轮次 +1
            "count": risk_debate_state["count"] + 1,
        }

        # ─────────────────────────────────────────────────────────────────
        # 第七步：返回更新后的状态
        # ─────────────────────────────────────────────────────────────────

        return sync_risk_debate_update(
            debate_state=new_risk_debate_state,
            sender="Neutral Analyst",
        )

    return neutral_node
