"""
================================================================================
                   FUNDAMENTALS_ANALYST.PY 详解
                       基本面分析师节点
================================================================================

【模块定位】
    本文件是 TradingAgents 的"基本面分析师"节点。

    在 LangGraph 工作流中的位置：
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         LangGraph 工作流                                  │
    │                                                                           │
    │   start                                                                   │
    │     │                                                                    │
    │     ▼                                                                    │
    │   ┌──────────────────────────────────────────────────────────────┐        │
    │   │              4 位分析师并行执行（第一层并行）                     │        │
    │   │                                                               │        │
    │   │   market_analyst     →  技术分析（价格、指标）                  │        │
    │   │   news_analyst       →  新闻分析                               │        │
    │   │   fundamentals_analyst →  基本面分析（当前文件）                │        │
    │   │   social_media_analyst →  社交媒体情绪                         │        │
    │   │                                                               │        │
    │   └──────────────────────────────────────────────────────────────┘        │
    │                             │                                           │
    │                             ▼                                           │
    │   ┌──────────────────────────────────────────────────────────────┐        │
    │   │              多空辩论（第二层：Bull vs Bear）                   │        │
    │   │                                                               │        │
    │   │   bull_researcher  ←────────────────→  bear_researcher       │        │
    │   │          ↺ 循环（由 count 控制）                               │        │
    │   └──────────────────────────────────────────────────────────────┘        │
    │                             │                                           │
    │                             ▼                                           │
    │   research_manager  →  汇总辩论，生成投资计划                        │
    │                             │                                           │
    │                             ▼                                           │
    │   trader  →  基于计划做出交易决策                                   │
    │                             │                                           │
    │                             ▼                                           │
    │   ┌──────────────────────────────────────────────────────────────┐        │
    │   │              风险辩论（第三层：3种风险偏好）                   │        │
    │   │                                                               │        │
    │   │   aggressive_debator    →  高风险激进派                       │        │
    │   │   conservative_debator  →  低风险保守派                       │        │
    │   │   neutral_debator       →  中性平衡派                         │        │
    │   └──────────────────────────────────────────────────────────────┘        │
    │                             │                                           │
    │                             ▼                                           │
    │   portfolio_manager  →  最终投资决策                                │
    │                             │                                           │
    │                             ▼                                           │
    │                            end                                          │
    └─────────────────────────────────────────────────────────────────────────┘

【基本面分析师的职责】
    基本面分析关注的是公司的"内在价值"，回答的核心问题是：
    "这家公司值多少钱？它能持续盈利吗？"

    基本面分析包含四大维度：

    1. 公司概览
       → 公司是做什么的？行业地位如何？商业模式是什么？

    2. 资产负债表
       → 公司有多少资产？欠了多少债？财务是否健康？

    3. 现金流量表
       → 公司真的收到钱了吗？现金流转是否正常？

    4. 利润表
       → 公司赚钱了吗？盈利能力如何？增长趋势怎样？

【本文件的工具】
    本文件绑定 4 个工具：
    • get_fundamentals       → 公司概览
    • get_balance_sheet     → 资产负债表
    • get_cashflow         → 现金流量表
    • get_income_statement  → 利润表

    这些工具来自 agent_utils.py，它们是对 dataflows 层函数的二次封装。

【工厂函数模式】
    create_fundamentals_analyst(llm) 是一个工厂函数：
    • 输入：llm（大语言模型）
    • 输出：一个可调用的节点函数 fundamentals_analyst_node

    为什么用工厂函数？
    LangGraph 需要一个"可调用对象"作为节点，而节点需要访问 llm。
    直接把 llm 传进去会导致 LangGraph 无法序列化。
    所以用工厂函数把 llm "闭包"进节点函数里。

【Prompt 设计】
    系统提示词的核心要求：
    1. 写一份"全面"的报告
    2. 包含尽可能多的细节
    3. 提供"可操作的见解"和证据
    4. 结尾必须加 Markdown 表格

    这样的设计是为了让 LLM 输出的报告：
    • 信息密度高（全面）
    • 结构清晰（Markdown 表格）
    • 可直接用于交易决策（可操作）

================================================================================
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.prompts import build_collaboration_system_prompt
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    build_screener_semantic_instruction,
    get_tools_for_analyst,
    get_language_instruction,
)
from tradingagents.agents.utils.state_helpers import sync_report_updates
from tradingagents.dataflows.config import get_config


def create_fundamentals_analyst(llm):
    """
    【工厂函数】创建基本面分析师节点

    【工作流程】

        ┌─────────────────────────────────────────────────────────────────────┐
        │                                                                       │
        │   create_fundamentals_analyst(llm)  被调用                            │
        │                    │                                                  │
        │                    ▼                                                  │
        │   返回 fundamentals_analyst_node 函数                                  │
        │                    │                                                  │
        │                    ▼                                                  │
        │   LangGraph 在执行工作流时调用 fundamentals_analyst_node(state)          │
        │                    │                                                  │
        │                    ▼                                                  │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │ Step 1: 从 state 读取当前交易日期和公司信息                      │   │
        │   │ Step 2: 构建 Prompt（包含公司背景、工具说明、日期）              │   │
        │   │ Step 3: 调用 LLM，让它决定是否调用工具                         │   │
        │   │ Step 4: LLM 可能调用工具获取基本面数据                         │   │
        │   │ Step 5: LLM 生成报告，返回结果                                 │   │
        │   │ Step 6: 返回 {messages, fundamentals_report}                   │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                                                                       │
        └─────────────────────────────────────────────────────────────────────┘

    【返回值中的 fundamentals_report 字段】

        如果 LLM 调用了工具（tool_calls 不为空）：
        → fundamentals_report = ""（空字符串）
        → 实际数据在 messages 中（通过工具调用获取）

        如果 LLM 没有调用工具：
        → fundamentals_report = result.content（直接使用 LLM 的回复）

        这是一种"混合模式"：
        • LLM 可以主动调用工具获取数据（主动获取）
        • LLM 也可以基于已有信息直接回答（被动模式）

        两种情况下，报告最终都会通过 state 传递给后续节点。

    【参数】
        llm: LangChain 兼容的大语言模型
            例如：ChatOpenAI(model="gpt-4o")

    【返回值】
        fundamentals_analyst_node: 一个可调用的节点函数
    """

    def fundamentals_analyst_node(state):
        """
        【节点函数】基本面分析师的核心逻辑

        【参数详解：state】

            state 是 LangGraph 维护的"全局状态字典"。
            在基本面分析师节点执行前，state 中已经包含：

            state["trade_date"]
                → 当前模拟交易日期，格式 "YYYY-MM-DD"
                → 用于告知 LLM"今天是几号"，避免获取到未来数据

            state["company_of_interest"]
                → 要分析的股票代码，如 "NVDA"、"AAPL"
                → 用于构建 instrument_context

            state["messages"]
                → 历史对话消息（第一轮为空）
                → 包含之前分析师的回复，供本节点参考

        【返回值详解】

            返回一个字典，包含两个字段：

            1. messages: [result]
               → 将 LLM 的回复追加到 messages 中
               → 后续节点可以通过 state["messages"] 访问

            2. fundamentals_report: report
               → 分析师的报告内容
               → 传递给 bull/bear_researcher 进行辩论

        【LangChain Expression Language (LCEL)】

            ┌─────────────────────────────────────────────────────────────────────┐
            │                                                                       │
            │   chain = prompt | llm.bind_tools(tools)                             │
            │                │              │                                       │
            │                │              └── 将 tools 绑定到 llm                  │
            │                │                  使得 llm 可以调用这些工具           │
            │                │                                                           │
            │                └── prompt 的输出作为 llm 的输入                        │
            │                    这是 LangChain 的"管道操作符"                        │
            │                                                                       │
            └─────────────────────────────────────────────────────────────────────┘
        """

        # ─────────────────────────────────────────────────────────────────
        # 第一步：从 state 读取当前日期和公司上下文
        # ─────────────────────────────────────────────────────────────────

        current_date = state["trade_date"]

        # build_instrument_context() 构建公司背景信息
        # 包括：公司名称、行业、市值、当前价格等
        # 这些信息会注入到 Prompt 中，帮助 LLM 理解分析对象
        instrument_context = build_instrument_context(state["company_of_interest"])
        semantic_instruction = build_screener_semantic_instruction(state, "fundamentals")

        # ─────────────────────────────────────────────────────────────────
        # 第二步：定义工具列表
        # ─────────────────────────────────────────────────────────────────
        # 工具列表告诉 LLM"你有哪些手段可以获取数据"
        # LLM 会根据 Prompt 的指引自主决定调用哪个工具

        tools = get_tools_for_analyst("fundamentals", state["company_of_interest"])

        # 注意：get_insider_transactions 在 import 中，但未加入 tools 列表
        # 这是设计决策：内幕交易更多归类到社交媒体/情绪分析

        # ─────────────────────────────────────────────────────────────────
        # 第三步：构建系统提示词（System Message）
        # ─────────────────────────────────────────────────────────────────
        # 系统提示词是"角色定义"——告诉 LLM 扮演什么角色

        system_message = (
            # 角色定义：基本面研究员
            "You are a researcher tasked with analyzing fundamental information over the past week about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials, and company financial history to gain a full view of the company's fundamental information to inform traders. Make sure to include as much detail as possible. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            # 格式要求：Markdown 表格
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            # 工具使用说明
            + " Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial statements."
            + (f" {semantic_instruction}" if semantic_instruction else "")
            # 语言指令（支持多语言输出）
            + get_language_instruction()
        )

        # H3: Inject Skill and Screener Context
        from tradingagents.harness.skills import SkillInjector
        from tradingagents.harness.context import ScreenerContextInjector

        screener_context_str = ""
        if state.get("screener_context") and state["screener_context"].get("signal_card"):
            sc_injector = ScreenerContextInjector()
            screener_context_str = "\n\n" + sc_injector.build_context(
                state["screener_context"]["signal_card"]
            )

        skill_injector = SkillInjector()
        skill_section, _ = skill_injector.build_skill_section("fundamentals")

        system_message = system_message + screener_context_str + "\n" + skill_section

        # ─────────────────────────────────────────────────────────────────
        # 第四步：构建完整的 Prompt 模板
        # ─────────────────────────────────────────────────────────────────
        # ChatPromptTemplate 是 LangChain 的 Prompt 管理工具
        # MessagesPlaceholder(variable_name="messages") 是动态消息占位符
        # 第一轮时 messages 为空，后续轮次会包含历史对话

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "{shared_system_prompt}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        # ─────────────────────────────────────────────────────────────────
        # 第五步：填充 Prompt 中的变量
        # ─────────────────────────────────────────────────────────────────
        # .partial() 方法用于填充 Prompt 中的 {variable} 占位符
        # 填充后，Prompt 中的 {tool_names}、{current_date} 等变量被替换为具体值

        prompt = prompt.partial(system_message=system_message)

        # tool_names: 将工具列表转为逗号分隔的字符串
        # 例如："get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement"
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))

        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)
        prompt = prompt.partial(
            shared_system_prompt=build_collaboration_system_prompt(
                tool_names=", ".join([tool.name for tool in tools]),
                role_prompt=system_message,
                current_date=current_date,
                instrument_context=instrument_context,
            )
        )

        # ─────────────────────────────────────────────────────────────────
        # 第六步：构建 LCEL 链
        # ─────────────────────────────────────────────────────────────────
        # prompt | llm.bind_tools(tools)
        # → 先渲染 Prompt，再调用 LLM（带工具绑定）

        chain = prompt | llm.bind_tools(tools)
        #t | 操作符是 LangChain Expression Language (LCEL) 的核心。它的意思是：把左边的输出作为右边的输入。
        """"prompt (模板 + partial 变量)
                │
                │  ← 当 chain.invoke() 被调用时，LangChain 会：
                │     1. 先把 prompt 中的所有 {variable} 占位符用 .partial() 注入的值替换
                │     2. 渲染成最终的字符串
                │     3. 把渲染后的字符串传给 llm
                │
                ▼
            llm.bind_tools(tools)
                │
                │  ← llm 收到的是"渲染后的完整 Prompt"
                │     其中包含了：
                │     • {tool_names}  → "get_fundamentals, get_balance_sheet, ..."
                │     • {current_date} → "2024-06-15"
                │     • {instrument_context} → "公司名称、行业、市值..."
                │     • {system_message} → 角色定义和工具说明
                │
                ▼
            最终发送给 LLM 的完整消息
        """


        # ─────────────────────────────────────────────────────────────────
        # 第七步：执行链
        # ─────────────────────────────────────────────────────────────────
        # state["messages"] 是历史消息，第一轮为空列表
        # 执行后返回 AIMessage（可能包含 tool_calls）

        result = chain.invoke(state["messages"])

        # ─────────────────────────────────────────────────────────────────
        # 第八步：处理返回值
        # ─────────────────────────────────────────────────────────────────
        report = ""

        """
            【阶段 1：LLM 第一次调用（决定调用工具）】
            result = chain.invoke(state["messages"])
            │
            result.tool_calls = [
                {"name": "get_fundamentals", "args": {"ticker": "NVDA", "curr_date": "2024-06-15"}},
                {"name": "get_balance_sheet", "args": {...}},
                ...
            ]
            │
            result.content = ""  ← 还没有最终报告

            【LangChain 框架自动处理】自动执行工具，把结果添加到 messages，重新调用 LLM

            【阶段 2：LLM 第二次调用（生成最终报告）】
            result = chain.invoke(state["messages"])  ← 这次 state["messages"] 包含了工具返回的数据
            │
            result.tool_calls = []  ← 不再调用工具了
            result.content = "## Fundamentals Report\n\n..."  ← 最终报告
            │
            执行第 331 行的判断：
            if len(result.tool_calls) == 0:  → True
                report = result.content  ← 捕获最终报告


                这是 LangChain 的 ReAct Agent 默认行为：
                    chain.invoke() 会在框架层自动执行工具
                    工具执行和 LLM 再次调用对我们是透明的
                    result.content 最终包含的是工具执行后 LLM 生成的内容

        """

        # result.tool_calls: LLM 请求调用的工具列表
        # 如果为空，说明 LLM 没有调用工具，直接用回复内容作为报告
        if len(result.tool_calls) == 0:
            report = result.content

        # ─────────────────────────────────────────────────────────────────
        # 第九步：返回更新后的状态
        # ─────────────────────────────────────────────────────────────────

        return sync_report_updates(
            report_key="fundamentals",
            report_value=report,
            messages=[result],
            sender="Fundamentals Analyst",
        )

    return fundamentals_analyst_node
