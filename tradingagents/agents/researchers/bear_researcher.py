"""
================================================================================
                   BEAR_RESEARCHER.PY 详解
                       空头研究员（熊方分析师）
================================================================================

【模块定位】
    本文件是 TradingAgents 的"空头研究员"节点（看空分析师）。

    在多空辩论层中，bear_researcher 与 bull_researcher 形成对立：

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         多空辩论层（第一轮 → N 轮）                        │
    │                                                                           │
    │         ┌─────────────────────────┐                                      │
    │         │    Bull Researcher      │  →  看多方                           │
    │         │    (多头分析师)         │                                      │
    │         └───────────┬─────────────┘                                      │
    │                     │                                                    │
    │                     │  互相反驳                                          │
    │                     ▼                                                    │
    │         ┌─────────────────────────┐                                      │
    │         │    Bear Researcher      │  →  看空方（当前文件）               │
    │         │    (空头分析师)         │                                      │
    │         └─────────────────────────┘                                      │
    │                     │                                                    │
    │                     │  循环（N 轮）                                     │
    └─────────────────────┼───────────────────────────────────────────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │   Research Manager      │  →  汇总辩论，裁判
              └─────────────────────────┘

【空头分析师的核心思想】

    1. 关注风险：
       → 市场饱和度
       → 财务不稳定性
       → 宏观经济威胁

    2. 关注劣势：
       → 竞争地位弱化
       → 创新能力下降
       → 竞争对手威胁

    3. 关注负面信号：
       → 财务数据恶化
       → 行业趋势向下
       → 负面新闻

【与 bull_researcher 的对称性】

    bear_researcher 和 bull_researcher 是一对"镜像"角色：

    ┌─────────────────┬─────────────────────────────┬─────────────────────────────┐
    │      维度        │     bull_researcher         │      bear_researcher       │
    ├─────────────────┼─────────────────────────────┼─────────────────────────────┤
    │   立场           │   看多                     │     看空                   │
    │   核心观点       │   成长潜力、竞争优势       │     风险、劣势、威胁       │
    │   反驳对象       │   Bear 的论点              │     Bull 的论点            │
    │   任务           │   强调正面证据            │     强调负面证据           │
    └─────────────────┴─────────────────────────────┴─────────────────────────────┘

    两者代码结构几乎完全相同，只有 prompt 中的"立场"不同。

【辩论循环机制】

    辩论不是一轮定胜负，而是多轮循环：

    轮次 1：
        Bull 先发言 → Bear 反驳

    轮次 2：
        Bull 回应 Bear 的反驳 → Bear 再反驳

    ...（直到达到最大轮次）

    最大轮次由 setup.py 中的条件逻辑控制：
    → investment_debate_state["count"] >= max_debate_rounds → 跳出循环

【prompt 设计要点】

    1. 强调"反驳"：
       → 不能只列举看空理由
       → 必须针对 Bull 的论点逐一反驳

    2. 关注历史经验：
       → 参考 past_memories
       → 从过去的错误中学习

    3. 要求对话式输出：
       → 不是"列清单"，而是"辩论"
       → 直接回应对方的观点

================================================================================
"""

from tradingagents.agents.utils.agent_utils import (
    build_conclusion_template_instruction,
    enforce_execution_profile_output,
    build_screener_semantic_instruction,
    build_semantic_execution_profile,
    enforce_skill_usage,
)
from tradingagents.agents.utils.state_helpers import sync_investment_debate_update


