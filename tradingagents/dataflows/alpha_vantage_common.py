"""
================================================================================
                        ALPHA_VANTAGE_COMMON.PY 详解
                          Alpha Vantage API 底层工具
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│                           模块定位图                                         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        agents/utils/*.py                             │   │
│  │         (封装层 - @tool 装饰器，将函数暴露给 LLM)                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       interface.py                                   │   │
│  │              (路由层 - route_to_vendor)                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              alpha_vantage_*.py (各功能模块)                          │   │
│  │   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │   │
│  │   │ alpha_van-  │ │ alpha_van-  │ │ alpha_van-  │ │ alpha_van-  │  │   │
│  │   │ tage_stock  │ │ tage_indic- │ │ tage_funda- │ │ tage_news   │  │   │
│  │   │ .py         │ │ ator.py     │ │ mentals.py  │ │ .py         │  │   │
│  │   └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘  │   │
│  └──────────┼────────────────┼────────────────┼────────────────┼───────┘   │
│             │                │                │                │           │
│             └────────────────┼────────────────┼────────────────┘           │
│                              │                │                             │
│                              ▼                ▼                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    alpha_vantage_common.py                              │ │
│  │                                                                       │ │
│  │   ┌────────────────────────────────────────────────────────────────┐  │ │
│  │   │  共享工具函数：                                                  │  │ │
│  │   │  - get_api_key(): 从环境变量获取 API Key                        │  │ │
│  │   │  - format_datetime_for_api(): 日期格式转换                       │  │ │
│  │   │  - _make_api_request(): 统一的 HTTP 请求处理                    │  │ │
│  │   │  - _filter_csv_by_date_range(): CSV 数据日期过滤                │  │ │
│  │   └────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                       │ │
│  │   ┌────────────────────────────────────────────────────────────────┐  │ │
│  │   │  异常类：                                                       │  │ │
│  │   │  - AlphaVantageRateLimitError: 频率限制异常                     │  │ │
│  │   └────────────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                              │                                             │
│                              ▼                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                      Alpha Vantage API                                 │ │
│  │                  https://www.alphavantage.co/query                     │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
一、模块职责
================================================================================

这个模块是 Alpha Vantage 数据源的「底层基础设施」：

  1. API 通信：处理所有与 Alpha Vantage API 的 HTTP 通信
  2. 错误处理：检测和处理频率限制错误
  3. 数据格式化：将 API 返回的日期格式转换为标准格式
  4. 数据过滤：根据日期范围过滤 CSV 数据

为什么需要这个模块？
-------------------
  - Alpha Vantage 有多个端点（TIME_SERIES_DAILY, SMA, EMA, OVERVIEW...）
  - 每个端点都需要：
      * 相同的 API Key
      * 相同的请求方式（HTTP GET）
      * 相同的错误处理逻辑
  - 抽象出 common 模块，避免代码重复

================================================================================
二、API 基础知识
================================================================================

Alpha Vantage API 概览：

┌─────────────────────────────────────────────────────────────────────────────┐
│  API 端点示例                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  URL: https://www.alphavantage.co/query                                    │
│                                                                             │
│  参数：                                                                    │
│    function=TIME_SERIES_DAILY_ADJUSTED  # API 功能                         │
│    symbol=IBM                          # 股票代码                           │
│    apikey=YOUR_API_KEY                # API 密钥                          │
│    outputsize=compact                  # 返回数据量（compact=100条）         │
│    datatype=csv                        # 返回格式（csv 或 json）             │
│                                                                             │
│  主要功能：                                                                │
│    - TIME_SERIES_DAILY: 日线数据                                          │
│    - SMA, EMA, MACD, RSI: 技术指标                                        │
│    - OVERVIEW: 公司概览                                                    │
│    - BALANCE_SHEET: 资产负债表                                            │
│    - NEWS_SENTIMENT: 新闻情绪                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
三、代码逐段解析
================================================================================
"""

import os
import requests
import pandas as pd
import json
from datetime import datetime
from io import StringIO

# ==============================================================================
# 第一部分：常量定义
# ==============================================================================

# Alpha Vantage API 的基础 URL
# 所有 API 调用都发送到这个端点
API_BASE_URL = "https://www.alphavantage.co/query"


# ==============================================================================
# 第二部分：辅助函数
# ==============================================================================

