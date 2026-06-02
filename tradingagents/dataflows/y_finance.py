"""
================================================================================
                        Y_FINANCE.PY 详解
                   Yahoo Finance 数据源实现层
================================================================================

【模块定位】
    本文件是 TradingAgents 数据获取层的"第二数据源"（备用数据源）。

    在项目中的定位：
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                        interface.py (路由层)                             │
    │                              │                                          │
    │              VENDOR_METHODS["get_stock_data"]["yfinance"] 指向这里      │
    └─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                        y_finance.py (当前文件)                          │
    │                                                                          │
    │  当 Alpha Vantage 触发 RateLimit 错误时，route_to_vendor() 会自动      │
    │  回退到本文件中的函数，作为"备用数据源"获取数据。                          │
    │                                                                          │
    │  核心职责：                                                              │
    │    1. get_YFin_data_online()        → 获取 OHLCV 股票行情                │
    │    2. get_stock_stats_indicators_window() → 获取技术指标（SMA, RSI 等）  │
    │    3. get_fundamentals()            → 获取公司基本面概览                 │
    │    4. get_balance_sheet()           → 获取资产负债表                     │
    │    5. get_cashflow()                → 获取现金流量表                     │
    │    6. get_income_statement()        → 获取利润表                        │
    │    7. get_insider_transactions()    → 获取内幕交易数据                   │
    │                                                                          │
    └─────────────────────────────────────────────────────────────────────────┘

【为什么需要 yfinance 作为备用？】
    • Alpha Vantage 免费版限制：5次/分钟，25次/天
    • yfinance 几乎无限制，可以"兜底"
    • 设计模式：优雅降级 (Graceful Degradation)

【与 Alpha Vantage 的对比】
    ┌─────────────────┬─────────────────────┬─────────────────────────────┐
    │     维度        │    Alpha Vantage    │        yfinance            │
    ├─────────────────┼─────────────────────┼─────────────────────────────┤
    │     限制        │    严格（5次/分钟）  │    几乎无限制               │
    │     收费        │    免费额度有限       │    完全免费                  │
    │     数据质量     │    专业级            │    依赖 Yahoo 数据源          │
    │     技术指标     │    API 直接计算      │    需用 stockstats 库计算    │
    │     新闻        │    NEWS_SENTIMENT API │    yf.Search() 搜索         │
    └─────────────────┴─────────────────────┴─────────────────────────────┘

================================================================================
"""

# ==============================================================================
# 导入层解析
# ==============================================================================
# 本文件使用的外部依赖：
#   • typing.Annotated        → 为函数参数添加元数据描述（供 LLM 理解参数含义）
#   • datetime                → 日期时间处理
#   • dateutil.relativedelta  → 灵活的日期计算（如 curr_date - days）
#   • pandas as pd            → 数据处理（DataFrame）
#   • yfinance as yf          → Yahoo Finance Python 包（核心数据源）
#   • stockstats_utils        → 本地技术指标计算工具（见下方详解）

from typing import Annotated
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import yfinance as yf
import os
# 【教学】stockstats_utils 是本项目的"技术指标计算引擎"
# 为什么需要它？因为 yfinance 返回的只是原始价格数据
# 技术指标（SMA, RSI, MACD 等）需要额外计算，stockstats 就是这个计算器
from .stockstats_utils import StockstatsUtils, _clean_dataframe, yf_retry, load_ohlcv, filter_financials_by_date


# ==============================================================================
# 函数 1: get_YFin_data_online() — 获取股票 OHLCV 行情数据
# ==============================================================================

