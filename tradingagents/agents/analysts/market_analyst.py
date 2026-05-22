"""
================================================================================
                      MARKET_ANALYST.PY 详解
                          市场技术分析师节点
================================================================================

【模块定位】
    本文件是 TradingAgents 的"市场技术分析师"节点。

    与 fundamentals_analyst.py 的区别：
    ┌─────────────────┬─────────────────────────────┬─────────────────────────────┐
    │      维度        │   fundamentals_analyst      │     market_analyst         │
    ├─────────────────┼─────────────────────────────┼─────────────────────────────┤
    │   分析角度       │   公司内在价值               │     价格走势和技术指标      │
    │   关注点         │   财务报表、盈利能力          │     趋势、动量、波动性      │
    │   数据来源       │   基本面 API                 │     历史行情 + 指标 API    │
    │   核心问题       │   "这家公司值多少钱？"        │     "现在该买还是卖？"     │
    └─────────────────┴─────────────────────────────┴─────────────────────────────┘

【技术分析的核心思想】
    技术分析认为：市场的所有信息（基本面、情绪、政策）都反映在价格中。
    通过分析历史价格和成交量，可以预测未来走势。

    三大假设（技术分析三大前提）：
    1. 市场行为包容一切（价格反映所有信息）
    2. 趋势具有惯性（历史会重演）
    3. 价格沿趋势移动（顺势而为）

【本文件的工具】
    • get_stock_data    → 获取 OHLCV 历史行情
    • get_indicators   → 获取技术指标

    重要：Prompt 明确要求"先调用 get_stock_data，再调用 get_indicators"
    因为 get_indicators 需要行情数据作为基础。

【指标分类（Prompt 中的核心内容）】

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                     技术指标 4 大类别                                     │
    ├─────────────────────────────────────────────────────────────────────────┤
    │                                                                         │
    │  【趋势指标】— 判断市场方向（向上/向下/震荡）                              │
    │    close_50_sma   → 50日均线，中期趋势                                  │
    │    close_200_sma  → 200日均线，长期趋势                                 │
    │    close_10_ema   → 10日指数均线，短期动量                              │
    │                                                                         │
    │  【动量指标】— 判断涨跌力度（速度）                                       │
    │    macd           → MACD 主线                                           │
    │    macds          → MACD 信号线                                         │
    │    macdh          → MACD 柱状图                                         │
    │    rsi            → 相对强弱指数                                         │
    │                                                                         │
    │  【波动性指标】— 判断波动大小（震幅）                                     │
    │    boll           → 布林带中轨                                          │
    │    boll_ub        → 布林带上轨                                          │
    │    boll_lb        → 布林带下轨                                          │
    │    atr            → 平均真实波幅                                         │
    │                                                                         │
    │  【成交量指标】— 判断参与热度                                            │
    │    vwma           → 成交量加权移动平均                                   │
    │                                                                         │
    └─────────────────────────────────────────────────────────────────────────┘

【Prompt 设计要点】

    1. 指标选择策略：
       → 从 4 大类别中选，总数不超过 8 个
       → 要求"互补"而非"冗余"
       → 例如：不同时选 RSI 和 StochRSI（两者太相似）

    2. 分析要求：
       → 非常详细和细致的趋势报告
       → 提供"可操作的见解"（如"RSI 超买，可能回调"）
       → 结尾必须加 Markdown 表格

    3. 使用顺序：
       → 必须先 get_stock_data 获取原始行情
       → 再用 get_indicators 获取指标

================================================================================
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    build_screener_semantic_instruction,
    get_segment_advisory,
    get_tools_for_analyst,
    get_language_instruction,
)
from tradingagents.agents.prompts import build_collaboration_system_prompt
from tradingagents.agents.utils.state_helpers import sync_report_updates
from tradingagents.dataflows.config import get_config


def create_market_analyst(llm):
    """
    【工厂函数】创建市场分析师节点

    【market_analyst_node 的工作流程】

        ┌─────────────────────────────────────────────────────────────────────┐
        │                                                                       │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 1: 构建 Prompt                                          │   │
        │   │                                                               │   │
        │   │  system_message 包含：                                        │   │
        │   │  • 4 大类指标的详细说明和用法                                  │   │
        │   │  • 指标选择的策略（互补、不超过 8 个）                          │   │
        │   │  • 使用顺序要求（先行情，后指标）                              │   │
        │   │  • 输出格式要求（Markdown 表格）                              │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                               │                                      │
        │                               ▼                                      │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 2: LLM 决定                                              │   │
        │   │                                                               │   │
        │   │  LLM 分析 Prompt，发现需要数据                                 │   │
        │   │       ↓                                                       │   │
        │   │  调用 get_stock_data → 获取 OHLCV 行情                        │   │
        │   │       ↓                                                       │   │
        │   │  调用 get_indicators → 获取技术指标                           │   │
        │   │       ↓                                                       │   │
        │   │  基于数据生成报告                                              │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                               │                                      │
        │                               ▼                                      │
        │   ┌───────────────────────────────────────────────────────────────┐   │
        │   │  Step 3: 返回 state 更新                                      │   │
        │   │                                                               │   │
        │   │  {                                                           │   │
        │   │      "messages": [result],     // LLM 回复（含工具调用）       │   │
        │   │      "market_report": report   // 报告内容                    │   │
        │   │  }                                                           │   │
        │   └───────────────────────────────────────────────────────────────┘   │
        │                                                                       │
        └─────────────────────────────────────────────────────────────────────┘
    """

    def market_analyst_node(state):
        """
        【节点函数】市场分析师的核心逻辑
        """

        # ─────────────────────────────────────────────────────────────────
        # 第一步：从 state 读取上下文
        # ─────────────────────────────────────────────────────────────────

        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])
        segment_advisory = get_segment_advisory(state["company_of_interest"], "market")
        semantic_instruction = build_screener_semantic_instruction(state, "market")

        # ─────────────────────────────────────────────────────────────────
        # 第二步：定义工具列表
        # ─────────────────────────────────────────────────────────────────
        # 注意：工具只有 2 个，但 Prompt 要求"先 get_stock_data，后 get_indicators"
        # LLM 会自动遵守这个顺序

        tools = get_tools_for_analyst("market", state["company_of_interest"])

        # ─────────────────────────────────────────────────────────────────
        # 第三步：构建系统提示词（这是最关键的部分）
        # ─────────────────────────────────────────────────────────────────
        # system_message 非常长，因为需要详细告诉 LLM：
        # 1. 每个指标是什么
        # 2. 怎么用
        # 3. 选哪些
        # 4. 选多少

        system_message = (
            # 角色定义
            """You are a trading assistant tasked with analyzing financial markets. Your role is to select the **most relevant indicators** for a given market condition or trading strategy from the following list. The goal is to choose up to **8 indicators** that provide complementary insights without redundancy. Categories and each category's indicators are:

