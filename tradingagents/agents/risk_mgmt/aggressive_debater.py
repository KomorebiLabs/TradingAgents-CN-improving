"""
================================================================================
                    AGGRESSIVE_DEBATOR.PY 详解
                        激进风险辩论家节点
================================================================================

【模块定位】
    本文件是 TradingAgents 的"激进风险辩论家"节点。

    在风险辩论层中，aggressive_debator 与 conservative_debator 和 neutral_debator
    形成三角辩论，共同为 portfolio_manager 提供风险视角的决策依据。

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                       风险辩论层                                         │
    │                                                                           │
    │                    ┌──────────────────────┐                              │
    │                    │   Trader 的交易决策    │                              │
    │                    └──────────┬───────────┘                              │
    │                               │                                          │
    │              ┌────────────────┼────────────────┐                          │
    │              ▼                ▼                ▼                          │
    │   ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐          │
    │   │ aggressive_debator│ │neutral_debator  │ │conservative_     │          │
    │   │  (当前文件)       │ │                  │ │debator           │          │
    │   │                  │ │                  │ │                  │          │
    │   │ 角色：            │ │ 角色：           │ │ 角色：           │          │
    │   │ 高风险高回报      │ │ 中性平衡          │ │ 低风险稳定        │          │
    │   │                  │ │                  │ │                  │          │
    │   │ 核心观点：        │ │ 核心观点：        │ │ 核心观点：       │          │
    │   │ "高风险=高回报"   │ │ "中庸之道"        │ │ "稳健第一"       │          │
    │   │ "抓住机遇"        │ │ "权衡利弊"        │ │ "控制回撤"       │          │
    │   └──────────────────┘ └──────────────────┘ └──────────────────┘          │
    │              │                │                │                       │
    │              └────────────────┼────────────────┘                       │
    │                               ▼                                         │
    │                    ┌──────────────────────┐                              │
    │                    │  portfolio_manager   │                              │
    │                    │  综合三方观点做决策    │                              │
    │                    └──────────────────────┘                              │
    │                                                                           │
    └─────────────────────────────────────────────────────────────────────────┘

【aggressive_debator 的核心特质】

    1. 关注点：
       → 潜在上涨空间（upside potential）
       → 成长机会（growth opportunities）
       → 竞争优势（competitive advantages）

    2. 思维方式：
       → "高风险伴随高回报"
       → "过于保守会错失良机"
       → "创新和冒险是超额收益的来源"

    3. 对 trader_plan 的态度：
       → 支持 Trader 提出的激进策略
       → 反驳 Conservative 的谨慎观点
       → 挑战 Neutral 的"骑墙"立场

【输入数据】

    • trader_investment_plan → Trader 提出的交易建议
    • 4位分析师的报告 → 市场/新闻/基本面/情绪分析
    • risk_debate_state → 辩论历史（包含其他辩论家的观点）

【输出】

    • 更新 risk_debate_state
    • 追加 aggressive_history
    • 更新 current_aggressive_response

================================================================================
"""

from tradingagents.agents.utils.state_helpers import (
    determine_risk_next_stage,
    sync_risk_debate_update,
)
from tradingagents.agents.utils.agent_utils import (
    build_conclusion_template_instruction,
    enforce_execution_profile_output,
    build_screener_semantic_instruction,
    build_semantic_execution_profile,
    enforce_skill_usage,
)
from tradingagents.harness.skills.injector import SkillInjector
from tradingagents.harness.skills.types import DecisionType