def get_YFin_data_online(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
):
    """
    【函数功能】
        获取指定股票的历史 OHLCV（开盘价、最高价、最低价、收盘价、成交量）数据。

    【在项目中的角色】
        这是 interface.py 中 VENDOR_METHODS["get_stock_data"]["yfinance"] 的实现。
        当 Alpha Vantage 不可用时，本函数作为"备用数据源"被调用。

    【数据流】
        调用者 (route_to_vendor)
                │
                ▼
        get_YFin_data_online("NVDA", "2024-01-01", "2024-12-31")
                │
                ├──► yf.Ticker("NVDA")       → 创建 Ticker 对象
                ├──► ticker.history()          → 获取历史行情
                ├──► yf_retry()               → 带重试的请求（防止临时失败）
                ├──► 数据清洗                  → 去时区、保留2位小数
                └──► 转换为 CSV 字符串         → 返回给 LLM 阅读

    【返回值示例】
        # Stock data for NVDA from 2024-01-01 to 2024-12-31
        # Total records: 252
        # Data retrieved on: 2024-12-31 15:30:00

        Date,Open,High,Low,Close,Adj Close,Volume
        2024-01-02,480.00,485.50,478.00,482.00,482.00,45000000
        ...
    """

    # 【教学】验证日期格式是否正确
    # 如果格式不对，strptime 会抛出异常，这是最简单的"防御性编程"
    # 【面试点】这里只验证，不处理异常 —— 异常会向上传播，由调用者处理
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    # Create ticker object
    # 【教学】yf.Ticker() 是 yfinance 的核心类
    # 它封装了对 Yahoo Finance API 的所有访问
    # 注意：symbol.upper() 确保股票代码是大写（Yahoo Finance 兼容）
    ticker = yf.Ticker(symbol.upper())

    # Fetch historical data for the specified date range
    # 【教学】ticker.history() 返回 pandas DataFrame
    # 参数：start=开始日期, end=结束日期
    # yf_retry 是一个包装器，增加重试逻辑（见 stockstats_utils.py）
    data = yf_retry(lambda: ticker.history(start=start_date, end=end_date))

    # Check if data is empty
    # 【教学】检查数据是否为空
    # 可能的原因：
    #   • 股票代码错误
    #   • 日期范围超出交易日
    #   • Yahoo Finance 暂时不可用
    if data.empty:
        return (
            f"No data found for symbol '{symbol}' between {start_date} and {end_date}"
        )

    # Remove timezone info from index for cleaner output
    # 【教学】DataFrame 的索引（Date）是带时区的
    # 去掉时区信息，让输出更简洁，也避免 LLM 看到时区感到困惑
    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    # Round numerical values to 2 decimal places for cleaner display
    # 【教学】价格数据保留2位小数，减少 token 消耗（对 LLM 很重要！）
    # 注意：只对价格列处理，Volume 是整数，不需要处理
    numeric_columns = ["Open", "High", "Low", "Close", "Adj Close"]
    for col in numeric_columns:
        if col in data.columns:
            data[col] = data[col].round(2)

    # Convert DataFrame to CSV string
    # 【教学】DataFrame.to_csv() 是 pandas 内置方法
    # 返回 CSV 格式的字符串，方便 LLM 读取
    csv_string = data.to_csv()

    # Add header information
    # 【教学】添加人类可读的头部信息
    # LLM 会"看到"这些注释，有助于理解数据来源和范围
    header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(data)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    return header + csv_string


# ==============================================================================
# 函数 2: get_stock_stats_indicators_window() — 获取技术指标时间窗口数据
# ==============================================================================

