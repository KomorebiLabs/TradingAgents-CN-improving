"""
================================================================================
                      ALPHA_VANTAGE_INDICATOR.PY 详解
                            技术指标获取
================================================================================

┌──────────────────────────────────────────────────────────────────────────
│                           模块位置图                                     
│                                                                          
│  ┌─────────────────────────────────────────────────────────────────────┐
│  │                          interface.py                                 
│  │                      (路由层 - route_to_vendor)                       
│  └─────────────────────────────────────────────────────────────────────┘
│                                    │                                    
│                                    ▼                                    
│  ┌─────────────────────────────────────────────────────────────────────┐
│  │                     alpha_vantage_indicator.py                        
│  │                     (功能模块 - 技术指标)                             
│  │                                                                       
│  │    get_indicator(symbol, indicator, curr_date, look_back_days)        
│  │              │                                                        
│  │              ├──► 验证指标是否支持                                    
│  │              │                                                        
│  │              ├──► 调用对应的 Alpha Vantage API                        
│  │              │    ┌─────────────────────────────────────────┐         
│  │              │    │  supported_indicators 映射表：           │        
│  │              │    │  "rsi"     → "RSI" API                  │         │
│  │              │    │  "macd"    → "MACD" API                 │         │
│  │              │    │  "close_50_sma" → "SMA" API             │         │
│  │              │    └─────────────────────────────────────────┘         
│  │              │                                                        
│  │              ├──► 解析 CSV 数据                                       
│  │              │                                                        
│  │              └──► 按日期范围过滤                                      
│  │                   (从 curr_date 向前 look_back_days 天)              │
│  │                                                                       
│  └─────────────────────────────────────────────────────────────────────┘
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  alpha_vantage_common.py                                │   │
│  │                    (底层 HTTP 工具)                                    
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
一、模块职责
================================================================================

这个模块负责从 Alpha Vantage 获取各种技术分析指标。

技术指标是：
  - 基于历史价格/成交量计算的交易信号
  - 帮助交易员判断趋势、超买超卖、波动性等
  - 是量化交易和算法交易的核心工具

支持的技术指标（共 12 种）：

┌─────────────────────────────────────────────────────────────────────────────┐
│                          支持的技术指标列表                                    │
├────────────────────┬────────────────────────────────────────────────────────┤
│                    │                                                        │
│  【趋势指标】       │                                                        │
│  ├─ close_50_sma  │  50 日简单移动平均线                                    │
│  ├─ close_200_sma │  200 日简单移动平均线                                   │
│  └─ close_10_ema  │  10 日指数移动平均线                                    │
│                    │                                                        │
│  【动量指标】       │                                                        │
│  ├─ macd          │  MACD 线（12/26 日 EMA 差值）                         │
│  ├─ macds         │  MACD 信号线（9 日 EMA）                               │
│  ├─ macdh         │  MACD 柱状图                                           │
│  └─ rsi           │  相对强弱指数 (14 日)                                   │
│                    │                                                        │
│  【波动性指标】     │                                                        │
│  ├─ boll          │  布林带中轨（20 日 SMA）                               │
│  ├─ boll_ub       │  布林带上轨（中轨 + 2 倍标准差）                       │
│  ├─ boll_lb       │  布林带下轨（中轨 - 2 倍标准差）                       │
│  └─ atr           │  平均真实波幅                                          │
│                    │                                                        │
│  【成交量指标】     │                                                        │
│  └─ vwma          │  成交量加权移动平均（Alpha Vantage 不支持）            │
│                    │                                                        │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
二、技术指标详解
================================================================================

【趋势指标】

1. SMA (Simple Moving Average) - 简单移动平均
   公式：SMA = (P1 + P2 + ... + Pn) / n
   用途：
     - 50 SMA：识别中期趋势
     - 200 SMA：识别长期趋势，"金叉/死叉"信号

2. EMA (Exponential Moving Average) - 指数移动平均
   公式：EMA = (Close - Previous EMA) * k + Previous EMA
         其中 k = 2 / (n + 1)
   特点：
     - 比 SMA 更敏感，近期价格权重更大
     - 10 EMA：捕捉短期动量变化

【动量指标】

3. MACD (Moving Average Convergence Divergence)
   组成：
     - MACD 线 = 12 日 EMA - 26 日 EMA
     - Signal 线 = MACD 的 9 日 EMA
     - Histogram = MACD 线 - Signal 线
   信号：
     - MACD 上穿 Signal → 买入信号
     - MACD 下穿 Signal → 卖出信号
     - 与价格背离 → 潜在反转信号

4. RSI (Relative Strength Index) - 相对强弱指数
   公式：RSI = 100 - (100 / (1 + RS))
         其中 RS = 平均涨幅 / 平均跌幅
   范围：0-100
     - RSI > 70 → 超买
     - RSI < 30 → 超卖

【波动性指标】

5. Bollinger Bands - 布林带
   组成：
     - 中轨 = 20 日 SMA
     - 上轨 = 中轨 + 2 * 标准差
     - 下轨 = 中轨 - 2 * 标准差
   用途：
     - 价格触及上轨 → 可能超买
     - 价格触及下轨 → 可能超卖
     - 带宽收缩 → 突破在即

6. ATR (Average True Range) - 平均真实波幅
   用途：
     - 设置止损：止损 = 入场价 - 2 * ATR
     - 仓位管理：大 ATR → 小仓位

================================================================================
三、Alpha Vantage API 对应
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│                       API 与指标的映射关系                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Alpha Vantage API      │  本模块映射       │  返回数据                      │
│  ──────────────────────┼──────────────────┼───────────────────────────    │
│  SMA                   │  close_50_sma     │  SMA 值                       │
│                        │  close_200_sma    │  SMA 值                       │
│  EMA                   │  close_10_ema     │  EMA 值                       │
│  MACD                  │  macd             │  MACD, Signal, Histogram       │
│                        │  macds            │  Signal                       │
│                        │  macdh            │  Histogram                    │
│  RSI                   │  rsi              │  RSI 值                       │
│  BBANDS                │  boll             │  Middle, Upper, Lower          │
│                        │  boll_ub          │  Upper                       │
│                        │  boll_lb          │  Lower                       │
│  ATR                   │  atr              │  ATR 值                       │
│                        │  vwma             │  ⚠ 不支持（需本地计算）        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
四、代码逐段解析
================================================================================
"""