def create_aggressive_debater(llm, skill_injector=None):
    if skill_injector is None:
        skill_injector = SkillInjector()
    """
    【工厂函数】创建激进风险辩论家节点

    【aggressive_node 的工作流程】

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
        │   │  Step 2: 构建 Prompt（激进派视角）                              │   │
        │   │                                                               │   │
        │   │  核心任务：                                                   │   │
        │   │    • 支持 Trader 的激进策略                                    │   │
        │   │    • 反驳 Conservative 的谨慎观点                              │   │
        │   │    • 挑战 Neutral 的"中庸"立场                                 │   │
        │   │    • 强调"高风险=高回报"                                       │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                               │                                      │
        │                               ▼                                      │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 3: 更新辩论状态                                          │   │
        │   │                                                               │   │
        │   │  • 追加到 history                                             │   │
        │   │  • 追加到 aggressive_history                                  │   │
        │   │  • 更新 current_aggressive_response                          │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                                                                       │
        └─────────────────────────────────────────────────────────────────────┘
    """

    def aggressive_node(state) -> dict:
        """
        【节点函数】激进风险辩论家的核心逻辑
        """

        # ─────────────────────────────────────────────────────────────────
        # 第一步：从 state 读取辩论状态
        # ─────────────────────────────────────────────────────────────────

        risk_debate_state = state["risk_debate_state"]

        # 完整的辩论历史
        history = risk_debate_state.get("history", "")

        # 激进派自己的历史
        aggressive_history = risk_debate_state.get("aggressive_history", "")

        # 其他两方的最新观点（用于反驳）
        current_conservative_response = risk_debate_state.get("current_conservative_response", "")
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
        # 这是辩论的核心对象：
        # Aggressive 支持 Trader 的激进策略
        # Conservative 认为 Trader 过于激进
        # Neutral 试图找出折中方案

        trader_decision = state["trader_investment_plan"]
        compression_notes = state.get("orchestration", {}).get("compression_notes", "")
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
            decision_type=DecisionType.OFFENSIVE,
            existing_prompt="",
            node_name="aggressive",
            debate_round=current_count or 1,
            is_counter_round=bool(current_count >= 1),
            is_adjudication=False,
        )

        # ─────────────────────────────────────────────────────────────────
        # 第五步：构建 Prompt
        # ─────────────────────────────────────────────────────────────────
        # Prompt 强调：
        # 1. 支持 Trader 的高风险高回报策略
        # 2. 反驳 Conservative 和 Neutral 的谨慎观点
        # 3. 强调"抓住机遇"而非"规避风险"
        # 4. 用数据支持激进立场

        prompt = skill_prompt + "\n\n" + f"""As the Aggressive Risk Analyst, your role is to actively champion high-reward, high-risk opportunities, emphasizing bold strategies and competitive advantages. When evaluating the trader's decision or plan, focus intently on the potential upside, growth potential, and innovative benefits—even when these come with elevated risk. Use the provided market data and sentiment analysis to strengthen your arguments and challenge the opposing views. Specifically, respond directly to each point made by the conservative and neutral analysts, countering with data-driven rebuttals and persuasive reasoning. Highlight where their caution might miss critical opportunities or where their assumptions may be overly conservative. Here is the trader's decision:

{trader_decision}

Your task is to create a compelling case for the trader's decision by questioning and critiquing the conservative and neutral stances to demonstrate why your high-reward perspective offers the best path forward. Incorporate insights from the following sources into your arguments:

Compressed handoff notes from prior stage: {compression_notes}
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
Here is the current conversation history: {history} Here are the last arguments from the conservative analyst: {current_conservative_response} Here are the last arguments from the neutral analyst: {current_neutral_response}. If there are no responses from the other viewpoints yet, present your own argument based on the available data.

Engage actively by addressing any specific concerns raised, refuting the weaknesses in their logic, and asserting the benefits of risk-taking to outpace market norms. Maintain a focus on debating and persuading, not just presenting data. Challenge each counterpoint to underscore why a high-risk approach is optimal.
If Route risk weight is high, keep the argument concise and directly defend only the highest-upside thesis that survives obvious risk checks.
If Route policy role is policy_top_stock, explicitly explain why leadership continuation can justify tactical aggression.
Output conversationally as if you are speaking without any special formatting."""

        # ─────────────────────────────────────────────────────────────────
        # 第六步：调用 LLM
        # ─────────────────────────────────────────────────────────────────

        response = llm.invoke(prompt)
        response.content = enforce_execution_profile_output(response.content, execution_profile)

        skill_result = enforce_skill_usage(
            content=response.content,
            injected_skill_names=injected_skill_names,
            node_name="aggressive",
            decision_type=DecisionType.OFFENSIVE.value,
            debate_round=current_count or 1,
            is_counter_round=bool(current_count >= 1),
            is_adjudication=False,
        )
        response.content = skill_result["content"]

        # 加上角色标识
        argument = f"Aggressive Analyst: {response.content}"

        # ─────────────────────────────────────────────────────────────────
        # 第七步：更新辩论状态
        # ─────────────────────────────────────────────────────────────────

        new_risk_debate_state = {
            # 追加到完整历史
            "history": history + "\n" + argument,

            # 追加到激进派历史
            "aggressive_history": aggressive_history + "\n" + argument,

            # 保持其他两方历史不变
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),

            # 标记最新发言
            "latest_speaker": "Aggressive",

            # 更新激进派最新论点（供其他方反驳）
            "current_aggressive_response": argument,
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": risk_debate_state.get("current_neutral_response", ""),

            # 辩论轮次 +1
            "count": risk_debate_state["count"] + 1,
        }

        # ─────────────────────────────────────────────────────────────────
        # 第八步：返回更新后的状态
        # ─────────────────────────────────────────────────────────────────

        update = sync_risk_debate_update(
            debate_state=new_risk_debate_state,
            sender="Aggressive Analyst",
        )
        orchestration = dict(state.get("orchestration", {}))
        orchestration["next_stage"] = determine_risk_next_stage(
            risk_history=new_risk_debate_state["history"],
            latest_argument=argument,
            compression_notes=compression_notes,
        )
        update["orchestration"] = orchestration
        return update

    return aggressive_node