def get_stock_stats_indicators_window(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[
        str, "The current trading date you are trading on, YYYY-mm-dd"
    ],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:
    """
    【函数功能】
        获取指定时间段内的技术指标数值序列。

    【在项目中的角色】
        这是 interface.py 中 VENDOR_METHODS["get_indicators"]["yfinance"] 的实现。
        与 Alpha Vantage 不同，yfinance 版本使用本地 stockstats 库计算指标。

    【技术指标支持列表】
        ┌─────────────────┬───────────────────────────────────────────────────────┐
        │      类别       │                     指标名称                            │
        ├─────────────────┼───────────────────────────────────────────────────────┤
        │   移动平均线    │  close_50_sma, close_200_sma, close_10_ema          │
        │   MACD 系列     │  macd, macds (Signal), macdh (Histogram)              │
        │   动量指标      │  rsi (相对强弱指数)                                     │
        │   波动率指标    │  boll (布林带中轨), boll_ub (上轨), boll_lb (下轨), atr │
        │   成交量指标    │  vwma (成交量加权平均), mfi (资金流量指数)               │
        └─────────────────┴───────────────────────────────────────────────────────┘

    【数据流】
        输入：symbol="NVDA", indicator="rsi", curr_date="2024-12-31", look_back_days=14
                │
                ▼
        方案 A（优先）：_get_stock_stats_bulk() — 批量计算
                │
                ├──► load_ohlcv() 一次性获取数据
                ├──► stockstats 计算所有指标
                └──► 遍历日期查表，返回数值

                ▼

        方案 B（回退）：get_stockstats_indicator() — 逐日计算
                └── 循环调用 StockstatsUtils.get_stock_stats()

    【返回值示例】
        ## rsi values from 2024-12-17 to 2024-12-31:

        2024-12-17: 65.23
        2024-12-18: 68.45
        2024-12-19: N/A: Not a trading day (weekend or holiday)
        ...

        RSI: Measures momentum to flag overbought/oversold conditions.
        Usage: Apply 70/30 thresholds and watch for divergence to signal reversals.
        ...
    """

    # 【教学】best_ind_params 是一个"指标元数据字典"==给LLM的说明书！
    # 为什么需要它？因为 yfinance 本身不提供指标的解释
    # 这个字典为每个指标提供了：
    #   1. 中文名称（隐含）
    #   2. 用途说明（Usage）
    #   3. 使用技巧（Tips）
    # LLM 会在给分析师的 prompt 中包含这些信息，帮助分析师理解指标含义
    best_ind_params = {
        # Moving Averages
        "close_50_sma": (
            "50 SMA: A medium-term trend indicator. "
            "Usage: Identify trend direction and serve as dynamic support/resistance. "
            "Tips: It lags price; combine with faster indicators for timely signals."
        ),
        "close_200_sma": (
            "200 SMA: A long-term trend benchmark. "
            "Usage: Confirm overall market trend and identify golden/death cross setups. "
            "Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries."
        ),
        "close_10_ema": (
            "10 EMA: A responsive short-term average. "
            "Usage: Capture quick shifts in momentum and potential entry points. "
            "Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals."
        ),
        # MACD Related
        "macd": (
            "MACD: Computes momentum via differences of EMAs. "
            "Usage: Look for crossovers and divergence as signals of trend changes. "
            "Tips: Confirm with other indicators in low-volatility or sideways markets."
        ),
        "macds": (
            "MACD Signal: An EMA smoothing of the MACD line. "
            "Usage: Use crossovers with the MACD line to trigger trades. "
            "Tips: Should be part of a broader strategy to avoid false positives."
        ),
        "macdh": (
            "MACD Histogram: Shows the gap between the MACD line and its signal. "
            "Usage: Visualize momentum strength and spot divergence early. "
            "Tips: Can be volatile; complement with additional filters in fast-moving markets."
        ),
        # Momentum Indicators
        "rsi": (
            "RSI: Measures momentum to flag overbought/oversold conditions. "
            "Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. "
            "Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis."
        ),
        # Volatility Indicators
        "boll": (
            "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. "
            "Usage: Acts as a dynamic benchmark for price movement. "
            "Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals."
        ),
        "boll_ub": (
            "Bollinger Upper Band: Typically 2 standard deviations above the middle line. "
            "Usage: Signals potential overbought conditions and breakout zones. "
            "Tips: Confirm signals with other tools; prices may ride the band in strong trends."
        ),
        "boll_lb": (
            "Bollinger Lower Band: Typically 2 standard deviations below the middle line. "
            "Usage: Indicates potential oversold conditions. "
            "Tips: Use additional analysis to avoid false reversal signals."
        ),
        "atr": (
            "ATR: Averages true range to measure volatility. "
            "Usage: Set stop-loss levels and adjust position sizes based on current market volatility. "
            "Tips: It's a reactive measure, so use it as part of a broader risk management strategy."
        ),
        # Volume-Based Indicators
        "vwma": (
            "VWMA: A moving average weighted by volume. "
            "Usage: Confirm trends by integrating price action with volume data. "
            "Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses."
        ),
        "mfi": (
            "MFI: The Money Flow Index is a momentum indicator that uses both price and volume to measure buying and selling pressure. "
            "Usage: Identify overbought (>80) or oversold (<20) conditions and confirm the strength of trends or reversals. "
            "Tips: Use alongside RSI or MACD to confirm signals; divergence between price and MFI can indicate potential reversals."
        ),
    }

    # 【教学】验证指标名称是否支持
    # 如果不支持，抛出 ValueError，让调用者知道参数错误
    if indicator not in best_ind_params:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(best_ind_params.keys())}"
        )

    # 【教学】计算日期范围
    # end_date = curr_date（当前交易日）
    # start_date = curr_date - look_back_days（往前推 N 天）
    end_date = curr_date
    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)

    # Optimized: Get stock data once and calculate indicators for all dates
    # 【教学】优化的批量计算模式
    # 原理：一次性加载所有数据，用 stockstats 库批量计算指标
    # 优势：比逐日计算快 10-50 倍（减少 API 调用和网络延迟）
    try:
        indicator_data = _get_stock_stats_bulk(symbol, indicator, curr_date)
        
        # Generate the date range we need
        # 【教学】遍历日期范围，逐日查询指标值
        current_dt = curr_date_dt
        date_values = []
        
        while current_dt >= before:
            date_str = current_dt.strftime('%Y-%m-%d')
            
            # Look up the indicator value for this date
            # 【教学】查表获取指标值
            # 注意：如果日期不是交易日（周末/假日），指标值为 "N/A"
            if date_str in indicator_data:
                indicator_value = indicator_data[date_str]
            else:
                indicator_value = "N/A: Not a trading day (weekend or holiday)"
            
            date_values.append((date_str, indicator_value))
            current_dt = current_dt - relativedelta(days=1)
        
        # Build the result string
        # 【教学】构建返回字符串
        # 格式：日期: 指标值（每行一个日期）
        ind_string = ""
        for date_str, value in date_values:
            ind_string += f"{date_str}: {value}\n"
        
    except Exception as e:
        # 【教学】回退机制：如果批量计算失败，使用逐日计算
        # 可能的原因：
        #   • stockstats 库计算出错
        #   • 数据格式异常
        #   • 网络临时问题
        print(f"Error getting bulk stockstats data: {e}")
        ind_string = ""
        curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        while curr_date_dt >= before:
            indicator_value = get_stockstats_indicator(
                symbol, indicator, curr_date_dt.strftime("%Y-%m-%d")
            )
            ind_string += f"{curr_date_dt.strftime('%Y-%m-%d')}: {indicator_value}\n"
            curr_date_dt = curr_date_dt - relativedelta(days=1)

    # 【教学】组装最终返回字符串
    # 包含：日期范围 + 指标数值序列 + 指标解释（元数据）
    result_str = (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {end_date}:\n\n"
        + ind_string
        + "\n\n"
        + best_ind_params.get(indicator, "No description available.")
    )

    return result_str