from .alpha_vantage_common import _make_api_request


# ==============================================================================
# 第一部分：指标定义
# ==============================================================================

def get_indicator(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
    interval: str = "daily",
    time_period: int = 14,
    series_type: str = "close"
) -> str:
    """
    获取指定股票的技术指标数据。

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                           函数流程图                                      │
    │                                                                          │
    │    输入：                                                                │
    │      symbol="NVDA"                                                     │
    │      indicator="rsi"                                                   │
    │      curr_date="2024-06-15"                                            │
    │      look_back_days=30                                                  │
    │                                                                          │
    │              │                                                         │
    │              ▼                                                         │
    │    ┌─────────────────────────────┐                                     │
    │    │ 1. 验证指标                 │                                     │
    │    │ supported_indicators 中？  │                                     │
    │    └─────────────────────────────┘                                     │
    │              │                                                         │
    │              ▼                                                         │
    │    ┌─────────────────────────────┐                                     │
    │    │ 2. 计算日期范围              │                                     │
    │    │ before = curr_date - 30天    │                                     │
    │    │ curr_date = 2024-06-15      │                                     │
    │    └─────────────────────────────┘                                     │
    │              │                                                         │
    │              ▼                                                         │
    │    ┌─────────────────────────────┐                                     │
    │    │ 3. 调用对应 API              │                                     │
    │    │ RSI(symbol, interval=daily, │                                     │
    │    │   time_period=14, ...)      │                                     │
    │    └─────────────────────────────┘                                     │
    │              │                                                         │
    │              ▼                                                         │
    │    ┌─────────────────────────────┐                                     │
    │    │ 4. 解析 CSV                  │                                     │
    │    │ time,RSI                    │                                     │
    │    │ 2024-05-17,45.23           │                                     │
    │    │ 2024-05-18,48.56           │                                     │
    │    └─────────────────────────────┘                                     │
    │              │                                                         │
    │              ▼                                                         │
    │    ┌─────────────────────────────┐                                     │
    │    │ 5. 按日期过滤                │                                     │
    │    │ 只保留 2024-05-17 到        │                                     │
    │    │ 2024-06-15 的数据           │                                     │
    │    └─────────────────────────────┘                                     │
    │              │                                                         │
    │              ▼                                                         │
    │    ┌─────────────────────────────┐                                     │
    │    │ 6. 格式化输出                │                                     │
    │    │ ## RSI values from ...     │                                     │
    │    │ 2024-05-17: 45.23          │                                     │
    │    │ ...                        │                                     │
    │    │ [指标描述]                  │                                     │
    │    └─────────────────────────────┘                                     │
    │              │                                                         │
    │              ▼                                                         │
    │    输出：格式化字符串                                                   │
    │                                                                          │
    └─────────────────────────────────────────────────────────────────────────┘

    Args:
        symbol: 股票代码
                例如：IBM, AAPL, NVDA

        indicator: 技术指标名称
                   可选值：
                     - "close_50_sma": 50 日简单移动平均
                     - "close_200_sma": 200 日简单移动平均
                     - "close_10_ema": 10 日指数移动平均
                     - "macd": MACD
                     - "macds": MACD 信号线
                     - "macdh": MACD 柱状图
                     - "rsi": 相对强弱指数
                     - "boll": 布林带中轨
                     - "boll_ub": 布林带上轨
                     - "boll_lb": 布林带下轨
                     - "atr": 平均真实波幅
                     - "vwma": 成交量加权移动平均（不支持）

        curr_date: 当前交易日
                   格式：YYYY-MM-DD
                   用于计算 look_back_days 之前的日期

        look_back_days: 回溯天数
                        例如：30 表示获取从 curr_date-30天 到 curr_date 的数据

        interval: 时间间隔
                  默认："daily"
                  可选："1min", "5min", "15min", "30min", "60min", "weekly", "monthly"

        time_period: 计算周期
                     大多数指标默认为 14
                     RSI: 通常 14
                     ATR: 通常 14

        series_type: 价格类型
                     默认："close"
                     可选："open", "high", "low", "close"

    Returns:
        格式化字符串，包含：
          - 标题（指标名称和日期范围）
          - 日期-值对列表
          - 指标解释和交易建议

    示例：
        >>> result = get_indicator("IBM", "rsi", "2024-06-15", 30)
        >>> print(result)
        ## RSI values from 2024-05-17 to 2024-06-15:

        2024-05-17: 45.23
        2024-05-18: 48.56
        ...

        RSI: Measures momentum to flag overbought/oversold conditions...
    """
    from datetime import datetime
    from dateutil.relativedelta import relativedelta

    # -------------------------------------------------------------------------
    # Step 1: 定义支持的指标和它们的 API 配置
    # -------------------------------------------------------------------------
    #
    # supported_indicators 字典：
    #   key = 本模块使用的指标名
    #   value = tuple(Alpha Vantage API 参数)
    #
    # 格式：(API 参数名, series_type)
    #   - API 参数名：Alpha Vantage API 的 function 参数
    #   - series_type：计算指标使用的价格类型（None 表示不适用）
    #
    supported_indicators = {
        # 趋势指标 - SMA API
        "close_50_sma": ("50 SMA", "close"),    # 50 日 SMA，基于收盘价
        "close_200_sma": ("200 SMA", "close"),   # 200 日 SMA，基于收盘价
        "close_10_ema": ("10 EMA", "close"),     # 10 日 EMA，基于收盘价

        # 动量指标 - MACD API
        "macd": ("MACD", "close"),              # MACD 主线
        "macds": ("MACD Signal", "close"),       # MACD 信号线
        "macdh": ("MACD Histogram", "close"),    # MACD 柱状图

        # 动量指标 - RSI API
        "rsi": ("RSI", "close"),                # RSI

        # 波动性指标 - BBANDS API
        "boll": ("Bollinger Middle", "close"),   # 布林带中轨
        "boll_ub": ("Bollinger Upper Band", "close"),  # 布林带上轨
        "boll_lb": ("Bollinger Lower Band", "close"),  # 布林带下轨

        # 波动性指标 - ATR API
        "atr": ("ATR", None),                   # ATR（不需要 series_type）

        # 成交量指标 - 不支持
        "vwma": ("VWMA", "close")              # VWMA（Alpha Vantage 不直接支持）
    }

    # -------------------------------------------------------------------------
    # Step 2: 定义指标描述（用于 LLM 理解指标含义）
    # -------------------------------------------------------------------------
    #
    # indicator_descriptions 字典包含：
    #   - 指标名称和简要说明
    #   - 使用建议
    #   - 注意事项
    #
    # 这些描述会被添加到返回结果中，帮助 LLM Agent 理解指标含义
    #
    indicator_descriptions = {
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
        "rsi": (
            "RSI: Measures momentum to flag overbought/oversold conditions. "
            "Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. "
            "Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis."
        ),
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
        "vwma": (
            "VWMA: A moving average weighted by volume. "
            "Usage: Confirm trends by integrating price action with volume data. "
            "Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses."
        )
    }

    # -------------------------------------------------------------------------
    # Step 3: 验证指标
    # -------------------------------------------------------------------------
    if indicator not in supported_indicators:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(supported_indicators.keys())}"
        )

    # -------------------------------------------------------------------------
    # Step 4: 计算日期范围
    # -------------------------------------------------------------------------
    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    # 计算回溯日期
    before = curr_date_dt - relativedelta(days=look_back_days)

    # -------------------------------------------------------------------------
    # Step 5: 确定 API 调用参数
    # -------------------------------------------------------------------------
    # 从 supported_indicators 获取 API 参数名和 series_type
    api_indicator_name, required_series_type = supported_indicators[indicator]

    # 如果指标有特定的 series_type 要求，使用它覆盖用户输入
    # 这样可以确保使用正确的价格类型计算指标
    if required_series_type:
        series_type = required_series_type

    # -------------------------------------------------------------------------
    # Step 6: 调用对应的 API
    # -------------------------------------------------------------------------
    try:
        # 根据指标类型调用不同的 Alpha Vantage API
        # 每个指标都需要不同的参数

        if indicator == "close_50_sma":
            # SMA API，周期 50
            data = _make_api_request("SMA", {
                "symbol": symbol,
                "interval": interval,
                "time_period": "50",
                "series_type": series_type,
                "datatype": "csv"
            })

        elif indicator == "close_200_sma":
            # SMA API，周期 200
            data = _make_api_request("SMA", {
                "symbol": symbol,
                "interval": interval,
                "time_period": "200",
                "series_type": series_type,
                "datatype": "csv"
            })

        elif indicator == "close_10_ema":
            # EMA API，周期 10
            data = _make_api_request("EMA", {
                "symbol": symbol,
                "interval": interval,
                "time_period": "10",
                "series_type": series_type,
                "datatype": "csv"
            })

        elif indicator in ["macd", "macds", "macdh"]:
            # MACD API
            # 注意：MACD API 返回三个值：MACD, Signal, Histogram
            # 我们在后面根据 indicator 选择需要的列
            data = _make_api_request("MACD", {
                "symbol": symbol,
                "interval": interval,
                "series_type": series_type,
                "datatype": "csv"
            })

        elif indicator == "rsi":
            # RSI API
            data = _make_api_request("RSI", {
                "symbol": symbol,
                "interval": interval,
                "time_period": str(time_period),  # 默认 14
                "series_type": series_type,
                "datatype": "csv"
            })

        elif indicator in ["boll", "boll_ub", "boll_lb"]:
            # BBANDS API（布林带）
            # 返回三个列：Middle Band, Upper Band, Lower Band
            data = _make_api_request("BBANDS", {
                "symbol": symbol,
                "interval": interval,
                "time_period": "20",  # 标准布林带周期
                "series_type": series_type,
                "datatype": "csv"
            })

        elif indicator == "atr":
            # ATR API
            data = _make_api_request("ATR", {
                "symbol": symbol,
                "interval": interval,
                "time_period": str(time_period),  # 默认 14
                "datatype": "csv"
            })

        elif indicator == "vwma":
            # Alpha Vantage 不直接支持 VWMA
            # 返回一条友好的消息
            return (
                f"## VWMA (Volume Weighted Moving Average) for {symbol}:\n\n"
                f"VWMA calculation requires OHLCV data and is not directly available from Alpha Vantage API.\n"
                f"This indicator would need to be calculated from the raw stock data using volume-weighted price averaging.\n\n"
                f"{indicator_descriptions.get('vwma', 'No description available.')}"
            )

        else:
            return f"Error: Indicator {indicator} not implemented yet."

        # -------------------------------------------------------------------------
        # Step 7: 解析 CSV 数据
        # -------------------------------------------------------------------------
        # Alpha Vantage 返回的 CSV 格式：
        # time,MACD,MACD_Signal,MACD_Hist
        # 2024-05-17,0.52,0.48,0.04

        lines = data.strip().split('\n')
        if len(lines) < 2:
            return f"Error: No data returned for {indicator}"

        # 解析表头
        header = [col.strip() for col in lines[0].split(',')]

        # 找到时间列
        try:
            date_col_idx = header.index('time')
        except ValueError:
            return f"Error: 'time' column not found in data for {indicator}. Available columns: {header}"

        # -------------------------------------------------------------------------
        # Step 8: 确定要提取的列
        # -------------------------------------------------------------------------
        # col_name_map：将本模块的指标名映射到 CSV 列名
        # 这是必需的，因为 Alpha Vantage 对不同指标使用不同的列名
        col_name_map = {
            # MACD 相关
            "macd": "MACD",
            "macds": "MACD_Signal",
            "macdh": "MACD_Hist",

            # 布林带
            "boll": "Real Middle Band",
            "boll_ub": "Real Upper Band",
            "boll_lb": "Real Lower Band",

            # 其他指标（列名与指标名相同或直接是值）
            "rsi": "RSI",
            "atr": "ATR",
            "close_10_ema": "EMA",        # EMA API 返回的列名是 EMA
            "close_50_sma": "SMA",        # SMA API 返回的列名是 SMA
            "close_200_sma": "SMA",       # 同上
        }

        target_col_name = col_name_map.get(indicator)

        if not target_col_name:
            # 默认使用第二列（某些指标如 SMA 只有一个值列）
            value_col_idx = 1
        else:
            try:
                value_col_idx = header.index(target_col_name)
            except ValueError:
                return (
                    f"Error: Column '{target_col_name}' not found for indicator '{indicator}'. "
                    f"Available columns: {header}"
                )

        # -------------------------------------------------------------------------
        # Step 9: 提取指定日期范围内的数据
        # -------------------------------------------------------------------------
        result_data = []
        for line in lines[1:]:
            if not line.strip():
                continue

            values = line.split(',')
            if len(values) > value_col_idx:
                try:
                    date_str = values[date_col_idx].strip()
                    date_dt = datetime.strptime(date_str, "%Y-%m-%d")

                    # 只保留指定范围内的数据
                    if before <= date_dt <= curr_date_dt:
                        value = values[value_col_idx].strip()
                        result_data.append((date_dt, value))

                except (ValueError, IndexError):
                    continue

        # -------------------------------------------------------------------------
        # Step 10: 格式化输出
        # -------------------------------------------------------------------------
        # 按日期排序（升序）
        result_data.sort(key=lambda x: x[0])

        # 构建结果字符串
        ind_string = ""
        for date_dt, value in result_data:
            ind_string += f"{date_dt.strftime('%Y-%m-%d')}: {value}\n"

        if not ind_string:
            ind_string = "No data available for the specified date range.\n"

        # 最终格式化输出
        result_str = (
            f"## {indicator.upper()} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
            + ind_string
            + "\n\n"
            + indicator_descriptions.get(indicator, "No description available.")
        )

        return result_str

    except Exception as e:
        print(f"Error getting Alpha Vantage indicator data for {indicator}: {e}")
        return f"Error retrieving {indicator} data: {str(e)}"


