"""
================================================================================
                     PORTFOLIO_MANAGER.PY 详解
                         投资组合经理节点
================================================================================

【模块定位】
    本文件是 TradingAgents 的"投资组合经理"节点，位于工作流的最后阶段。

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         工作流中的位置                                     │
    │                                                                           │
    │   4位分析师 → Bull/Bear辩论 → Research Manager → Trader                  │
    │                                                           │              │
    │                                                           ▼              │
    │                               3位风险辩论家（Aggressive/Conservative/Neutral）│
    │                                                           │              │
    │                                                           ▼              │
    │                          portfolio_manager（当前文件）→ 最终决策          │
    │                                                                           │
    └─────────────────────────────────────────────────────────────────────────┘

【portfolio_manager 的职责】
    在风险辩论结束后，综合三方（激进/保守/中性）观点，
    做出最终的投资决策。

    决策尺度（Rating Scale）：
    ┌─────────────────────────────────────────────────────────────────────────┐
    │  评级             │  含义                                                 │
    ├──────────────────┼──────────────────────────────────────────────────────┤
    │  Buy             │  强烈建议买入或加仓                                    │
    │  Overweight      │  看好，逐步增加仓位                                    │
    │  Hold            │  维持现有仓位，不操作                                  │
    │  Underweight     │  看淡，减仓获利了结                                    │
    │  Sell            │  建议清仓或回避                                        │
    └─────────────────────────────────────────────────────────────────────────┘

【与 research_manager 的区别】
    ┌─────────────────┬─────────────────────────────┬─────────────────────────────┐
    │      维度        │     research_manager        │    portfolio_manager       │
    ├─────────────────┼─────────────────────────────┼─────────────────────────────┤
    │   关注点         │   投资方向（买/卖/观望）      │   风险权衡（仓位/时机）      │
    │   辩论对手       │   Bull vs Bear（方向之争）   │   三种风险偏好（程度之争）   │
    │   输出           │   investment_plan（投资计划） │   final_trade_decision    │
    │   问题           │   "应该投吗？"              │   "投多少？怎么投？"        │
    └─────────────────┴─────────────────────────────┴─────────────────────────────┘

【Prompt 设计要点】

    1. Rating Scale 必须五选一：
       → 不是"看情况"，而是"必须有立场"
       → 避免"骑墙"式的模糊结论

    2. 必须输出三部分：
       → Rating（评级）：Buy/Overweight/Hold/Underweight/Sell
       → Executive Summary（执行摘要）：简洁的行动计划
       → Investment Thesis（投资论点）：基于辩论的详细推理

    3. 参考 past_memories：
       → 过去的决策经验（记忆系统）
       → "以史为鉴"

================================================================================
"""

from tradingagents.agents.prompts import build_xml_decision_prompt
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    build_conclusion_template_instruction,
    enforce_execution_profile_output,
    build_semantic_execution_profile,
    build_screener_semantic_instruction,
    get_language_instruction,
    get_segment_advisory,
    enforce_skill_usage,
)
from tradingagents.agents.utils.state_helpers import sync_decision_updates
from tradingagents.harness.skills.injector import SkillInjector
from tradingagents.harness.skills.types import DecisionType