# ==============================================================================
# 函数 3: _get_stock_stats_bulk() — 批量计算技术指标（内部函数）
# ==============================================================================

def _get_stock_stats_bulk(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to calculate"],
    curr_date: Annotated[str, "current date for reference"]
) -> dict:
    """
    【函数功能】
        一次性加载历史数据，批量计算技术指标。

    【设计思想】
        这是一个"优化函数"，用于替代逐日计算。

        ┌─────────────────────────────────────────────────────────────────────┐
        │                      性能对比                                       │
        ├─────────────────────────────────────────────────────────────────────┤
        │                                                                     │
        │   逐日计算（旧方案）：                                               │
        │   for day in range(100):                                           │
        │       get_stockstats_indicator()  ← 每次都查 Yahoo Finance API      │
        │   总耗时：100 次网络请求 + 100 次计算 = 约 30 秒                    │
        │                                                                     │
        │   批量计算（新方案）：                                               │
        │   load_ohlcv()              ← 1 次网络请求                         │
        │   stockstats.batch_calc()    ← 本地计算                             │
        │   总耗时：1 次网络请求 + 1 次计算 = 约 1 秒                          │
        │                                                                     │
        └─────────────────────────────────────────────────────────────────────┘

    【返回值格式】
        {
            "2024-12-17": "65.23",
            "2024-12-18": "68.45",
            "2024-12-19": "N/A",
            ...
        }

    【注意】这是一个内部函数（下划线开头）
        外部不应该直接调用它，而是通过 get_stock_stats_indicators_window()
    """
    from stockstats import wrap

    # 【教学】load_ohlcv() 是 stockstats_utils.py 中的函数
    # 一次性获取指定股票的历史 OHLCV 数据
    # 返回值已经是清洗过的 DataFrame
    data = load_ohlcv(symbol, curr_date)

    # 【教学】stockstats.wrap() 是 stockstats 库的"魔法函数"
    # 它的作用：
    #   • 将普通 DataFrame 包装成 StockDataFrame
    #   • StockDataFrame 支持"属性访问"计算指标
    #   • 例如：df["close"] 返回收盘价，df["rsi"] 返回 RSI 值
    df = wrap(data)

    # 【教学】将日期列转换为字符串格式 "YYYY-MM-DD"
    # 这是为了后续查表方便
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    
    # Calculate the indicator for all rows at once
    # 【教学】触发 stockstats 计算指标
    # 技巧：在 Python 中，访问 df[indicator] 就会触发计算
    # stockstats 会根据列名（如 "rsi", "macd"）自动计算对应指标
    df[indicator]  # This triggers stockstats to calculate the indicator
    
    # Create a dictionary mapping date strings to indicator values
    # 【教学】将 DataFrame 转换为字典
    # 格式：{日期字符串: 指标值字符串}
    # 为什么要转字典？因为字典查表 O(1)，比 DataFrame 快
    result_dict = {}
    for _, row in df.iterrows():
        date_str = row["Date"]
        indicator_value = row[indicator]
        
        # Handle NaN/None values
        # 【教学】处理空值
        # stockstats 计算时，非交易日会是 NaN
        # 转为 "N/A" 字符串，便于 LLM 理解
        if pd.isna(indicator_value):
            result_dict[date_str] = "N/A"
        else:
            result_dict[date_str] = str(indicator_value)
    
    return result_dict