# Moving Averages (趋势指标):
- close_50_sma: 50 SMA: A medium-term trend indicator. Usage: Identify trend direction and serve as dynamic support/resistance. Tips: It lags price; combine with faster indicators for timely signals.
- close_200_sma: 200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend and identify golden/death cross setups. Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries.
- close_10_ema: 10 EMA: A responsive short-term average. Usage: Capture quick shifts in momentum and potential entry points. Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals.

# MACD Related (动量指标):
- macd: MACD: Computes momentum via differences of EMAs. Usage: Look for crossovers and divergence as signals of trend changes. Tips: Confirm with other indicators in low-volatility or sideways markets.
- macds: MACD Signal: An EMA smoothing of the MACD line. Usage: Use crossovers with the MACD line to trigger trades. Tips: Should be part of a broader strategy to avoid false positives.
- macdh: MACD Histogram: Shows the gap between the MACD line and its signal. Usage: Visualize momentum strength and spot divergence early. Tips: Can be volatile; complement with additional filters in fast-moving markets.

# Momentum Indicators (动量指标):
- rsi: RSI: Measures momentum to flag overbought/oversold conditions. Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis.

# Volatility Indicators (波动性指标):
- boll: Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. Usage: Acts as a dynamic benchmark for price movement. Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals.
- boll_ub: Bollinger Upper Band: Typically 2 standard deviations above the middle line. Usage: Signals potential overbought conditions and breakout zones. Tips: Confirm signals with other tools; prices may ride the band in strong trends.
- boll_lb: Bollinger Lower Band: Typically 2 standard deviations below the middle line. Usage: Indicates potential oversold conditions. Tips: Use additional analysis to avoid false reversal signals.
- atr: ATR: Averages true range to measure volatility. Usage: Set stop-loss levels and adjust position sizes based on current market volatility. Tips: It's a reactive measure, so use it as part of a broader risk management strategy.

# Volume-Based Indicators (成交量指标):
- vwma: VWMA: A moving average weighted by volume. Usage: Confirm trends by integrating price action with volume data. Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses.

# 指标选择策略:
- Select indicators that provide diverse and complementary information.
- Avoid redundancy (e.g., do not select both rsi and stochrsi).
- Briefly explain why they are suitable for the given market context.
- When you tool call, please use the exact name of the indicators provided above as they are defined parameters.
- **CRITICAL: Please make sure to call get_stock_data first to retrieve the CSV that is needed to generate indicators.**
- Then use get_indicators with the specific indicator names.
- When available for mainland China growth-oriented or liquidity-fragile names, use get_cn_market_flow to inspect main-force flow, execution pressure, and liquidity proxy signals.
- Write a very detailed and nuanced report of the trends you observe.
- Provide specific, actionable insights with supporting evidence to help traders make informed decisions."""
            # 格式要求
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + (f" {segment_advisory}" if segment_advisory else "")
            + (f" {semantic_instruction}" if semantic_instruction else "")
            # 语言指令
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
        skill_section = skill_injector.build_skill_section("market")

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
            # LLM 没有调用工具，直接用回复作为报告
            report = result.content

        # ─────────────────────────────────────────────────────────────────
        # 第八步：返回更新后的状态
        # ─────────────────────────────────────────────────────────────────

        return sync_report_updates(
            report_key="market",
            report_value=report,
            messages=[result],
            sender="Market Analyst",
        )

    return market_analyst_node
