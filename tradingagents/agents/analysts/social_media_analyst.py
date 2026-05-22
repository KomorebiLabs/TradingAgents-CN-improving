"""
================================================================================
                   SOCIAL_MEDIA_ANALYST.PY 详解
                      社交媒体分析师节点
================================================================================

【模块定位】
    本文件是 TradingAgents 的"社交媒体分析师"节点。

    社交媒体分析关注的是：
    • 散户/公众对公司的看法
    • 社交媒体上的讨论热度
    • 情绪数据（看多还是看空）

    这是基本面分析和新闻分析的补充——
    有时候，股价的涨跌不是因为财报或新闻，
    而是因为"大家在说什么"。

【与 news_analyst.py 的对比】

    ┌─────────────────┬─────────────────────────────┬─────────────────────────────┐
    │      维度        │     news_analyst            │   social_media_analyst     │
    ├─────────────────┼─────────────────────────────┼─────────────────────────────┤
    │   数据来源       │   新闻媒体（Reuters等）       │   社交媒体 + 论坛          │
    │   内容风格       │   专业报道、事实为主          │   个人观点、情绪为主        │
    │   覆盖范围       │   全球宏观经济 + 个股         │   公司相关讨论              │
    │   分析重点       │   事件影响评估               │   情绪倾向分析              │
    │   工具           │   get_news + get_global_news │   get_news（特定股票）      │
    └─────────────────┴─────────────────────────────┴─────────────────────────────┘

【为什么只用 get_news？】

    social_media_analyst 只绑定了 get_news 一个工具，没有 get_global_news。

    原因：社交媒体分析的核心是"特定公司的公众情绪"，
    不需要全球宏观经济新闻。

    对比：
    • news_analyst 需要两个工具：
      → get_news → 个股新闻
      → get_global_news → 宏观新闻

    • social_media_analyst 只需要一个工具：
      → get_news → 搜索公司相关新闻和社交讨论

【Prompt 设计要点】

    1. 强调"情绪分析"：
       → 分析散户每天的情绪倾向
       → 看人们对公司是什么看法

    2. 要求"全面报告"：
       → 社交媒体 + 新闻 + 情绪数据
       → 多种来源交叉验证

    3. 特别提到"Try to look at all sources possible"：
       → 鼓励 LLM 尽可能多地搜索不同来源
       → 避免单一来源带来的偏差

【情绪数据的价值】

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  案例：GameStop (GME) 散户逼空事件 (2021年1月)                          │
    │                                                                           │
    │  事件回顾：                                                              │
    │    • Reddit WallStreetBets 社区大量讨论 GME                              │
    │    • 散户情绪极度看多，互相鼓励买入                                      │
    │    • 股价从 $20 涨到 $483（涨幅 2300%）                                  │
    │                                                                           │
    │  教训：                                                                 │
    │    • 基本面（GameStop 业绩很差）无法解释这种涨幅                          │
    │    • 但社交媒体情绪可以提前预警（情绪极度亢奋）                           │
    │    • 社交媒体分析可以捕捉到"散户群体行为"                                │
    │                                                                           │
    │  风险：                                                                 │
    │    • 社交媒体噪声很大                                                    │
    │    • 情绪容易被操纵（唱多出货）                                          │
    │    • 需要结合其他分析一起看                                              │
    └─────────────────────────────────────────────────────────────────────────┘

================================================================================
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.prompts import build_collaboration_system_prompt
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    build_screener_semantic_instruction,
    get_language_instruction,
    get_tools_for_analyst,
)
from tradingagents.agents.utils.state_helpers import sync_report_updates
from tradingagents.dataflows.config import get_config


def create_social_media_analyst(llm):
    """
    【工厂函数】创建社交媒体分析师节点

    【social_media_analyst_node 的工作流程】

        ┌─────────────────────────────────────────────────────────────────────┐
        │                                                                       │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 1: 搜索公司相关新闻                                        │   │
        │   │                                                               │   │
        │   │  工具：get_news(ticker, start_date, end_date)                  │   │
        │   │  范围：过去一周的社交媒体讨论 + 新闻                            │   │
        │   │                                                               │   │
        │   │  示例：get_news("NVDA", "2024-01-01", "2024-01-07")           │   │
        │   │    → 搜索 NVDA 过去 7 天的相关讨论                            │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                               │                                      │
        │                               ▼                                      │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 2: 情绪分析                                              │   │
        │   │                                                               │   │
        │   │  • 正面评论 vs 负面评论 → 整体倾向                            │   │
        │   │  • 讨论热度 → 是否是热门话题                                  │   │
        │   │  • 情绪变化 → 一周内是否有显著变化                            │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                               │                                      │
        │                               ▼                                      │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 3: 生成报告                                              │   │
        │   │                                                               │   │
        │   │  格式要求：                                                   │   │
        │   │    • 长篇报告                                                  │   │
        │   │    • 包含洞察和对交易者的建议                                  │   │
        │   │    • Markdown 表格总结                                        │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                                                                       │
        └─────────────────────────────────────────────────────────────────────┘
    """

    def social_media_analyst_node(state):
        """
        【节点函数】社交媒体分析师的核心逻辑
        """

        # ─────────────────────────────────────────────────────────────────
        # 第一步：从 state 读取上下文
        # ─────────────────────────────────────────────────────────────────

        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])
        semantic_instruction = build_screener_semantic_instruction(state, "social")

        # ─────────────────────────────────────────────────────────────────
        # 第二步：定义工具列表
        # ─────────────────────────────────────────────────────────────────
        # 注意：只有 get_news 一个工具
        # 这是与 news_analyst.py 的关键区别

        tools = get_tools_for_analyst("social", state["company_of_interest"])

        # ─────────────────────────────────────────────────────────────────
        # 第三步：构建系统提示词
        # ─────────────────────────────────────────────────────────────────
        # Prompt 强调：
        # 1. 分析社交媒体帖子和公众情绪
        # 2. 分析每天的情绪数据
        # 3. 尽可能看所有可能的来源

        system_message = (
            "You are a social media and company specific news researcher/analyst tasked with analyzing social media posts, recent company news, and public sentiment for a specific company over the past week. You will be given a company's name your objective is to write a comprehensive long report detailing your analysis, insights, and implications for traders and investors on this company's current state after looking at social media and what people are saying about that company, analyzing sentiment data of what people feel each day about the company, and looking at recent company news. Use the get_news(query, start_date, end_date) tool to search for company-specific news and social media discussions. Try to look at all sources possible from social media to sentiment to news. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
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
        skill_section = skill_injector.build_skill_section("social")

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

        # ─────────────────────────────────────────────────────────────────
        # 第七步：处理返回值
        # ─────────────────────────────────────────────────────────────────

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        # ─────────────────────────────────────────────────────────────────
        # 第八步：返回更新后的状态
        # ─────────────────────────────────────────────────────────────────
        # 返回字段名是 sentiment_report（情绪报告）
        # 与 news_report 不同

        return sync_report_updates(
            report_key="sentiment",
            report_value=report,
            messages=[result],
            sender="Social Analyst",
        )

    return social_media_analyst_node