# ==============================================================================
# 函数 4: get_stockstats_indicator() — 单日技术指标计算（回退方案）
# ==============================================================================

def get_stockstats_indicator(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[
        str, "The current trading date you are trading on, YYYY-mm-dd"
    ],
) -> str:
    """
    【函数功能】
        获取单个日期的技术指标值。

    【使用场景】
        这是"回退方案"，当 _get_stock_stats_bulk() 失败时使用。
        每次调用只查一天的数据，精度高但速度慢。

    【与 _get_stock_stats_bulk() 的关系】
        _get_stock_stats_bulk()  → 批量计算（优化路径）
        get_stockstats_indicator() → 单日计算（回退路径）

    【返回值】
        指标值的字符串形式，如 "65.23" 或 ""（出错时）
    """

    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    curr_date = curr_date_dt.strftime("%Y-%m-%d")

    try:
        # 【教学】调用 StockstatsUtils.get_stock_stats() 计算指标
        # StockstatsUtils 是 stockstats_utils.py 中定义的工具类
        # 它封装了 stockstats 库的使用细节
        indicator_value = StockstatsUtils.get_stock_stats(
            symbol,
            indicator,
            curr_date,
        )
    except Exception as e:
        # 【教学】异常处理：打印错误信息，返回空字符串
        # 为什么返回空字符串而不是抛异常？
        # 因为这个函数在循环中被调用，如果抛异常会中断整个流程
        # 返回空字符串让调用者决定如何处理
        print(
            f"Error getting stockstats indicator data for indicator {indicator} on {curr_date}: {e}"
        )
        return ""

    return str(indicator_value)


