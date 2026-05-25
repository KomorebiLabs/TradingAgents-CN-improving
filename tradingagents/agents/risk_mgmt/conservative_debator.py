"""
================================================================================
                   CONSERVATIVE_DEBATOR.PY 详解
                       保守风险辩论家节点
================================================================================

【模块定位】
    本文件是 TradingAgents 的"保守风险辩论家"节点。

    与 aggressive_debator 形成鲜明对比：
    → Aggressive："高风险=高回报，抓住机遇"
    → Conservative："稳健第一，控制回撤"

【保守派的核心思想】

    1. 核心理念：
       → 保护资产（Asset Protection）
       → 最小化波动（Minimize Volatility）
       → 追求稳定增长（Steady Growth）

    2. 关注风险：
       → 潜在亏损（Potential Losses）
       → 经济衰退（Economic Downturns）
       → 市场波动（Market Volatility）

    3. 思维方式：
       → "本金损失是最不可逆的"
       → "稳健的增长比大起大落更好"
       → "风险管理是长期生存的关键"

【对 Trader 策略的态度】
    Conservative 并不完全反对 Trader 的策略，
    而是关注其中的"高风险元素"，试图找出更稳健的替代方案。

    例如：
    → Trader："全仓买入，期待翻倍"
    → Conservative："考虑分批建仓，设置止损，控制单次亏损不超过 2%"

【Prompt 设计要点】
    • 强调"保护资产"而非"追求收益"
    • 要求指出 Trader 策略中的"高风险元素"
    • 提出"更谨慎的替代方案"

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


def create_conservative_debator(llm, skill_injector=None):
    if skill_injector is None:
        skill_injector = SkillInjector()
    """
    【工厂函数】创建保守风险辩论家节点

    【conservative_node 的工作流程】

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
        │   │  Step 2: 构建 Prompt（保守派视角）                              │   │
        │   │                                                               │   │
        │   │  核心任务：                                                   │   │
        │   │    • 评估 Trader 策略中的风险点                                │   │
        │   │    • 反驳 Aggressive 的"高风险=高回报"                       │   │
        │   │    • 提出更稳健的替代方案                                      │   │
        │   │    • 强调"资产保护"的重要性                                   │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                               │                                      │
        │                               ▼                                      │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 3: 更新辩论状态                                          │   │
        │   │                                                               │   │
        │   │  • 追加到 history                                             │   │
        │   │  • 追加到 conservative_history                               │   │
        │   │  • 更新 current_conservative_response                         │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                                                                       │
        └─────────────────────────────────────────────────────────────────────┘
    """

    def conservative_node(state) -> dict:
        """
        【节点函数】保守风险辩论家的核心逻辑
        """

        # ─────────────────────────────────────────────────────────────────
        # 第一步：从 state 读取辩论状态
        # ─────────────────────────────────────────────────────────────────

        risk_debate_state = state["risk_debate_state"]

        # 完整的辩论历史
        history = risk_debate_state.get("history", "")

        # 保守派自己的历史
        conservative_history = risk_debate_state.get("conservative_history", "")

        # 其他两方的最新观点（用于反驳）
        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

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
            decision_type=DecisionType.DEFENSIVE,
            existing_prompt="",
            node_name="conservative",
            debate_round=current_count or 1,
            is_counter_round=bool(current_count >= 1),
            is_adjudication=False,
        )

        # ─────────────────────────────────────────────────────────────────
        # 第五步：构建 Prompt
        # ─────────────────────────────────────────────────────────────────
        # Prompt 强调：
        # 1. 保护资产、减少波动
        # 2. 谨慎评估潜在损失
        # 3. 提出低风险的调整方案

        prompt = skill_prompt + "\n\n" + f"""As the Conservative Risk Analyst, your primary objective is to protect assets, minimize volatility, and ensure steady, reliable growth. You prioritize stability, security, and risk mitigation, carefully assessing potential losses, economic downturns, and market volatility. When evaluating the trader's decision or plan, critically examine high-risk elements, pointing out where the decision may expose the firm to undue risk and where more cautious alternatives could secure long-term gains. Here is the trader's decision:

{trader_decision}

Your task is to actively counter the arguments of the Aggressive and Neutral Analysts, highlighting where their views may overlook potential threats or fail to prioritize sustainability. Respond directly to their points, drawing from the following data sources to build a convincing case for a low-risk approach adjustment to the trader's decision:
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
Here is the current conversation history: {history} Here is the last response from the aggressive analyst: {current_aggressive_response} Here is the last response from the neutral analyst: {current_neutral_response}. If there are no responses from the other viewpoints yet, present your own argument based on the available data.

Engage by questioning their optimism and emphasizing the potential downsides they may have overlooked. Address each of their counterpoints to showcase why a conservative stance is ultimately the safest path for the firm's assets.
If Route capital quality is speculative or Route risk weight is high, explicitly prioritize liquidation risk, false breakout risk, and crowding unwind risk over upside discussion.
If Route policy role is policy_top_stock, test whether leadership status increases crowding fragility instead of reducing risk.
Focus on debating and critiquing their arguments to demonstrate the strength of a low-risk strategy over their approaches. Output conversationally as if you are speaking without any special formatting."""

        # ─────────────────────────────────────────────────────────────────
        # 第五步：调用 LLM
        # ─────────────────────────────────────────────────────────────────

        response = llm.invoke(prompt)
        response.content = enforce_execution_profile_output(response.content, execution_profile)

        skill_result = enforce_skill_usage(
            content=response.content,
            injected_skill_names=injected_skill_names,
            node_name="conservative",
            decision_type=DecisionType.DEFENSIVE.value,
            debate_round=current_count or 1,
            is_counter_round=bool(current_count >= 1),
            is_adjudication=False,
        )
        response.content = skill_result["content"]

        # 加上角色标识
        argument = f"Conservative Analyst: {response.content}"

        # ─────────────────────────────────────────────────────────────────
        # 第六步：更新辩论状态
        # ─────────────────────────────────────────────────────────────────

        new_risk_debate_state = {
            # 追加到完整历史
            "history": history + "\n" + argument,

            # 保持激进派历史不变
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),

            # 追加到保守派历史
            "conservative_history": conservative_history + "\n" + argument,

            # 保持中性派历史不变
            "neutral_history": risk_debate_state.get("neutral_history", ""),

            # 标记最新发言
            "latest_speaker": "Conservative",

            # 更新保守派最新论点
            "current_aggressive_response": risk_debate_state.get("current_aggressive_response", ""),
            "current_conservative_response": argument,
            "current_neutral_response": risk_debate_state.get("current_neutral_response", ""),

            # 辩论轮次 +1
            "count": risk_debate_state["count"] + 1,
        }

        # ─────────────────────────────────────────────────────────────────
        # 第七步：返回更新后的状态
        # ─────────────────────────────────────────────────────────────────

        return sync_risk_debate_update(
            debate_state=new_risk_debate_state,
            sender="Conservative Analyst",
        )

    return conservative_node
