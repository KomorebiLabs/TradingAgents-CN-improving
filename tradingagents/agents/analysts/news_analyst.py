"""
================================================================================
                       NEWS_ANALYST.PY 详解
                          新闻分析师节点
================================================================================

【模块定位】
    本文件是 TradingAgents 的"新闻分析师"节点。

    新闻分析关注的是外部事件对公司/市场的影响：
    • 宏观经济新闻（央行政策、通胀数据）
    • 行业动态（竞争对手动作、政策变化）
    • 公司特定新闻（财报发布、产品发布、管理层变动）

    与 social_media_analyst.py 的区别：
    ┌─────────────────┬─────────────────────────────┬─────────────────────────────┐
    │      维度        │      news_analyst           │   social_media_analyst     │
    ├─────────────────┼─────────────────────────────┼─────────────────────────────┤
    │   内容来源       │   新闻媒体（Reuters、Bloomberg）│  社交媒体 + 公众讨论       │
    │   覆盖范围       │   全球宏观经济 + 个股新闻      │   散户情绪 + 口碑          │
    │   信息特点       │   专业、正式、可能有时滞        │   即时、情绪化、噪声多     │
    │   工具           │   get_news + get_global_news  │   get_news（特定股票）      │
    └─────────────────┴─────────────────────────────┴─────────────────────────────┘

【两个工具的区别】

    get_news(ticker, start_date, end_date)
        → 针对特定股票的新闻
        → 例如：get_news("NVDA", "2024-01-01", "2024-01-07")
        → 用于分析"NVDA 这周有什么新闻"

    get_global_news(curr_date, look_back_days, limit)
        → 全球宏观经济新闻
        → 按主题过滤：financial_markets, economy_macro, economy_monetary
        → 用于分析"市场整体在发生什么"

【新闻分析的难点】
    新闻满天飞，但并非每条都有价值。新闻分析师需要：
    1. 筛选：哪些新闻真正影响股价？
    2. 判断：这条新闻是利好还是利空？
    3. 评估：影响是短期的还是长期的？
    4. 排序：哪些最重要，需要先关注？

【Prompt 设计要点】
    • 强调"全面报告"和"可操作的见解"
    • 要求分析"过去一周"的新闻（与模拟交易系统匹配）
    • 结尾必须加 Markdown 表格

================================================================================
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    build_screener_semantic_instruction,
    get_segment_advisory,
    get_language_instruction,
    get_tools_for_analyst,
    suppress_repeated_tool_calls,
)
from tradingagents.agents.prompts import build_collaboration_system_prompt
from tradingagents.agents.utils.state_helpers import sync_report_updates
from tradingagents.dataflows.config import get_config


def create_news_analyst(llm):
    """
    【工厂函数】创建新闻分析师节点

    【news_analyst_node 的工作流程】

        ┌─────────────────────────────────────────────────────────────────────┐
        │                                                                       │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 1: 工具选择                                              │   │
        │   │                                                               │   │
        │   │  两个工具：                                                   │   │
        │   │    • get_news("NVDA", "2024-01-01", "2024-01-07")           │   │
        │   │      → NVDA 的个股新闻                                        │   │
        │   │    • get_global_news("2024-01-07", 7, 50)                   │   │
        │   │      → 过去 7 天的全球宏观经济新闻                            │   │
        │   │                                                               │   │
        │   │  LLM 可以自主决定调用哪些工具                                 │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                               │                                      │
        │                               ▼                                      │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 2: 综合分析                                              │   │
        │   │                                                               │   │
        │   │  • 个股新闻 → 公司层面的影响                                  │   │
        │   │  • 宏观新闻 → 市场整体环境                                    │   │
        │   │  • 综合判断 → 哪些对交易决策有影响                            │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                               │                                      │
        │                               ▼                                      │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 3: 生成报告                                              │   │
        │   │                                                               │   │
        │   │  格式要求：                                                   │   │
        │   │    • 全面详尽                                                 │   │
        │   │    • 可操作的见解                                             │   │
        │   │    • Markdown 表格总结                                       │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                                                                       │
        └─────────────────────────────────────────────────────────────────────┘
    """

    def news_analyst_node(state):
        """
        【节点函数】新闻分析师的核心逻辑
        """

        # ─────────────────────────────────────────────────────────────────
        # 第一步：从 state 读取上下文
        # ─────────────────────────────────────────────────────────────────

        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])
        segment_advisory = get_segment_advisory(state["company_of_interest"], "news")
        semantic_instruction = build_screener_semantic_instruction(state, "news")

        # ─────────────────────────────────────────────────────────────────
        # 第二步：定义工具列表
        # ─────────────────────────────────────────────────────────────────
        # 两个工具的组合覆盖：
        # 1. get_news → 个股新闻（公司发生了什么）
        # 2. get_global_news → 宏观新闻（市场环境如何）

        tools = get_tools_for_analyst("news", state["company_of_interest"])

        # ─────────────────────────────────────────────────────────────────
        # 第三步：构建系统提示词
        # ─────────────────────────────────────────────────────────────────
        # Prompt 强调：
        # 1. 分析"过去一周"的相关新闻
        # 2. 关注宏观经济学和交易相关内容
        # 3. 提供可操作的见解

        system_message = (
            "You are a news researcher tasked with analyzing recent news and trends over the past week. Please write a comprehensive report of the current state of the world that is relevant for trading and macroeconomics. Use the available tools: get_news(query, start_date, end_date) for company-specific or targeted news searches, and get_global_news(curr_date, look_back_days, limit) for broader macroeconomic news. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + " When available for mainland China growth or STAR-board names, use get_cn_policy_news(curr_date, look_back_days, limit) to inspect policy, regulation, liquidity, and technology-cycle catalysts."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + (f" {segment_advisory}" if segment_advisory else "")
            + (f" {semantic_instruction}" if semantic_instruction else "")
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
        skill_section, _ = skill_injector.build_skill_section("news")

        system_message = system_message + screener_context_str + "\n" + skill_section

        # ─────────────────────────────────────────────────────────────────
        # 第四步：构建 Prompt 模板
        # ─────────────────────────────────────────────────────────────────

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
        # 第五步：填充变量
        # ─────────────────────────────────────────────────────────────────

        prompt = prompt.partial(system_message=system_message)
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
        # 第六步：构建链并执行
        # ─────────────────────────────────────────────────────────────────

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])
        suppress_repeated_tool_calls(result, state["messages"], "News analyst")

        # ─────────────────────────────────────────────────────────────────
        # 第七步：处理返回值
        # ─────────────────────────────────────────────────────────────────

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        # ─────────────────────────────────────────────────────────────────
        # 第八步：返回更新后的状态
        # ─────────────────────────────────────────────────────────────────

        return sync_report_updates(
            report_key="news",
            report_value=report,
            messages=[result],
            sender="News Analyst",
        )

    return news_analyst_node