# ==============================================================================
# 函数 5: get_fundamentals() — 获取公司基本面概览
# ==============================================================================

def get_fundamentals(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
):
    """
    【函数功能】
        获取公司的基本面概览数据。

    【数据来源】
        yfinance.Ticker.info — 这是一个"信息字典"
        包含 Yahoo Finance 收集的所有公开信息

    【包含的字段】
        ┌─────────────────────┬───────────────────────────────────────────────┐
        │        类别         │                     字段                      │
        ├─────────────────────┼───────────────────────────────────────────────┤
        │   基本信息          │  Name, Sector, Industry, Market Cap            │
        │   估值指标          │  PE Ratio, Forward PE, PEG Ratio, Price/Book  │
        │   盈利指标          │  EPS, Revenue, EBITDA, Net Income, Margins    │
        │   财务健康          │  Debt/Equity, Current Ratio, ROE, ROA         │
        │   股东回报          │  Dividend Yield                                │
        │   动量数据          │  Beta, 52W High/Low, 50D/200D Avg             │
        └─────────────────────┴───────────────────────────────────────────────┘

    【返回格式示例】
        # Company Fundamentals for NVDA
        # Data retrieved on: 2024-12-31 15:30:00

        Name: NVIDIA Corporation
        Sector: Technology
        Industry: Semiconductors
        Market Cap: 1500000000000
        PE Ratio (TTM): 65.5
        ...
    """
    """Get company fundamentals overview from yfinance."""
    try:
        # 【教学】创建 Ticker 对象
        ticker_obj = yf.Ticker(ticker.upper())

        # 【教学】ticker.info 是一个"懒加载字典"
        # 第一次访问时会发起网络请求
        # 后续访问直接返回缓存
        # yf_retry() 包装器增加重试机制
        info = yf_retry(lambda: ticker_obj.info)

        if not info:
            return f"No fundamentals data found for symbol '{ticker}'"

        # 【教学】fields 列表定义了"需要提取的字段"
        # 格式：(显示名称, info字典中的键)
        # 只有当值不为 None 时才加入输出
        fields = [
            ("Name", info.get("longName")),
            ("Sector", info.get("sector")),
            ("Industry", info.get("industry")),
            ("Market Cap", info.get("marketCap")),
            ("PE Ratio (TTM)", info.get("trailingPE")),
            ("Forward PE", info.get("forwardPE")),
            ("PEG Ratio", info.get("pegRatio")),
            ("Price to Book", info.get("priceToBook")),
            ("EPS (TTM)", info.get("trailingEps")),
            ("Forward EPS", info.get("forwardEps")),
            ("Dividend Yield", info.get("dividendYield")),
            ("Beta", info.get("beta")),
            ("52 Week High", info.get("fiftyTwoWeekHigh")),
            ("52 Week Low", info.get("fiftyTwoWeekLow")),
            ("50 Day Average", info.get("fiftyDayAverage")),
            ("200 Day Average", info.get("twoHundredDayAverage")),
            ("Revenue (TTM)", info.get("totalRevenue")),
            ("Gross Profit", info.get("grossProfits")),
            ("EBITDA", info.get("ebitda")),
            ("Net Income", info.get("netIncomeToCommon")),
            ("Profit Margin", info.get("profitMargins")),
            ("Operating Margin", info.get("operatingMargins")),
            ("Return on Equity", info.get("returnOnEquity")),
            ("Return on Assets", info.get("returnOnAssets")),
            ("Debt to Equity", info.get("debtToEquity")),
            ("Current Ratio", info.get("currentRatio")),
            ("Book Value", info.get("bookValue")),
            ("Free Cash Flow", info.get("freeCashflow")),
        ]

        # 【教学】构建输出字符串
        # 只包含非空字段，避免 LLM 看到大量 "None"
        lines = []
        for label, value in fields:
            if value is not None:
                lines.append(f"{label}: {value}")

        # 添加头部信息
        header = f"# Company Fundamentals for {ticker.upper()}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + "\n".join(lines)

    except Exception as e:
        return f"Error retrieving fundamentals for {ticker}: {str(e)}"