def get_api_key() -> str:
    """
    从环境变量获取 Alpha Vantage API 密钥。

    Alpha Vantage 需要 API Key 来认证请求。
    这个函数从环境变量 ALPHA_VANTAGE_API_KEY 读取密钥。

    使用环境变量的原因：
      1. 安全性：密钥不应该硬编码在代码中
      2. 灵活性：可以在不同环境使用不同的密钥
      3. 便捷性：无需修改代码即可更换密钥

    设置方式（任选一种）：
      # Linux/Mac
      export ALPHA_VANTAGE_API_KEY=YOUR_API_KEY

      # Windows PowerShell
      $env:ALPHA_VANTAGE_API_KEY = "YOUR_API_KEY"

      # 在 .env 文件中（需要 python-dotenv）
      ALPHA_VANTAGE_API_KEY=YOUR_API_KEY

    Returns:
        API 密钥字符串

    Raises:
        ValueError: 环境变量未设置

    示例：
        >>> api_key = get_api_key()
        >>> print(api_key[:4] + "****")  # 打印部分密钥
        'YOUR****'
    """
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise ValueError("ALPHA_VANTAGE_API_KEY environment variable is not set.")
    return api_key


def format_datetime_for_api(date_input) -> str:
    """
    将各种日期格式转换为 Alpha Vantage API 要求的格式。

    Alpha Vantage API 要求日期格式：YYYYMMDDTHHMM
      - YYYY: 4 位年份
      - MM: 2 位月份
      - DD: 2 位日期
      - HH: 2 位小时（24 小时制）
      - MM: 2 位分钟

    支持的输入格式：
      - "2024-01-15" → "20240115T0000"
      - "2024-01-15 14:30" → "20240115T1430"
      - "20240115T1430" → "20240115T1430" (已是正确格式，直接返回)
      - datetime(2024, 1, 15, 14, 30) → "20240115T1430"

    这个函数主要用于新闻 API 的时间范围参数：
      time_from=20240115T0000
      time_to=20240131T2359

    Args:
        date_input: 日期输入，可以是字符串或 datetime 对象

    Returns:
        格式化后的日期字符串 YYYYMMDDTHHMM

    Raises:
        ValueError: 不支持的日期格式
    """
    if isinstance(date_input, str):
        # 情况 1: 已经是正确格式（13 个字符，包含 T）
        if len(date_input) == 13 and 'T' in date_input:
            return date_input

        # 情况 2: "2024-01-15" 格式
        try:
            dt = datetime.strptime(date_input, "%Y-%m-%d")
            return dt.strftime("%Y%m%dT0000")
        except ValueError:
            pass

        # 情况 3: "2024-01-15 14:30" 格式
        try:
            dt = datetime.strptime(date_input, "%Y-%m-%d %H:%M")
            return dt.strftime("%Y%m%dT%H%M")
        except ValueError:
            raise ValueError(f"Unsupported date format: {date_input}")

    elif isinstance(date_input, datetime):
        # 情况 4: datetime 对象
        return date_input.strftime("%Y%m%dT%H%M")

    else:
        # 不支持的类型
        raise ValueError(f"Date must be string or datetime object, got {type(date_input)}")


# ==============================================================================
# 第三部分：异常定义
# ==============================================================================

class AlphaVantageRateLimitError(Exception):
    """
    Alpha Vantage API 频率限制异常。

    Alpha Vantage 有严格的 API 调用频率限制：
      - 免费版: 5 次/分钟，25 次/天
      - Premium 版: 更高限制

    当触发频率限制时，API 会返回：
      {
        "Information": "Thank you for using Alpha Vantage! Our standard API
        call frequency is 5 requests per minute and 25 requests per day.
        Please upgrade to premium for higher frequency."
      }

    这个异常用于：
      1. 在 route_to_vendor() 中触发自动回退机制
      2. 允许系统切换到备用数据源（如 Yahoo Finance）

    使用场景：
        try:
            data = _make_api_request("TIME_SERIES_DAILY", params)
        except AlphaVantageRateLimitError:
            # 切换到备用数据源
            data = get_from_yfinance(...)
    """
    pass


# ==============================================================================
# 第四部分：核心 API 请求函数 ⭐⭐⭐
# ==============================================================================

