"""
================================================================================
                   RESEARCH_MANAGER.PY 详解
                        研究经理节点（裁判）
================================================================================

【模块定位】
    本文件是 TradingAgents 的"研究经理"节点，位于多空辩论层之后。

    研究经理的角色是"裁判"：
    → 听取 Bull 和 Bear 的辩论
    → 综合双方论点
    → 做出最终的投资方向决策

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         工作流中的位置                                     │
    │                                                                           │
    │         ┌──────────────────────────────────────────┐                  │
    │         │       Bull/Bear 辩论层（N 轮）            │                  │
    │         │                                          │                  │
    │         │  Bull ←─────────────────────────────→ Bear│                  │
    │         └──────────────────────┬───────────────────┘                  │
    │                              │                                          │
    │                              ▼                                          │
    │         ┌──────────────────────────────────────────┐                  │
    │         │         research_manager（当前文件）         │                  │
    │         │              裁判：汇总辩论                 │                  │
    │         └──────────────────────┬───────────────────┘                  │
    │                              │                                          │
    │                              ▼                                          │
    │                              trader                                     │
    │                                                                           │
    └─────────────────────────────────────────────────────────────────────────┘

【research_manager 的职责】

    1. 汇总辩论要点：
       → 总结 Bull 和 Bear 的核心论点
       → 找出最具说服力的证据

    2. 做出决策：
       → Buy / Sell / Hold
       → 不允许"两边都有道理所以 Hold"
       → 必须有明确的立场

    3. 制定投资计划：
       → 给出具体的行动计划
       → 包括战略步骤（Strategic Actions）

【与 portfolio_manager 的区别】

    ┌─────────────────┬─────────────────────────────┬─────────────────────────────┐
    │      维度        │     research_manager        │    portfolio_manager       │
    ├─────────────────┼─────────────────────────────┼─────────────────────────────┤
    │   关注点         │   投资方向（买/卖/观望）      │   风险权衡（仓位/时机）      │
    │   辩论对手       │   Bull vs Bear（方向之争）   │   三种风险偏好（程度之争）   │
    │   输出           │   investment_plan（投资计划） │   final_trade_decision    │
    │   问题           │   "应该投吗？"              │   "投多少？怎么投？"        │
    └─────────────────┴─────────────────────────────┴─────────────────────────────┘

【Prompt 设计要点】

    1. 强调"决策"而非"总结"：
       → 不是"双方都有道理"
       → 而是"我站在哪边，为什么"

    2. 要求制定详细计划：
       → Recommendation（推荐）
       → Rationale（理由）
       → Strategic Actions（战略行动）

    3. 参考 past_memories：
       → 从历史错误中学习
       → 避免重复同样的判断失误

【为什么不需要工具？】

    research_manager 不调用任何工具（Tools）。
    它只是"裁判"，所有需要的数据（分析师报告、辩论历史）
    都已经存在于 state 中。

    这体现了角色分工：
    → 分析师：获取数据
    → 研究员：辩论
    → 研究经理：裁判（不获取新数据）

================================================================================
"""

from tradingagents.agents.prompts import build_xml_decision_prompt
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    build_conclusion_template_instruction,
    enforce_execution_profile_output,
    build_screener_semantic_instruction,
    build_semantic_execution_profile,
    enforce_skill_usage,
)
from tradingagents.agents.utils.state_helpers import (
    determine_research_manager_next_stage,
    sync_decision_updates,
)
from tradingagents.harness.skills.injector import SkillInjector
from tradingagents.harness.skills.types import DecisionType