# ==============================================================================
# 函数 6: get_balance_sheet() — 获取资产负债表
# ==============================================================================

def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None
):
    """
    【函数功能】
        获取公司的资产负债表。

    【数据来源】
        • 季度数据：ticker_obj.quarterly_balance_sheet
        • 年度数据：ticker_obj.balance_sheet

    【资产负债表的组成】
        ┌─────────────────────────────────────────────────────────────┐
        │  资产 (Assets)                                             │
        │    ├── 流动资产 (Current Assets)                           │
        │    │    ├── 现金及等价物                                    │
        │    │    ├── 应收账款                                       │
        │    │    └── 存货                                          │
        │    └── 非流动资产 (Non-current Assets)                     │
        │         ├── 固定资产                                       │
        │         └── 无形资产                                       │
        ├─────────────────────────────────────────────────────────────┤
        │  负债 (Liabilities)                                       │
        │    ├── 流动负债 (Current Liabilities)                      │
        │    │    ├── 应付账款                                       │
        │    │    └── 短期借款                                      │
        │    └── 长期负债 (Long-term Liabilities)                   │
        ├─────────────────────────────────────────────────────────────┤
        │  股东权益 (Shareholders' Equity)                           │
        └─────────────────────────────────────────────────────────────┘

    【curr_date 参数的作用】
        用于 filter_financials_by_date() 过滤
        只返回 curr_date 之前的财务报表（避免"未来信息泄漏"）
    """
    """Get balance sheet data from yfinance."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())

        # 【教学】根据 freq 参数选择数据类型
        # 季度数据：quarterly_balance_sheet（默认，更及时）
        # 年度数据：balance_sheet（更稳定，但滞后）
        if freq.lower() == "quarterly":
            data = yf_retry(lambda: ticker_obj.quarterly_balance_sheet)
        else:
            data = yf_retry(lambda: ticker_obj.balance_sheet)

        # 【教学】filter_financials_by_date() 过滤日期
        # 原因：财务报表有滞后性（如 Q3 财报可能在 Q4 才发布）
        # 过滤后确保不泄露"未来信息"
        data = filter_financials_by_date(data, curr_date)

        if data.empty:
            return f"No balance sheet data found for symbol '{ticker}'"
            
        # Convert to CSV string for consistency with other functions
        # 【教学】统一转换为 CSV 格式
        # 这是为了与 Alpha Vantage 版本保持一致
        csv_string = data.to_csv()
        
        # Add header information
        header = f"# Balance Sheet data for {ticker.upper()} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving balance sheet for {ticker}: {str(e)}"


# ==============================================================================
# 函数 7: get_cashflow() — 获取现金流量表
# ==============================================================================

def get_cashflow(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None
):
    """
    【函数功能】
        获取公司的现金流量表。

    【现金流量表的组成】
        ┌─────────────────────────────────────────────────────────────┐
        │  经营活动现金流 (Operating Cash Flow)                       │
        │    公司主营业务产生的现金流入/流出                           │
        ├─────────────────────────────────────────────────────────────┤
        │  投资活动现金流 (Investing Cash Flow)                       │
        │    购买资产、投资子公司等                                    │
        ├─────────────────────────────────────────────────────────────┤
        │  融资活动现金流 (Financing Cash Flow)                       │
        │    发行股票、债券、支付股息等                                │
        ├─────────────────────────────────────────────────────────────┤
        │  净现金流 (Net Cash Flow)                                   │
        │    三者之和，反映资金变化                                    │
        └─────────────────────────────────────────────────────────────┘

    【与利润表的区别】
        • 利润表：权责发生制（应收未收也算收入）
        • 现金流量表：收付实现制（实际收到/支出才算）
        • 案例：公司卖了 100 万商品，但客户还没付款
            → 利润表：+100 万收入
            → 现金流量表：0（还没收到钱）
    """
    """Get cash flow data from yfinance."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())

        if freq.lower() == "quarterly":
            data = yf_retry(lambda: ticker_obj.quarterly_cashflow)
        else:
            data = yf_retry(lambda: ticker_obj.cashflow)

        data = filter_financials_by_date(data, curr_date)

        if data.empty:
            return f"No cash flow data found for symbol '{ticker}'"
            
        csv_string = data.to_csv()
        
        header = f"# Cash Flow data for {ticker.upper()} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving cash flow for {ticker}: {str(e)}"


