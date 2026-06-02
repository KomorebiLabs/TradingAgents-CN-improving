"""
================================================================================
                   BULL_RESEARCHER.PY 详解
                       多头研究员（牛方分析师）
================================================================================

【模块定位】
    本文件是 TradingAgents 的"多头研究员"节点（看多分析师）。

    与 bear_researcher 形成对称的对立角色，共同组成多空辩论层。

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         多空辩论层                                         │
    │                                                                           │
    │         ┌─────────────────────────┐                                      │
    │         │    Bull Researcher      │  →  看多方（当前文件）               │
    │         │    (多头分析师)         │                                      │
    │         └───────────┬─────────────┘                                      │
    │                     │                                                    │
    │                     │  互相反驳                                          │
    │                     ▼                                                    │
    │         ┌─────────────────────────┐                                      │
    │         │    Bear Researcher      │  →  看空方                          │
    │         │    (空头分析师)         │                                      │
    │         └─────────────────────────┘                                      │
    │                     │                                                    │
    │                     │  循环（N 轮）                                     │
    └─────────────────────┼───────────────────────────────────────────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │   Research Manager      │  →  裁判
              └─────────────────────────┘

【多头分析师的核心思想】

    1. 关注成长：
       → 市场机会
       → 营收增长
       → 可扩展性

    2. 关注优势：
       → 独特产品
       → 强大品牌
       → 市场主导地位

    3. 关注正面信号：
       → 财务健康
       → 行业趋势向上
       → 正面新闻

【与 bear_researcher 的镜像关系】

    bull_researcher 和 bear_researcher 代码结构几乎完全相同：

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                          镜像对比                                         │
    │                                                                           │
    │   bull_researcher                    bear_researcher                     │
    │   ─────────────────                  ──────────────────                   │
    │   立场：看多                         立场：看空                         │
    │   反驳 Bear 的论点                   反驳 Bull 的论点                   │
    │   强调：成长潜力、优势               强调：风险、劣势                   │
    │   Bull Analyst 标识                 Bear Analyst 标识                   │
    │   bull_history                     bear_history                        │
    └─────────────────────────────────────────────────────────────────────────┘

    唯一不同的是 prompt 中的角色定义和论点方向。

【Prompt 设计要点】

    1. 强调"反驳"：
       → 不能只列举看多理由
       → 必须针对 Bear 的论点逐一反驳

    2. 关注历史经验：
       → 参考 past_memories
       → 从过去的成功/失败中学习

    3. 要求对话式输出：
       → "辩论"而非"列表"
       → 直接回应对方的观点

================================================================================
"""

from tradingagents.agents.utils.agent_utils import (
    build_conclusion_template_instruction,
    enforce_execution_profile_output,
    build_screener_semantic_instruction,
    build_semantic_execution_profile,
)
from tradingagents.agents.utils.state_helpers import sync_investment_debate_update