# ==============================================================================
# 补充说明
# ==============================================================================

"""
================================================================================
【MACD 指标的特别说明】

MACD (Moving Average Convergence Divergence) 是一种趋势动量指标：

计算公式：
  1. 快速 EMA（通常 12 日）- 慢速 EMA（通常 26 日）= MACD 线
  2. MACD 线的 9 日 EMA = Signal 线
  3. MACD 线 - Signal 线 = Histogram（柱状图）

Alpha Vantage 的 MACD API 返回：
  time,MACD,MACD_Signal,MACD_Hist
  2024-01-02,0.52,0.48,0.04

我们在代码中：
  - indicator="macd" → 提取 MACD 列
  - indicator="macds" → 提取 MACD_Signal 列
  - indicator="macdh" → 提取 MACD_Hist 列

================================================================================
【布林带指标的特别说明】

布林带（Bollinger Bands）由三条线组成：
  1. 中轨 = n 日简单移动平均（SMA）
  2. 上轨 = 中轨 + k × 标准差（k 通常为 2）
  3. 下轨 = 中轨 - k × 标准差

Alpha Vantage 的 BBANDS API 返回：
  time,Real Middle Band,Real Upper Band,Real Lower Band
  2024-01-02,185.50,195.30,175.70

我们在代码中：
  - indicator="boll" → 提取 Real Middle Band
  - indicator="boll_ub" → 提取 Real Upper Band
  - indicator="boll_lb" → 提取 Real Lower Band

================================================================================
【Look-Ahead Bias 防护】

重要：本函数通过日期过滤来防止「未来数据泄露」

问题：
  - 如果我们在 2024-01-01 分析股票
  - 不应该看到 2024-01-02 之后的数据
  - 否则就是「偷看未来」

解决方案：
  - 输入 curr_date 表示「当前日期」
  - look_back_days 表示回溯天数
  - 只返回 [curr_date - look_back_days, curr_date] 范围内的数据
  - 这确保了回测时不会「偷看未来」

================================================================================
【与 Yahoo Finance 的对比】

Yahoo Finance 使用 stockstats 库在本地计算技术指标。
Alpha Vantage 直接从 API 返回计算好的指标值。

两者对比：
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                          Alpha Vantage                                      │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │  优点：                                                                    │
  │    ✓ API 返回即用型数据                                                    │
  │    ✓ 无需本地计算                                                          │
  │    ✓ 数据一致性好（服务器端计算）                                          │
  │                                                                            │
  │  缺点：                                                                    │
  │    ✗ API 调用频率限制                                                      │
  │    ✗ 部分指标不支持（如 VWMA）                                            │
  └─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                          Yahoo Finance                                      │
  ├─────────────────────────────────────────────────────────────────────────────┤
  │  优点：                                                                    │
  │    ✓ 免费，无调用限制                                                      │
  │    ✓ 支持更多指标                                                          │
  │    ✓ VWMA 等指标可计算                                                    │
  │                                                                            │
  │  缺点：                                                                    │
  │    ✗ 需要下载原始 OHLCV 数据后本地计算                                     │
  │    ✗ 计算可能有差异                                                        │
  └─────────────────────────────────────────────────────────────────────────────┘

TradingAgents 的策略：
  - 优先使用 Alpha Vantage
  - 如果频率限制，自动切换到 Yahoo Finance
"""