# ==============================================================================
# 函数 8: get_income_statement() — 获取利润表
# ==============================================================================

def get_income_statement(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None
):
    """
    【函数功能】
        获取公司的利润表（损益表）。

    【利润表的组成】
        ┌─────────────────────────────────────────────────────────────┐
        │  营业收入 (Revenue)                                         │
        ├─────────────────────────────────────────────────────────────┤
        │  营业成本 (Cost of Revenue)                                │
        ├─────────────────────────────────────────────────────────────┤
        │  毛利润 (Gross Profit) = 收入 - 成本                        │
        ├─────────────────────────────────────────────────────────────┤
        │  营业费用 (Operating Expenses)                             │
        │    ├── 销售费用                                           │
        │    ├── 管理费用                                           │
        │    └── 研发费用                                           │
        ├─────────────────────────────────────────────────────────────┤
        │  营业利润 (Operating Income)                               │
        ├─────────────────────────────────────────────────────────────┤
        │  净利润 (Net Income) = 最终利润                             │
        └─────────────────────────────────────────────────────────────┘

    【分析要点】
        • 毛利率 = 毛利润 / 收入 → 越高越好（护城河）
        • 净利率 = 净利润 / 收入 → 反映整体盈利能力
        • 营收增长率 → 公司成长性
    """
    """Get income statement data from yfinance."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())

        if freq.lower() == "quarterly":
            data = yf_retry(lambda: ticker_obj.quarterly_income_stmt)
        else:
            data = yf_retry(lambda: ticker_obj.income_stmt)

        data = filter_financials_by_date(data, curr_date)

        if data.empty:
            return f"No income statement data found for symbol '{ticker}'"
            
        csv_string = data.to_csv()
        
        header = f"# Income Statement data for {ticker.upper()} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving income statement for {ticker}: {str(e)}"


# ==============================================================================
# 函数 9: get_insider_transactions() — 获取内幕交易数据
# ==============================================================================

def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol of the company"]
):
    """
    【函数功能】
        获取公司内部人员的股票交易记录。

    【什么是"内部人员"？】
        • 高管（CEO, CFO, CTO 等）
        • 董事
        • 大股东（持股 > 10%）
        • 上述人员的直系亲属

    【交易类型】
        • 购买 (Purchase) → 内部人看好公司
        • 出售 (Sale) → 可能需要现金，或不看好
        • 期权行权 (Option Exercise) → 高管薪酬的一部分

    【投资参考价值】
        ┌─────────────────────────────────────────────────────────────┐
        │  信号类型              │  解读                              │
        ├─────────────────────────────────────────────────────────────┤
        │  大额购买             │  强烈看多信号                      │
        │  大额出售             │  谨慎（但可能是正常薪酬需求）        │
        │  大额期权行权         │  中性（与薪酬结构相关）             │
        │  频繁小额交易         │  可能无意义                        │
        └─────────────────────────────────────────────────────────────┘

    【SEC 规定】
        美国上市公司内部人员须在交易后 2 个工作日内向 SEC 报告
        这些信息是公开的，yfinance 整合了这些数据
    """
    """Get insider transactions data from yfinance."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())

        # 【教学】insider_transactions 包含内部人员的交易记录
        data = yf_retry(lambda: ticker_obj.insider_transactions)
        
        if data is None or data.empty:
            return f"No insider transactions data found for symbol '{ticker}'"
            
        csv_string = data.to_csv()
        
        header = f"# Insider Transactions data for {ticker.upper()}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving insider transactions for {ticker}: {str(e)}"
