"""
================================================================================
                         TRADER.PY 详解
                            交易员节点
================================================================================

【模块定位】
    本文件是 TradingAgents 的"交易员"节点，位于 Research Manager 之后、风险辩论之前。

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         工作流中的位置                                     │
    │                                                                           │
    │   4位分析师 → Bull/Bear辩论 → Research Manager                           │
    │                                    │                                      │
    │                                    ▼                                      │
    │                              trader（当前文件）                            │
    │                                    │                                      │
    │                                    ▼                                      │
    │   3位风险辩论家（Aggressive/Conservative/Neutral）                        │
    │                                    │                                      │
    │                                    ▼                                      │
    │                          portfolio_manager                               │
    │                                                                           │
    └─────────────────────────────────────────────────────────────────────────┘

【trader 的职责】
    在 Research Manager 给出投资计划后，
    将计划转化为具体的交易建议（买入/持有/卖出）。

    trader 不做分析（那是分析师和研究员的事），
    只做决策：根据信息给出明确的交易方向。

【与 research_manager 的区别】

    ┌─────────────────┬─────────────────────────────┬─────────────────────────────┐
    │      维度        │     research_manager        │         trader             │
    ├─────────────────┼─────────────────────────────┼─────────────────────────────┤
    │   输入           │   Bull/Bear 的辩论          │   研究经理的投资计划        │
    │   输出           │   investment_plan           │   trader_investment_plan   │
    │   任务           │   综合多空，定方向          │   给出具体交易决策          │
    │   关注点         │   "方向"（买/卖/观望）       │   "行动"（买多少/怎么买）   │
    └─────────────────┴─────────────────────────────┴─────────────────────────────┘

【Prompt 设计要点】

    1. 强调"最终交易建议"：
       → 必须以 "FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**" 结尾
       → 这是整个系统停下来等待 portfolio_manager 的信号

    2. 包含 past_memories：
       → 参考过去的交易经验
       → 避免重复同样的错误

    3. 不需要工具：
       → trader 是"纯决策者"
       → 所有需要的数据都在 state 中

【functools.partial 的使用】

    create_trader(llm, memory) 返回的是：
        functools.partial(trader_node, name="Trader")

    这是为了让 LangGraph 能够正确识别节点的名称。
    在工作流图中，节点需要有名称来标识。

================================================================================
"""

import functools

from tradingagents.agents.prompts import TRADER_FEW_SHOTS, build_xml_decision_prompt
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    build_conclusion_template_instruction,
    enforce_execution_profile_output,
    build_screener_semantic_instruction,
    build_semantic_execution_profile,
    enforce_skill_usage,
)
from tradingagents.agents.utils.state_helpers import (
    determine_trader_next_stage,
    sync_decision_updates,
)
from tradingagents.harness.skills.injector import SkillInjector
from tradingagents.harness.skills.types import DecisionType