def create_portfolio_manager(llm, memory, skill_injector=None):
    if skill_injector is None:
        skill_injector = SkillInjector()
    """
    【工厂函数】创建投资组合经理节点

    【portfolio_manager_node 的工作流程】

        ┌─────────────────────────────────────────────────────────────────────┐
        │                                                                       │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 1: 收集所有输入                                          │   │
        │   │                                                               │   │
        │   │  输入来源：                                                    │   │
        │   │    • risk_debate_state["history"]    → 风险辩论历史             │   │
        │   │    • state["investment_plan"]        → 研究经理的投资计划       │   │
        │   │    • state["trader_investment_plan"] → 交易员的交易建议       │   │
        │   │    • memory.get_memories()           → 过去的决策经验           │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                               │                                      │
        │                               ▼                                      │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 2: 综合判断                                              │   │
        │   │                                                               │   │
        │   │  任务：                                                      │   │
        │   │    • 评估三方的论点                                            │   │
        │   │    • 决定最终评级（Buy/Hold/Sell 等）                          │   │
        │   │    • 给出具体的行动计划                                        │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                               │                                      │
        │                               ▼                                      │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 3: 输出                                                  │   │
        │   │                                                               │   │
        │   │  {                                                           │   │
        │   │      "final_trade_decision": "...",   // 最终决策             │   │
        │   │      "risk_debate_state": {...}       // 更新辩论状态         │   │
        │   │  }                                                           │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                                                                       │
        └─────────────────────────────────────────────────────────────────────┘

    【为什么不使用工具？】

        portfolio_manager 是"决策者"而非"数据收集者"。
        它不做任何工具调用，只做综合判断。

        对比：
        • 分析师节点：使用工具获取数据，生成报告
        • bull/bear_researcher：辩论双方
        • risk_debator：评估风险
        • portfolio_manager：不获取数据，直接决策

        这是角色分工的体现：每个节点做自己该做的事。

    【memory 的使用】

        memory.get_memories(curr_situation, n_matches=2)
        → 从记忆系统中获取最相似的 2 条历史经验
        → 帮助避免重复犯错

        什么样的情况算"相似"？
        → 记忆系统在存储时会计算"语义相似度"
        → 当前情况与过去情况的向量相似 → 匹配
    """

    def portfolio_manager_node(state) -> dict:
        """
        【节点函数】投资组合经理的核心逻辑
        """

        # ─────────────────────────────────────────────────────────────────
        # 第一步：从 state 读取上下文
        # ─────────────────────────────────────────────────────────────────

        instrument_context = build_instrument_context(state["company_of_interest"])
        segment_advisory = get_segment_advisory(state["company_of_interest"], "risk")
        compression_notes = state.get("orchestration", {}).get("compression_notes", "")
        semantic_instruction = build_screener_semantic_instruction(state, "portfolio_manager")
        execution_profile = build_semantic_execution_profile(state, "portfolio_manager")
        route_decision = state.get("route_decision", {}) or state.get("screener_context", {}).get("route_decision", {}) or {}
        policy_role = str(route_decision.get("policy_role", "") or "none")
        capital_quality = str(route_decision.get("capital_quality", "") or "none")
        conflict_tier = str(route_decision.get("conflict_tier", "") or "none")
        style = str(execution_profile.get("response_style", "balanced"))
        conclusion_mode = str(execution_profile.get("conclusion_mode", "standard"))
        conclusion_template_instruction = build_conclusion_template_instruction(conclusion_mode)
        must_include = execution_profile.get("evidence_must_include", []) or []
        portfolio_role_instruction = ""
        if capital_quality == "capital_quality_speculative":
            portfolio_role_instruction = (
                " Use a stricter default risk stance: demand smaller size, faster downgrade conditions, and explicit crowding-risk controls."
            )
        elif policy_role == "policy_top_stock":
            portfolio_role_instruction = (
                " Evaluate whether board leadership improves conviction enough to justify anything above a defensive rating."
            )

        # ─────────────────────────────────────────────────────────────────
        # 第二步：读取风险辩论的状态
        # ─────────────────────────────────────────────────────────────────

        # risk_debate_state 是子状态的子状态
        # 包含：辩论历史、三方各自的历史、最新论点等
        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]

        # ─────────────────────────────────────────────────────────────────
        # 第三步：读取上游节点的输出
        # ─────────────────────────────────────────────────────────────────

        # 4位分析师的报告
        market_research_report = state["market_report"]         # 市场技术分析
        news_report = state["news_report"]                     # 新闻分析
        fundamentals_report = state["fundamentals_report"]       # 基本面分析
        sentiment_report = state["sentiment_report"]             # 社交媒体情绪

        # Research Manager 和 Trader 的建议
        research_plan = state["investment_plan"]                 # 研究经理的投资计划
        trader_plan = state["trader_investment_plan"]           # 交易员的交易建议

        # ─────────────────────────────────────────────────────────────────
        # 第四步：从记忆系统获取历史经验
        # ─────────────────────────────────────────────────────────────────

        # 拼接当前情况描述
        curr_situation = (
            f"{market_research_report}\n\n"
            f"{sentiment_report}\n\n"
            f"{news_report}\n\n"
            f"{fundamentals_report}"
        )

        # 获取最相似的 2 条历史经验
        past_memories = memory.get_memories(
            curr_situation,
            n_matches=execution_profile.get("memory_n_matches", 2),
        )

        # 格式化为字符串
        past_memory_str = ""
        for rec in past_memories:
            past_memory_str += rec["recommendation"] + "\n\n"

        # ─────────────────────────────────────────────────────────────────
        # 第五步：注入 Skills
        # ─────────────────────────────────────────────────────────────────

        current_count = risk_debate_state["count"]
        skill_prompt, injected_skill_names = skill_injector.inject(
            decision_type=DecisionType.VALUATION,
            existing_prompt="",
            node_name="portfolio_manager",
            debate_round=current_count or 1,
            is_counter_round=False,
            is_adjudication=True,
        )

        # ─────────────────────────────────────────────────────────────────
        # 第六步：构建 Prompt
        # ─────────────────────────────────────────────────────────────────
        # Prompt 要求必须：
        # 1. 给出明确评级（5选1）
        # 2. 给出执行摘要
        # 3. 给出投资论点

        confidence_instruction = ""
        if state.get("orchestration", {}).get("enable_confidence_score"):
            confidence_instruction = (
                " Add a confidence line inside <decision> as Confidence: N/100 with one brief basis."
            )

        prompt = build_xml_decision_prompt(
            role_definition=skill_prompt + "\n\n" + (
                "You are the Portfolio Manager making the final risk-adjusted trading decision."
                " You must act like a compliance-focused risk officer with 20 years of A-share quantitative"
                " risk-control experience, while still issuing a clear portfolio action."
                f"{portfolio_role_instruction}"
            ),
            task_instructions=(
                f"{instrument_context}\n\n"
                f"{segment_advisory}\n\n"
                "Use exactly one rating from Buy / Overweight / Hold / Underweight / Sell.\n"
                f"Compressed handoff notes from prior stage:\n{compression_notes}\n\n"
                f"Screener semantic routing guidance:\n{semantic_instruction}\n\n"
                f"Semantic execution profile: {execution_profile}\n\n"
                f"Execution style: {style}; conclusion_mode={conclusion_mode}; required evidence={must_include}\n\n"
                f"{conclusion_template_instruction}\n\n"
                f"Route context: policy_role={policy_role}, capital_quality={capital_quality}, conflict_tier={conflict_tier}\n\n"
                f"Research Manager's investment plan: {research_plan}\n"
                f"Trader's transaction proposal: {trader_plan}\n"
                f"Lessons from past decisions: {past_memory_str}\n"
                f"Risk Analysts Debate History:\n{history}\n\n"
                "In <analysis>, summarize the strongest evidence and risk tradeoffs.\n"
                "In <decision>, provide the final rating, action plan, time horizon, and core thesis."
                " Emphasize risk controls, sizing discipline, and downside scenarios."
                f"{confidence_instruction}"
                f"{get_language_instruction()}"
            ),
        )

        # ─────────────────────────────────────────────────────────────────
        # 第七步：调用 LLM 生成决策
        # ─────────────────────────────────────────────────────────────────

        # 直接调用 llm.invoke()，不需要工具绑定
        # portfolio_manager 是"纯决策者"，不需要获取数据
        response = llm.invoke(prompt)
        response.content = enforce_execution_profile_output(response.content, execution_profile)

        skill_result = enforce_skill_usage(
            content=response.content,
            injected_skill_names=injected_skill_names,
            node_name="portfolio_manager",
            decision_type=DecisionType.VALUATION.value,
            debate_round=current_count or 1,
            is_counter_round=False,
            is_adjudication=True,
        )
        response.content = skill_result["content"]

        # ─────────────────────────────────────────────────────────────────
        # 第八步：更新 risk_debate_state
        # ─────────────────────────────────────────────────────────────────
        # 添加 Judge 的决策到辩论历史

        new_risk_debate_state = {
            # 最终决策（供日志/审计用）
            "judge_decision": response.content,

            # 保持历史记录不变
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],

            # 标记最新发言者为 Judge
            "latest_speaker": "Judge",

            # 保持三方的最新论点不变
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],

            # 辩论轮次 +1
            "count": risk_debate_state["count"],
        }

        # ─────────────────────────────────────────────────────────────────
        # 第九步：返回更新后的状态
        # ─────────────────────────────────────────────────────────────────

        update = sync_decision_updates(
            decision_key="final_trade_decision",
            decision_value=response.content,
            sender="Portfolio Manager",
        )
        orchestration = dict(state.get("orchestration", {}))
        prior_route = str(orchestration.get("final_route", "")).strip()
        prior_reason = str(orchestration.get("final_reason", "")).strip()
        orchestration["stage"] = "completed"
        orchestration["phase"] = "completed"
        orchestration["next_stage"] = "completed"
        orchestration["completed"] = True
        orchestration["compression_required"] = False
        orchestration["final_route"] = prior_route or "portfolio"
        orchestration["final_reason"] = prior_reason or "portfolio_manager_completed"
        update["orchestration"] = orchestration
        update["risk_debate_state"] = new_risk_debate_state
        update["debate_blocks"] = {"risk": new_risk_debate_state}
        return update

    return portfolio_manager_node