def create_bear_researcher(llm, memory, skill_injector=None):
    from tradingagents.harness.skills.injector import SkillInjector
    from tradingagents.harness.skills.types import DecisionType
    if skill_injector is None:
        skill_injector = SkillInjector()
    """
    【工厂函数】创建空头研究员节点

    【设计原理】

        工厂函数模式：create_xxx(llm, memory) → 返回节点函数

        好处：
        1. llm 和 memory 在创建时就绑定到函数内部
        2. LangGraph 调用节点时不需要再传这两个参数
        3. 可以给不同的分析师绑定不同的 llm

    【参数】
        llm: 快速思考模型（如 GPT-4o-mini）
        memory: 记忆系统（用于获取历史经验）

    【返回值】
        bear_node: 可调用的节点函数
    """

    def bear_node(state) -> dict:
        """
        【节点函数】空头分析师的核心逻辑

        【工作流程】

            ┌─────────────────────────────────────────────────────────────────┐
            │                                                                       │
            │   Step 1: 读取辩论状态                                               │
            │   • investment_debate_state → 辩论状态容器                           │
            │   • history → 所有发言的历史                                        │
            │   • current_response → Bull 的最新论点（需要反驳）                  │
            │                                                                       │
            └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
            ┌─────────────────────────────────────────────────────────────────┐
            │                                                                       │
            │   Step 2: 读取分析师报告                                               │
            │   • market_report / sentiment_report / news_report / fundamentals_report │
            │                                                                       │
            └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
            ┌─────────────────────────────────────────────────────────────────┐
            │                                                                       │
            │   Step 3: 从 memory 获取历史经验                                      │
            │   • get_memories(curr_situation, n_matches=2)                      │
            │   • 匹配相似情况，学习过去的教训                                     │
            │                                                                       │
            └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
            ┌─────────────────────────────────────────────────────────────────┐
            │                                                                       │
            │   Step 4: 构建 Prompt（空头视角）                                    │
            │   • 强调：风险、劣势、负面信号                                      │
            │   • 反驳：Bull 的论点                                               │
            │   • 要求：对话式、直接回应                                           │
            │                                                                       │
            └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
            ┌─────────────────────────────────────────────────────────────────┐
            │                                                                       │
            │   Step 5: 调用 LLM 生成论点                                          │
            │                                                                       │
            └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
            ┌─────────────────────────────────────────────────────────────────┐
            │                                                                       │
            │   Step 6: 更新辩论状态                                               │
            │   • history += bear 的发言                                          │
            │   • bear_history += bear 的发言                                    │
            │   • current_response = bear 的发言（供下一轮 Bull 反驳）             │
            │   • count += 1（轮次 +1）                                          │
            │                                                                       │
            └─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                                返回更新后的状态



            四个分析师的数据存放位置
            答案：都存放在 LangGraph 的 state 中
            ┌─────────────────────────────────────────────────────────────────────────┐
            │                                                                          │
            │   LangGraph 的 state（全局状态字典）                                     │
            │                                                                          │
            │   state = {                                                             │
            │       "trade_date": "2024-06-15",       ← 当前交易日期                    │
            │       "company_of_interest": "NVDA",     ← 分析的股票                     │
            │       "messages": [...],                 ← 对话历史（工具调用记录）        │
            │                                                                          │
            │       # ─── 分析师报告 ───                                              │
            │       "market_report": "...",            ← 市场技术分析报告               │
            │       "sentiment_report": "...",         ← 社交媒体情绪报告               │
            │       "news_report": "...",              ← 新闻分析报告                   │
            │       "fundamentals_report": "...",      ← 基本面分析报告                │
            │       # ────────────────                                              │
            │   }                                                                    │
            │                                                                          │
            └─────────────────────────────────────────────────────────────────────────┘



        【参数详解：state】

            state 是 LangGraph 维护的全局状态。
            bear_node 执行时，state 中包含：

            state["investment_debate_state"]
                → 辩论子状态，包含辩论历史、轮次等

            state["market_report"]
                → 市场技术分析报告

            state["sentiment_report"]
                → 社交媒体情绪报告

            state["news_report"]
                → 新闻分析报告

            state["fundamentals_report"]
                → 基本面分析报告

        【investment_debate_state 的结构】

            {
                "history": "...",
                → 所有辩论发言的累积记录

                "bull_history": "...",
                → Bull 的发言记录

                "bear_history": "...",
                → Bear 的发言记录

                "current_response": "...",
                → 最近一方的发言（供对方反驳）

                "count": 2,
                → 当前辩论轮次
            }

        【返回值】

            返回 {"investment_debate_state": new_investment_debate_state}
            只更新辩论子状态，不更新其他字段。

        """

        # ─────────────────────────────────────────────────────────────────
        # 第一步：读取辩论状态
        # ─────────────────────────────────────────────────────────────────

        investment_debate_state = state["investment_debate_state"]

        # history: 所有发言的累积记录
        # 包括 Bull 和 Bear 的所有历史发言
        history = investment_debate_state.get("history", "")

        # bear_history: 只有 Bear 的发言记录
        # 用于单独追踪 Bear 的论点演变
        bear_history = investment_debate_state.get("bear_history", "")

        # current_response: Bull 的最新发言
        # Bear 需要反驳这个内容
        current_response = investment_debate_state.get("current_response", "")
        route_decision = state.get("route_decision", {}) or state.get("screener_context", {}).get("route_decision", {}) or {}
        policy_role = str(route_decision.get("policy_role", "") or "none")
        capital_quality = str(route_decision.get("capital_quality", "") or "none")
        conflict_tier = str(route_decision.get("conflict_tier", "") or "none")
        debate_risk_weight = str(route_decision.get("debate_risk_weight", "") or "normal")
        if policy_role == "policy_top_stock":
            current_response = current_response[:1600]
        elif policy_role == "policy_core_member":
            current_response = current_response[:2200]
        if capital_quality == "capital_quality_speculative":
            debate_risk_weight = "high"

        # ─────────────────────────────────────────────────────────────────
        # 第二步：读取 4 位分析师的报告
        # ─────────────────────────────────────────────────────────────────
        # 这些报告是 Bull 和 Bear 共同的决策依据
        # 两方都基于同样的数据，但得出不同结论

        market_research_report = state["market_report"]           # 市场技术分析
        sentiment_report = state["sentiment_report"]             # 社交媒体情绪
        news_report = state["news_report"]                       # 全球财经新闻
        fundamentals_report = state["fundamentals_report"]       # 基本面分析
        semantic_instruction = build_screener_semantic_instruction(state, "research_manager")
        execution_profile = build_semantic_execution_profile(state, "research_manager")
        max_context_chars = int(execution_profile.get("max_context_chars", 3200) or 3200)
        style = str(execution_profile.get("response_style", "balanced"))
        conclusion_mode = str(execution_profile.get("conclusion_mode", "standard"))
        conclusion_template_instruction = build_conclusion_template_instruction(conclusion_mode)
        must_include = execution_profile.get("evidence_must_include", []) or []
        if len(history) > max_context_chars:
            history = history[-max_context_chars:]

        # ─────────────────────────────────────────────────────────────────
        # 第三步：从记忆系统获取历史经验
        # ─────────────────────────────────────────────────────────────────
        # memory.get_memories() 基于语义相似度匹配历史
        # 匹配的是"当前情况"和"过去情况"的相似性
        # n_matches=2 表示返回最相似的 2 条历史经验

        # 拼接当前情况描述（用于匹配相似历史）
        curr_situation = f"""
            {market_research_report}
            {sentiment_report}
            {news_report}
            {fundamentals_report}
        """
        if policy_role in {"policy_top_stock", "policy_core_member"}:
            curr_situation += "\nNeed to test whether this is a genuine board leader or merely a thematic passenger."

        past_memories = memory.get_memories(
            curr_situation,
            n_matches=execution_profile.get("memory_n_matches", 2),
        )

        # 格式化为字符串，供 Prompt 使用
        past_memory_str = ""
        for rec in past_memories:
            past_memory_str += rec["recommendation"] + "\n\n"

        # ─────────────────────────────────────────────────────────────────
        # 第四步：构建 Prompt（核心部分）
        # ─────────────────────────────────────────────────────────────────
        # Prompt 定义了 Bear 的角色和任务：
        # 1. 扮演看空分析师
        # 2. 反驳 Bull 的论点
        # 3. 强调风险、劣势、威胁

        # Determine debate round and counter-round status
        current_count = investment_debate_state["count"]
        is_counter_round = current_count >= 1

        # Build the role definition part
        role_definition = (
            "You are a Bear Analyst making the case against investing in the stock. "
            "Your goal is to present a well-reasoned argument emphasizing risks, "
            "challenges, and negative indicators. Leverage the provided research and data "
            "to highlight potential downsides and counter bullish arguments effectively."
        )

        # Inject defensive decision-type skills (round-aware)
        skill_prompt, injected_skill_names = skill_injector.inject(
            decision_type=DecisionType.DEFENSIVE,
            existing_prompt=role_definition,
            node_name="bear",
            debate_round=current_count,
            is_counter_round=is_counter_round,
        )

        prompt = skill_prompt + (
            f"\n\nRoute context:\n"
            f"- policy_role: {policy_role}\n"
            f"- capital_quality: {capital_quality}\n"
            f"- conflict_tier: {conflict_tier}\n"
            f"- debate_risk_weight: {debate_risk_weight}\n"
            f"\nKey points to focus on:\n"
            f"\n- Risks and Challenges: Highlight factors like market saturation, financial instability, or macroeconomic threats that could hinder the stock's performance.\n"
            f"- Competitive Weaknesses: Emphasize vulnerabilities such as weaker market positioning, declining innovation, or threats from competitors.\n"
            f"- Negative Indicators: Use evidence from financial data, market trends, or recent adverse news to support your position.\n"
            f"- Bull Counterpoints: Critically analyze the bull argument with specific data and sound reasoning, exposing weaknesses or over-optimistic assumptions.\n"
            f"- Engagement: Present your argument in a conversational style, directly engaging with the bull analyst's points and debating effectively rather than simply listing facts.\n"
            f"\nResources available:\n"
            f"\nMarket research report: {market_research_report}\n"
            f"Social media sentiment report: {sentiment_report}\n"
            f"Latest world affairs news: {news_report}\n"
            f"Company fundamentals report: {fundamentals_report}\n"
            f"Conversation history of the debate: {history}\n"
            f"Last bull argument: {current_response}\n"
            f"Reflections from similar situations and lessons learned: {past_memory_str}\n"
            f"Screener semantic routing guidance: {semantic_instruction}\n"
            f"Semantic execution profile: {execution_profile}\n"
            f"Execution style: {style}\n"
            f"Conclusion template: {conclusion_template_instruction}\n"
            f"Required evidence: {must_include}\n"
            f"Use this information to deliver a compelling bear argument, refute the bull's claims, and engage in a dynamic debate that demonstrates the risks and weaknesses of investing in the stock. You must also address reflections and learn from lessons and mistakes you made in the past.\n"
        )

        # ─────────────────────────────────────────────────────────────────
        # 第五步：调用 LLM
        # ─────────────────────────────────────────────────────────────────
        # bear_node 不使用工具（Tools），只做对话生成
        # 这是因为辩论的基础数据已经在分析师报告中获取

        response = llm.invoke(prompt)
        response.content = enforce_execution_profile_output(response.content, execution_profile)

        # Skill usage audit
        from tradingagents.agents.utils.agent_utils import enforce_skill_usage
        skill_result = enforce_skill_usage(
            content=response.content,
            injected_skill_names=injected_skill_names,
            node_name="bear",
            decision_type=DecisionType.DEFENSIVE.value,
            debate_round=current_count,
            is_counter_round=is_counter_round,
            is_adjudication=False,
        )
        response.content = skill_result["content"]

        # Write skill audit entry to AgentState
        audit_entry = skill_result["audit_entry"]
        _pending_audit_entry = audit_entry  # defer until new_investment_debate_state is created

        # 加上角色标识，便于阅读辩论历史
        argument = f"Bear Analyst: {response.content}"

        # ─────────────────────────────────────────────────────────────────
        # 第六步：更新辩论状态
        # ─────────────────────────────────────────────────────────────────

        new_investment_debate_state = {
            # 追加到完整历史（所有发言的累积）
            "history": history + "\n" + argument,

            # 保持 Bull 历史不变（从旧状态获取）
            "bull_history": investment_debate_state.get("bull_history", ""),

            # 追加到 Bear 历史
            "bear_history": bear_history + "\n" + argument,

            # 更新当前回复（供下一轮 Bull 反驳）
            "current_response": argument,

            # 辩论轮次 +1（供条件逻辑判断是否结束）
            "count": investment_debate_state["count"] + 1,

            # 追踪最后发言者（避免 current_response 内容误判导致无限循环）
            "latest_speaker": "Bear Researcher",
        }

        # Write deferred skill audit entry
        if _pending_audit_entry:
            existing_trail = dict(investment_debate_state.get("skill_audit_trail", {}))
            existing_trail.setdefault("bear", []).append(_pending_audit_entry)
            new_investment_debate_state["skill_audit_trail"] = existing_trail

        # ─────────────────────────────────────────────────────────────────
        # 第七步：返回更新后的状态
        # ─────────────────────────────────────────────────────────────────

        return sync_investment_debate_update(
            debate_state=new_investment_debate_state,
            sender="Bear Researcher",
        )

    # 返回节点函数（不是调用它）
    return bear_node