def create_trader(llm, memory, skill_injector=None):
    if skill_injector is None:
        skill_injector = SkillInjector()
    """
    【工厂函数】创建交易员节点

    【trader_node 的工作流程】

        ┌─────────────────────────────────────────────────────────────────────┐
        │                                                                       │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 1: 收集输入                                                │   │
        │   │                                                               │   │
        │   │  输入来源：                                                    │   │
        │   │    • state["company_of_interest"]    → 分析的公司              │   │
        │   │    • state["investment_plan"]        → 研究经理的计划          │   │
        │   │    • 4位分析师的报告                   → 分析依据              │   │
        │   │    • memory.get_memories()           → 历史经验               │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                               │                                      │
        │                               ▼                                      │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 2: 构建 Prompt（交易决策）                                │   │
        │   │                                                               │   │
        │   │  核心任务：                                                   │   │
        │   │    • 基于分析师报告和研究经理的计划                            │   │
        │   │    • 做出明确的交易决策（买/持/卖）                            │   │
        │   │    • 必须以 FINAL TRANSACTION PROPOSAL 结尾                    │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                               │                                      │
        │                               ▼                                      │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 3: 输出                                                  │   │
        │   │                                                               │   │
        │   │  {                                                           │   │
        │   │      "messages": [result],              // LLM 回复            │   │
        │   │      "trader_investment_plan": result.content, // 交易建议    │   │
        │   │      "sender": "Trader"                 // 发送者标识        │   │
        │   │  }                                                           │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                                                                       │
        └─────────────────────────────────────────────────────────────────────┘

    【为什么用 functools.partial？】

        LangGraph 在工作流图中需要给节点命名。
        但节点函数本身是动态生成的（由工厂函数创建）。
        functools.partial 可以"冻结"参数，同时保留节点的标识。

        效果：
        → trader_node 现在有了默认参数 name="Trader"
        → LangGraph 可以用 name="Trader" 来标识这个节点
    """

    def trader_node(state, name):
        """
        【节点函数】交易员的核心逻辑

        【参数详解】

            state: AgentState，包含完整的工作流状态
            name: 节点名称（由 functools.partial 注入）
        """

        # ─────────────────────────────────────────────────────────────────
        # 第一步：从 state 读取上下文
        # ─────────────────────────────────────────────────────────────────

        company_name = state["company_of_interest"]
        instrument_context = build_instrument_context(company_name)
        compression_notes = state.get("orchestration", {}).get("compression_notes", "")
        semantic_instruction = build_screener_semantic_instruction(state, "trader")
        execution_profile = build_semantic_execution_profile(state, "trader")
        route_decision = state.get("route_decision", {}) or state.get("screener_context", {}).get("route_decision", {}) or {}
        policy_role = str(route_decision.get("policy_role", "") or "none")
        capital_quality = str(route_decision.get("capital_quality", "") or "none")
        debate_risk_weight = str(route_decision.get("debate_risk_weight", "") or "normal")
        conclusion_mode = str(execution_profile.get("conclusion_mode", "standard"))
        conclusion_template_instruction = build_conclusion_template_instruction(conclusion_mode)
        style = str(execution_profile.get("response_style", "balanced"))
        must_include = execution_profile.get("evidence_must_include", []) or []
        trader_role_instruction = ""
        if capital_quality == "capital_quality_speculative" or debate_risk_weight == "high":
            trader_role_instruction = (
                " Default to tactical sizing, fast invalidation, and explicit exit conditions unless evidence is unusually strong."
            )
        elif policy_role == "policy_top_stock":
            trader_role_instruction = (
                " Treat this as a potential board-leadership continuation setup and judge whether leadership persistence justifies a cleaner execution plan."
            )

        # ─────────────────────────────────────────────────────────────────
        # 第二步：读取研究经理的投资计划
        # ─────────────────────────────────────────────────────────────────
        # investment_plan 是 research_manager 的输出
        # 包含：投资方向、理由、具体行动计划

        investment_plan = state["investment_plan"]

        # ─────────────────────────────────────────────────────────────────
        # 第三步：读取分析师报告（作为决策依据）
        # ─────────────────────────────────────────────────────────────────

        market_research_report = state["market_report"]         # 市场技术分析
        sentiment_report = state["sentiment_report"]             # 社交媒体情绪
        news_report = state["news_report"]                     # 新闻分析
        fundamentals_report = state["fundamentals_report"]       # 基本面分析

        # ─────────────────────────────────────────────────────────────────
        # 第四步：从记忆系统获取历史经验
        # ─────────────────────────────────────────────────────────────────

        curr_situation = (
            f"{market_research_report}\n\n"
            f"{sentiment_report}\n\n"
            f"{news_report}\n\n"
            f"{fundamentals_report}"
        )
        past_memories = memory.get_memories(
            curr_situation,
            n_matches=execution_profile.get("memory_n_matches", 2),
        )

        # 格式化历史经验
        past_memory_str = ""
        if past_memories:
            for rec in past_memories:
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            past_memory_str = "No past memories found."

        # ─────────────────────────────────────────────────────────────────
        # 第五步：注入 Skills
        # ─────────────────────────────────────────────────────────────────

        skill_prompt, injected_skill_names = skill_injector.inject(
            decision_type=DecisionType.OFFENSIVE,
            existing_prompt="",
            node_name="trader",
            debate_round=1,
            is_counter_round=False,
            is_adjudication=False,
        )

        # ─────────────────────────────────────────────────────────────────
        # 第六步：构建消息结构
        # ─────────────────────────────────────────────────────────────────
        # 与其他节点不同，trader 使用 ChatML 格式的消息列表
        # 而不是 LangChain 的 MessagesPlaceholder

        # user 消息：包含公司信息、投资计划、分析报告
        context = {
            "role": "user",
            "content": (
                f"Based on a comprehensive analysis by a team of analysts, here is an investment plan tailored for {company_name}. "
                f"{instrument_context} "
                f"Compressed handoff notes from prior stage: {compression_notes}\n\n"
                f"Screener semantic routing guidance: {semantic_instruction}\n\n"
                f"Semantic execution profile: {execution_profile}\n\n"
                f"Execution style: {style}; conclusion_mode={conclusion_mode}; required evidence={must_include}\n\n"
                f"{conclusion_template_instruction}\n\n"
                f"Route context: policy_role={policy_role}, capital_quality={capital_quality}, debate_risk_weight={debate_risk_weight}\n\n"
                f"This plan incorporates insights from current technical market trends, macroeconomic indicators, and social media sentiment. "
                f"Use this plan as a foundation for evaluating your next trading decision.\n\n"
                f"Proposed Investment Plan: {investment_plan}\n\n"
                f"Leverage these insights to make an informed and strategic decision."
            ),
        }

        # ── P4 Memory: Inject historical context ───────────────────────────────
        historical_context = state.get("historical_context")
        if historical_context:
            dims = historical_context.get("dimensions", {})
            dim_str = "; ".join(f"{k}={v}" for k, v in dims.items()) if dims else "N/A"
            historical_context_str = (
                f"\n\n[Historical Context — {historical_context.get('trade_date', '')} "
                f"({historical_context.get('confidence', '')}置信度)]\n"
                f"上一轮分析结论: {historical_context.get('summary', 'N/A')}\n"
                f"策略维度: {dim_str}\n"
                f"最终决策: {historical_context.get('final_decision', 'N/A')}\n"
                f"关键理由: {'; '.join(historical_context.get('key_reasons', [])[:3])}\n"
                f"风险提示: {'; '.join(historical_context.get('risks', [])[:2])}\n"
            )
            context["content"] += historical_context_str

        # system 消息：定义交易员的角色和输出要求
        messages = [
            {
                "role": "system",
                "content": (
                    build_xml_decision_prompt(
                        role_definition=skill_prompt + "\n\n" + (
                            "You are a trading agent converting research output into an actionable trade plan."
                            " Balance conviction, timing, position sizing, and risk control."
                            f"{trader_role_instruction}"
                        ),
                        task_instructions=(
                            "Make a specific recommendation to buy, sell, or hold."
                            " Conclude the actionable recommendation inside <decision> and include"
                            " the exact phrase FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** there."
                            f" Apply this Screener semantic routing guidance: {semantic_instruction}"
                            f" Apply this execution profile: {execution_profile}"
                            f" Apply lessons from past decisions: {past_memory_str}"
                        ),
                        few_shot_examples=TRADER_FEW_SHOTS,
                    )
                ),
            },
            context,
        ]

        # ─────────────────────────────────────────────────────────────────
        # 第六步：调用 LLM
        # ─────────────────────────────────────────────────────────────────

        # 注意：直接调用 llm.invoke()，不使用 LCEL 链
        # 因为 trader 不需要工具调用
        result = llm.invoke(messages)
        result.content = enforce_execution_profile_output(result.content, execution_profile)

        skill_result = enforce_skill_usage(
            content=result.content,
            injected_skill_names=injected_skill_names,
            node_name="trader",
            decision_type=DecisionType.OFFENSIVE.value,
            debate_round=1,
            is_counter_round=False,
            is_adjudication=False,
        )
        result.content = skill_result["content"]

        # ─────────────────────────────────────────────────────────────────
        # 第七步：返回更新后的状态
        # ─────────────────────────────────────────────────────────────────

        update = sync_decision_updates(
            decision_key="trader_plan",
            decision_value=result.content,
            sender=name,
        )
        orchestration = dict(state.get("orchestration", {}))
        orchestration["next_stage"] = determine_trader_next_stage(
            investment_plan=investment_plan,
            trader_output=result.content,
            compression_notes=compression_notes,
        )
        update["orchestration"] = orchestration
        update["messages"] = [result]

        # Append skill audit entry to update dict
        audit_entry = skill_result["audit_entry"]
        if audit_entry:
            update.setdefault("skill_audit_trail", {})
            update["skill_audit_trail"].setdefault("trader", []).append(audit_entry)

        return update

    # 返回绑定了 name="Trader" 的节点函数
    return functools.partial(trader_node, name="Trader")