def create_research_manager(llm, memory, skill_injector=None):
    if skill_injector is None:
        skill_injector = SkillInjector()
    """
    【工厂函数】创建研究经理节点

    【参数】
        llm: 快速思考模型
        memory: 记忆系统

    【返回值】
        research_manager_node: 可调用的节点函数
    """

    def research_manager_node(state) -> dict:
        """
        【节点函数】研究经理的核心逻辑

        【工作流程】

            ┌─────────────────────────────────────────────────────────────────┐
            │                                                                       │
            │   Step 1: 读取辩论历史                                               │
            │   • investment_debate_state["history"]                              │
            │   → Bull 和 Bear 的所有辩论记录                                      │
            │                                                                       │
            └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
            ┌─────────────────────────────────────────────────────────────────┐
            │                                                                       │
            │   Step 2: 读取分析师报告                                               │
            │   • 4 份报告（市场/情绪/新闻/基本面）                               │
            │   → 提供决策的背景信息                                               │
            │                                                                       │
            └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
            ┌─────────────────────────────────────────────────────────────────┐
            │                                                                       │
            │   Step 3: 从 memory 获取历史经验                                      │
            │   • past_memories                                                  │
            │   → 从过去的判断中学习                                               │
            │                                                                       │
            └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
            ┌─────────────────────────────────────────────────────────────────┐
            │                                                                       │
            │   Step 4: 构建 Prompt（裁判视角）                                    │
            │   • 总结双方论点                                                    │
            │   • 做出明确决策（Buy/Sell/Hold）                                   │
            │   • 制定投资计划                                                    │
            │                                                                       │
            └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
            ┌─────────────────────────────────────────────────────────────────┐
            │                                                                       │
            │   Step 5: 返回更新后的状态                                           │
            │   • investment_debate_state["judge_decision"]                       │
            │   • investment_plan                                                │
            │                                                                       │
            └─────────────────────────────────────────────────────────────────┘

        【返回值详解】

            返回两个字段：

            1. investment_debate_state: new_investment_debate_state
               → 添加裁判的决策到辩论状态
               → 供后续审计/日志使用

            2. investment_plan: response.content
               → 研究经理的投资计划
               → 传递给 trader 节点做交易决策

        """

        # ─────────────────────────────────────────────────────────────────
        # 第一步：从 state 读取上下文
        # ─────────────────────────────────────────────────────────────────

        instrument_context = build_instrument_context(state["company_of_interest"])
        compression_notes = state.get("orchestration", {}).get("compression_notes", "")
        semantic_instruction = build_screener_semantic_instruction(state, "research_manager")
        execution_profile = build_semantic_execution_profile(state, "research_manager")
        route_decision = state.get("route_decision", {}) or state.get("screener_context", {}).get("route_decision", {}) or {}
        policy_role = str(route_decision.get("policy_role", "") or "none")
        capital_quality = str(route_decision.get("capital_quality", "") or "none")
        conflict_tier = str(route_decision.get("conflict_tier", "") or "none")
        manager_role_instruction = ""
        if conflict_tier in {"high", "severe"}:
            manager_role_instruction = " Explicitly resolve the strongest contradiction before recommending action."
        elif policy_role == "policy_top_stock":
            manager_role_instruction = " Require an explicit verdict on whether this name is a genuine concept-board leader."

        # ─────────────────────────────────────────────────────────────────
        # 第二步：读取辩论状态
        # ─────────────────────────────────────────────────────────────────

        # investment_debate_state 是辩论子状态
        # 包含辩论历史、各方发言、轮次等
        investment_debate_state = state["investment_debate_state"]

        # history: Bull 和 Bear 的所有辩论发言
        history = investment_debate_state.get("history", "")

        # ─────────────────────────────────────────────────────────────────
        # 第三步：读取分析师报告
        # ─────────────────────────────────────────────────────────────────

        market_research_report = state["market_report"]           # 市场技术分析
        sentiment_report = state["sentiment_report"]             # 社交媒体情绪
        news_report = state["news_report"]                       # 新闻分析
        fundamentals_report = state["fundamentals_report"]       # 基本面分析

        # ─────────────────────────────────────────────────────────────────
        # 第四步：从记忆系统获取历史经验
        # ─────────────────────────────────────────────────────────────────

        curr_situation = f"""
            {market_research_report}
            {sentiment_report}
            {news_report}
            {fundamentals_report}
        """

        past_memories = memory.get_memories(
            curr_situation,
            n_matches=execution_profile.get("memory_n_matches", 2),
        )

        past_memory_str = ""
        for rec in past_memories:
            past_memory_str += rec["recommendation"] + "\n\n"
        max_context_chars = int(execution_profile.get("max_context_chars", 3200) or 3200)
        style = str(execution_profile.get("response_style", "balanced"))
        must_include = execution_profile.get("evidence_must_include", []) or []
        conclusion_mode = str(execution_profile.get("conclusion_mode", "standard"))
        conclusion_template_instruction = build_conclusion_template_instruction(conclusion_mode)
        if len(history) > max_context_chars:
            history = history[-max_context_chars:]

        # ─────────────────────────────────────────────────────────────────
        # 第五步：注入 Skills
        # ─────────────────────────────────────────────────────────────────

        current_count = investment_debate_state["count"]
        skill_prompt, injected_skill_names = skill_injector.inject(
            decision_type=DecisionType.VALUATION,
            existing_prompt="",
            node_name="research_manager",
            debate_round=current_count or 1,
            is_counter_round=False,
            is_adjudication=True,
        )

        # ─────────────────────────────────────────────────────────────────
        # 第六步：构建 Prompt（裁判视角）
        # ─────────────────────────────────────────────────────────────────
        # Prompt 强调：
        # 1. 总结双方论点
        # 2. 做出明确决策（不骑墙）
        # 3. 制定投资计划
        # 4. 参考历史经验

        confidence_instruction = ""
        if state.get("orchestration", {}).get("enable_confidence_score"):
            confidence_instruction = (
                " Add a confidence line inside <decision> as Confidence: N/100 with one brief justification."
            )

        prompt = build_xml_decision_prompt(
            role_definition=skill_prompt + "\n\n" + (
                "You are the Research Manager and debate facilitator."
                " Your job is to resolve the bull/bear dispute with a clear investment stance."
                f"{manager_role_instruction}"
            ),
            task_instructions=(
                f"{instrument_context}\n\n"
                f"Compressed handoff notes from prior stage:\n{compression_notes}\n\n"
                f"Screener semantic routing guidance:\n{semantic_instruction}\n\n"
                f"Semantic execution profile: {execution_profile}\n\n"
                f"Execution style: {style}; required evidence: {must_include}\n\n"
                f"{conclusion_template_instruction}\n\n"
                f"Route context: policy_role={policy_role}, capital_quality={capital_quality}, conflict_tier={conflict_tier}\n\n"
                f"Past reflections on mistakes:\n{past_memory_str}\n\n"
                f"Debate history:\n{history}\n\n"
                "In <analysis>, summarize the strongest bull and bear evidence and explain which side is stronger.\n"
                "In <decision>, provide a decisive Buy / Sell / Hold recommendation, rationale, and strategic actions for the trader."
                " Avoid defaulting to Hold unless it is strongly justified."
                f"{confidence_instruction}"
            ),
        )

        # ─────────────────────────────────────────────────────────────────
        # 第八步：调用 LLM
        # ─────────────────────────────────────────────────────────────────
        # 直接调用 llm.invoke()，不使用工具绑定
        # research_manager 是裁判，不需要获取新数据

        response = llm.invoke(prompt)
        response.content = enforce_execution_profile_output(response.content, execution_profile)

        skill_result = enforce_skill_usage(
            content=response.content,
            injected_skill_names=injected_skill_names,
            node_name="research_manager",
            decision_type=DecisionType.VALUATION.value,
            debate_round=current_count or 1,
            is_counter_round=False,
            is_adjudication=True,
        )
        response.content = skill_result["content"]

        # ─────────────────────────────────────────────────────────────────
        # 第七步：更新辩论状态
        # ─────────────────────────────────────────────────────────────────

        new_investment_debate_state = {
            # 裁判的决策（供审计/日志）
            "judge_decision": response.content,

            # 保持辩论历史不变
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),

            # 裁判的当前回复（不用于后续流程，但记录）
            "current_response": response.content,

            # 辩论轮次（不增加，由辩论层控制）
            "count": investment_debate_state["count"],
        }

        # ─────────────────────────────────────────────────────────────────
        # 第八步：返回更新后的状态
        # ─────────────────────────────────────────────────────────────────

        update = sync_decision_updates(
            decision_key="investment_plan",
            decision_value=response.content,
            sender="Research Manager",
        )
        orchestration = dict(state.get("orchestration", {}))
        orchestration["next_stage"] = determine_research_manager_next_stage(
            debate_history=history,
            manager_decision=response.content,
            compression_notes=compression_notes,
        )
        update["orchestration"] = orchestration
        update["investment_debate_state"] = new_investment_debate_state
        update["debate_blocks"] = {"investment": new_investment_debate_state}
        return update

    return research_manager_node