def _make_api_request(function_name: str, params: dict) -> dict | str:
    """
    ⭐ 核心 HTTP 请求函数 ⭐

    这是所有 Alpha Vantage API 调用的底层实现。

    请求流程：

        ┌─────────────────────────────────────────────────────────────┐
        │ 1. 准备参数                                                 │
        │    params = {                                              │
        │        "symbol": "IBM",                                    │
        │        "outputsize": "compact"                             │
        │    }                                                       │
        │                                                            │
        │    api_params = {                                          │
        │        "function": "TIME_SERIES_DAILY",    ← 添加 API 功能  │
        │        "apikey": "YOUR_KEY",               ← 添加 API 密钥  │
        │        "source": "trading_agents",        ← 来源标记       │
        │        "symbol": "IBM",                                    │
        │        "outputsize": "compact"                             │
        │    }                                                       │
        └─────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────────────┐
        │ 2. 发送 HTTP GET 请求                                       │
        │    response = requests.get(API_BASE_URL, params=api_params) │
        └─────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────────────┐
        │ 3. 检查响应                                                 │
        │                                                            │
        │    如果返回 JSON（可能是错误）：                              │
        │    ┌─────────────────────────────────────────────────┐      │
        │    │  {                                               │      │
        │    │    "Information": "API 频率限制..."              │      │
        │    │  }  → 抛出 AlphaVantageRateLimitError          │      │
        │    └─────────────────────────────────────────────────┘      │
        │                                                            │
        │    如果返回 CSV（正常数据）：                                 │
        │    ┌─────────────────────────────────────────────────┐      │
        │    │  timestamp,open,high,low,close,volume          │      │
        │    │  2024-01-02,180.50,182.00,179.80,181.25,...    │      │
        │    └─────────────────────────────────────────────────┘      │
        │    → 返回原始响应文本                                       │
        │                                                            │
        └─────────────────────────────────────────────────────────────┘

    Args:
        function_name: Alpha Vantage API 功能名称
                      如 "TIME_SERIES_DAILY", "SMA", "OVERVIEW" 等
        params: API 特定参数，如 {"symbol": "IBM", "datatype": "csv"}

    Returns:
        - CSV 格式的响应文本（正常情况）
        - JSON 格式的响应文本（某些 API 如 NEWS_SENTIMENT）

    Raises:
        AlphaVantageRateLimitError: API 频率限制触发
        requests.HTTPError: HTTP 请求失败

    注意：
        - 这个函数是下划线开头，表示内部使用
        - 不应该直接调用，而是通过 alpha_vantage_*.py 中的函数调用
    """
    # Step 1: 复制参数（避免修改原始字典）
    api_params = params.copy()

    # Step 2: 添加标准参数
    api_params.update({
        "function": function_name,     # API 功能名称
        "apikey": get_api_key(),       # API 密钥
        "source": "trading_agents",    # 来源标记（用于统计）
    })

    # Step 3: 处理 entitlement 参数（高级功能，可能需要）
    # entitlement 是 Alpha Vantage 的一些高级数据功能所需的特殊权限
    current_entitlement = globals().get('_current_entitlement')
    entitlement = api_params.get("entitlement") or current_entitlement

    if entitlement:
        api_params["entitlement"] = entitlement
    elif "entitlement" in api_params:
        # 如果 entitlement 为空，从参数中移除
        api_params.pop("entitlement", None)

    # Step 4: 发送 HTTP GET 请求
    response = requests.get(API_BASE_URL, params=api_params)
    response.raise_for_status()  # 如果状态码不是 200-299，抛出异常

    # Step 5: 获取响应文本
    response_text = response.text

    # Step 6: 检查是否为频率限制错误
    # Alpha Vantage 的错误响应通常是 JSON 格式
    try:
        response_json = json.loads(response_text)

        # 检查 "Information" 字段（Alpha Vantage 的错误信息格式）
        if "Information" in response_json:
            info_message = response_json["Information"]

            # 判断是否是频率限制错误
            if "rate limit" in info_message.lower() or "api key" in info_message.lower():
                # 抛出自定义异常，触发 route_to_vendor 的回退机制
                raise AlphaVantageRateLimitError(
                    f"Alpha Vantage rate limit exceeded: {info_message}"
                )

    except json.JSONDecodeError:
        # JSON 解析失败，说明是 CSV 数据（正常的响应格式）
        pass

    # Step 7: 返回响应文本
    return response_text