def create_bull_researcher(llm, memory, skill_injector=None):
    """
    【工厂函数】创建多头研究员节点

    【参数】
        llm: 快速思考模型
        memory: 记忆系统
        skill_injector: 可选的 SkillInjector 实例

    【返回值】
        bull_node: 可调用的节点函数
    """
    from tradingagents.harness.skills.injector import SkillInjector
    from tradingagents.harness.skills.types import DecisionType
    if skill_injector is None:
        skill_injector = SkillInjector()

    def bull_node(state) -> dict:
        """
        【节点函数】多头分析师的核心逻辑

        【工作流程】

            与 bear_node 完全对称：

            Step 1: 读取辩论状态
            → history、bull_history、current_response（这里是 Bear 的最新论点）

            Step 2: 读取分析师报告
            → 4 份报告（市场/情绪/新闻/基本面）

            Step 3: 从 memory 获取历史经验
            → past_memories

            Step 4: 构建 Prompt（多头视角）
            → 强调：成长、优势、正面信号
            → 反驳：Bear 的论点

            Step 5: 调用 LLM

            Step 6: 更新辩论状态
            → history += bull 的发言
            → bull_history += bull 的发言
            → current_response = bull 的发言
            → count += 1

        """

        # ─────────────────────────────────────────────────────────────────
        # 第一步：读取辩论状态
        # ─────────────────────────────────────────────────────────────────

        investment_debate_state = state["investment_debate_state"]

        # history: 所有发言的累积记录
        history = investment_debate_state.get("history", "")

        # bull_history: 只有 Bull 的发言记录
        bull_history = investment_debate_state.get("bull_history", "")

        # current_response: Bear 的最新发言
        # Bull 需要反驳这个内容
        current_response = investment_debate_state.get("current_response", "")
        route_decision = state.get("route_decision", {}) or state.get("screener_context", {}).get("route_decision", {}) or {}
        policy_role = str(route_decision.get("policy_role", "") or "none")
        capital_quality = str(route_decision.get("capital_quality", "") or "none")
        conflict_tier = str(route_decision.get("conflict_tier", "") or "none")
        debate_risk_weight = str(route_decision.get("debate_risk_weight", "") or "normal")
        if policy_role == "policy_top_stock":
            current_response = current_response[:1800]
        elif policy_role == "policy_core_member":
            current_response = current_response[:2400]
        if capital_quality == "capital_quality_speculative":
            debate_risk_weight = "high"

        # ─────────────────────────────────────────────────────────────────
        # 第二步：读取 4 位分析师的报告
        # ─────────────────────────────────────────────────────────────────

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

        curr_situation = f"""
            {market_research_report}
            {sentiment_report}
            {news_report}
            {fundamentals_report}
        """
        if policy_role in {"policy_top_stock", "policy_core_member"}:
            curr_situation += "\nConcept-board leadership and membership relevance should be treated as first-order evidence."

        past_memories = memory.get_memories(
            curr_situation,
            n_matches=execution_profile.get("memory_n_matches", 2),
        )

        past_memory_str = ""
        for rec in past_memories:
            past_memory_str += rec["recommendation"] + "\n\n"

        # ─────────────────────────────────────────────────────────────────
        # 第四步：构建 Prompt（多头视角）
        # ─────────────────────────────────────────────────────────────────
        # 与 bear_node 的 prompt 形成镜像：
        # → 强调成长潜力、竞争优势、正面指标
        # → 反驳空头的论点

        # Determine debate round and counter-round status
        current_count = investment_debate_state["count"]
        is_counter_round = current_count >= 1

        # Build the role definition part (to be prepended to skill injection)
        role_definition = (
            "You are a Bull Analyst advocating for investing in the stock. "
            "Your task is to build a strong, evidence-based case emphasizing "
            "growth potential, competitive advantages, and positive market indicators. "
            "Leverage the provided research and data to address concerns and counter "
            "bearish arguments effectively."
        )

        # Inject offensive decision-type skills (round-aware, with usage instruction)
        skill_prompt, injected_skill_names = skill_injector.inject(
            decision_type=DecisionType.OFFENSIVE,
            existing_prompt=role_definition,
            node_name="bull",
            debate_round=current_count,
            is_counter_round=is_counter_round,
        )

        prompt = skill_prompt + (
            f"""\n\nRoute context:
- policy_role: {policy_role}
- capital_quality: {capital_quality}
- conflict_tier: {conflict_tier}
- debate_risk_weight: {debate_risk_weight}

Key points to focus on:
- Growth Potential: Highlight the company's market opportunities, revenue projections, and scalability.
- Competitive Advantages: Emphasize factors like unique products, strong branding, or dominant market positioning.
- Positive Indicators: Use financial health, industry trends, and recent positive news as evidence.
- Bear Counterpoints: Critically analyze the bear argument with specific data and sound reasoning, addressing concerns thoroughly and showing why the bull perspective holds stronger merit.
- Engagement: Present your argument in a conversational style, engaging directly with the bear analyst's points and debating effectively rather than just listing data.

Resources available:
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
Company fundamentals report: {fundamentals_report}
Conversation history of the debate: {history}
Last bear argument: {current_response}
Reflections from similar situations and lessons learned: {past_memory_str}
Screener semantic routing guidance: {semantic_instruction}
Semantic execution profile: {execution_profile}
Execution style: {style}
Conclusion template: {conclusion_template_instruction}
Required evidence: {must_include}
Use this information to deliver a compelling bull argument, refute the bear's concerns, and engage in a dynamic debate that demonstrates the strengths of the bull position. You must also address reflections and learn from lessons and mistakes you made in the past.
"""
        )

        # ─────────────────────────────────────────────────────────────────
        # 第五步：调用 LLM
        # ─────────────────────────────────────────────────────────────────

        response = llm.invoke(prompt)
        response.content = enforce_execution_profile_output(response.content, execution_profile)

        # Skill usage audit
        from tradingagents.agents.utils.agent_utils import enforce_skill_usage
        skill_result = enforce_skill_usage(
            content=response.content,
            injected_skill_names=injected_skill_names,
            node_name="bull",
            decision_type=DecisionType.OFFENSIVE.value,
            debate_round=current_count,
            is_counter_round=is_counter_round,
            is_adjudication=False,
        )
        response.content = skill_result["content"]

        # 加上角色标识
        argument = f"Bull Analyst: {response.content}"

        # ─────────────────────────────────────────────────────────────────
        # 第六步：更新辩论状态
        # ─────────────────────────────────────────────────────────────────

        new_investment_debate_state = {
            # 追加到完整历史
            "history": history + "\n" + argument,

            # 追加到 Bull 历史
            "bull_history": bull_history + "\n" + argument,

            # 保持 Bear 历史不变
            "bear_history": investment_debate_state.get("bear_history", ""),

            # 更新当前回复（供下一轮 Bear 反驳）
            "current_response": argument,

            # 辩论轮次 +1
            "count": investment_debate_state["count"] + 1,

            # 追踪最后发言者（避免 current_response 内容误判导致无限循环）
            "latest_speaker": "Bull Researcher",
        }

        # Write skill audit entry to AgentState (must happen after dict init)
        audit_entry = skill_result["audit_entry"]
        if audit_entry:
            existing_trail = dict(investment_debate_state.get("skill_audit_trail", {}))
            existing_trail.setdefault("bull", []).append(audit_entry)
            new_investment_debate_state["skill_audit_trail"] = existing_trail

        # ─────────────────────────────────────────────────────────────────
        # 第七步：返回更新后的状态
        # ─────────────────────────────────────────────────────────────────

        return sync_investment_debate_update(
            debate_state=new_investment_debate_state,
            sender="Bull Researcher",
        )

    return bull_node