# ==============================================================================
# 第五部分：CSV 数据处理函数
# ==============================================================================

def _filter_csv_by_date_range(csv_data: str, start_date: str, end_date: str) -> str:
    """
    根据日期范围过滤 CSV 数据。

    这个函数用于：
      - 获取完整的 CSV 数据后，按日期范围过滤
      - 避免 LLM 看到不相关日期的数据

    为什么需要这个函数？
    ---------------------
    Alpha Vantage 的 API 有两种输出大小：
      - compact: 返回最近 100 个交易日的数据
      - full: 返回最多 20 年的历史数据

    但 API 不支持指定日期范围过滤：
      - 如果我们需要 2024-01-01 到 2024-06-01 的数据
      - 只能先获取完整数据，然后在本地过滤

    处理流程：

        原始 CSV 数据：                          过滤后：
        ┌─────────────────────────┐          ┌─────────────────────────┐
        │ timestamp,open,high,... │          │ timestamp,open,high,... │
        │ 2023-01-01,100,105,...│  ──────►   │ 2024-01-01,180,185,...  │
        │ 2023-02-01,102,107,...│            │ 2024-02-01,182,187,...  │
        │ 2024-01-01,180,185,...│  (保留)    │ ...                     │
        │ 2024-02-01,182,187,...│  (保留)    └─────────────────────────┘
        │ 2024-03-01,185,190,...│  (保留)     
        │ 2025-01-01,200,205,...│  ──────►   (2025年数据被过滤掉)
        └─────────────────────────┘

    Args:
        csv_data: 原始 CSV 字符串（来自 Alpha Vantage API）
        start_date: 开始日期，格式 "YYYY-MM-DD"
        end_date: 结束日期，格式 "YYYY-MM-DD"

    Returns:
        过滤后的 CSV 字符串

    示例：
        >>> csv_data = "timestamp,value\\n2023-01-01,100\\n2024-01-01,200"
        >>> filtered = _filter_csv_by_date_range(csv_data, "2024-01-01", "2024-12-31")
        >>> print(filtered)
        timestamp,value
        2024-01-01,200
    """
    # 边界情况处理
    if not csv_data or csv_data.strip() == "":
        return csv_data

    try:
        # Step 1: 解析 CSV 数据为 DataFrame
        df = pd.read_csv(StringIO(csv_data))

        # Step 2: 确定日期列
        # 假设第一列是时间戳列
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

        # Step 3: 解析日期范围
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)

        # Step 4: 按日期范围过滤
        # 包含 start_date 和 end_date
        filtered_df = df[(df[date_col] >= start_dt) & (df[date_col] <= end_dt)]

        # Step 5: 转换回 CSV 字符串
        return filtered_df.to_csv(index=False)

    except Exception as e:
        # 如果过滤失败（可能是数据格式问题），返回原始数据
        print(f"Warning: Failed to filter CSV data by date range: {e}")
        return csv_data


# ==============================================================================
# 使用示例
# ==============================================================================

"""
如何在其他模块中使用这些函数：

from .alpha_vantage_common import (
    _make_api_request,
    _filter_csv_by_date_range,
    format_datetime_for_api,
    AlphaVantageRateLimitError
)

# 示例 1: 获取股票数据
def get_stock(symbol, start_date, end_date):
    params = {
        "symbol": symbol,
        "outputsize": "full",
        "datatype": "csv",
    }

    # 调用 API
    csv_data = _make_api_request("TIME_SERIES_DAILY_ADJUSTED", params)

    # 按日期过滤
    filtered_data = _filter_csv_by_date_range(csv_data, start_date, end_date)

    return filtered_data


# 示例 2: 获取新闻（使用日期格式化）
def get_news(ticker, start_date, end_date):
    params = {
        "tickers": ticker,
        "time_from": format_datetime_for_api(start_date),
        "time_to": format_datetime_for_api(end_date),
    }

    return _make_api_request("NEWS_SENTIMENT", params)


# 示例 3: 处理频率限制
try:
    data = _make_api_request("TIME_SERIES_DAILY", params)
except AlphaVantageRateLimitError:
    # 切换到备用数据源
    data = get_from_yfinance(...)
"""
