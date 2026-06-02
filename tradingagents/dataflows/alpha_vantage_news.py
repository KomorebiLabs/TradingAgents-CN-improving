"""
================================================================================
                      ALPHA_VANTAGE_NEWS.PY 详解
                         新闻数据（含情感分析）
================================================================================

【模块定位】
    本文件是 TradingAgents 数据获取层的"新闻数据模块"，专门处理新闻获取。

    在项目中的定位：
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                        interface.py (路由层)                            │
    │                              │                                          │
    │        VENDOR_METHODS["get_news"]["alpha_vantage"]     → 本文件       │
    │        VENDOR_METHODS["get_global_news"]["alpha_vantage"] → 本文件    │
    │        VENDOR_METHODS["get_insider_transactions"]["alpha_vantage"] → 本文件│
    └─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │               alpha_vantage_news.py (当前文件)                           │
    │                                                                          │
    │  函数列表：                                                              │
    │    1. get_news()              → 按股票 ticker 获取新闻（带情感分数）     │
    │    2. get_global_news()       → 全球宏观经济新闻（按主题分类）           │
    │    3. get_insider_transactions() → 获取内部人员交易记录                  │
    │                                                                          │
    │  调用的公共工具（来自 alpha_vantage_common.py）：                         │
    │    • _make_api_request()       → 发送 HTTP 请求                        │
    │    • format_datetime_for_api()  → 日期格式转换                          │
    │                                                                          │
    └─────────────────────────────────────────────────────────────────────────┘

【核心优势：情感分数】
    Alpha Vantage 的新闻 API 最大的特色是自带"情感分数"（Sentiment Score）。

    这比 yfinance_news.py 的方案（依赖 LLM 自己判断情感）更精准：
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                                                                           │
    │   yfinance_news.py 方案：                                                 │
    │     步骤 1：获取新闻文本                                                   │
    │     步骤 2：LLM 阅读文本，自己判断情感                                    │
    │     问题：LLM 判断可能有偏差，且消耗更多 token                             │
    │                                                                           │
    │   Alpha Vantage 方案：                                                   │
    │     步骤 1：获取新闻文本 + 情感分数（API 直接给出）                       │
    │     步骤 2：LLM 参考情感分数做分析                                        │
    │     优势：情感分数是算法计算的结果，更客观                                  │
    │                                                                           │
    └─────────────────────────────────────────────────────────────────────────┘

【NEWS_SENTIMENT API 的情感分数】

    每条新闻返回的情感相关字段：

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  字段                  │  说明                                         │
    ├────────────────────────┼───────────────────────────────────────────────┤
    │  sentiment_score       │  情感分数，范围大约 -1 到 +1                   │
    │                        │  > 0 为正面，< 0 为负面，≈0 为中性             │
    │  sentiment            │  情感标签："Positive", "Negative", "Neutral"    │
    │  ticker_sentiment     │  每个 ticker 的情感贡献                        │
    │  ticker_sentiment_score│  该 ticker 的情感分数                         │
    └─────────────────────────────────────────────────────────────────────────┘

【topics 参数的作用】

    get_global_news() 使用 topics 参数过滤新闻类别：

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  topics 参数值                      │  覆盖的新闻类型                    │
    ├─────────────────────────────────────────────────────────────────────────┤
    │  financial_markets                 │  股市、金融市场                     │
    │  economy_macro                     │  宏观经济                           │
    │  economy_monetary                 │  货币政策                          │
    │  economy_fiscal                   │  财政政策                          │
    │  ipo                              │  IPO 相关                          │
    │  mergers_and_acquisitions          │  并购重组                          │
    │  commodities                      │  大宗商品                          │
    │  currencies                       │  外汇                              │
    │  company_news                     │  公司新闻                          │
    │  cryptocurrency                   │  加密货币                          │
    └─────────────────────────────────────────────────────────────────────────┘

    本文件使用的组合："financial_markets,economy_macro,economy_monetary"
    这覆盖了交易员最关心的三类宏观新闻。

================================================================================
"""

# ==============================================================================
# 导入层解析
# ==============================================================================
# 本文件调用 alpha_vantage_common.py 的两个工具函数

from .alpha_vantage_common import _make_api_request, format_datetime_for_api


# ==============================================================================
# 函数 1: get_news() — 按股票获取新闻
# ==============================================================================

def get_news(
    ticker: str,
    start_date: str,
    end_date: str
) -> dict[str, str] | str:
    """
    【函数功能】
        获取指定股票在指定日期范围内的新闻文章。

    【使用的 API】
        Alpha Vantage API: NEWS_SENTIMENT

    【在项目中的角色】
        这是 interface.py 中 VENDOR_METHODS["get_news"]["alpha_vantage"] 的实现。
        供 News Analyst（新闻分析师）分析个股新闻。

    【与 yfinance_news.py 的 get_news_yfinance() 对比】
        ┌─────────────────┬─────────────────────────────┬─────────────────────────────┐
        │      维度        │   Alpha Vantage 版本        │     yfinance 版本          │
        ├─────────────────┼─────────────────────────────┼─────────────────────────────┤
        │   情感分析       │   ✅ API 自带情感分数       │     ❌ 需要 LLM 判断        │
        │   过滤方式       │   tickers + 日期范围        │     ticker + 日期范围       │
        │   返回格式       │   JSON 字符串              │     Markdown 字符串        │
        │   文章数量       │   受 API limit 参数控制     │     受 count 参数控制       │
        └─────────────────┴─────────────────────────────┴─────────────────────────────┘

    【参数详解】

        ticker:
            股票代码，如 "NVDA"、"AAPL"、"MSFT"
            Alpha Vantage 支持多个代码，用逗号分隔，如 "NVDA,AAPL"

        start_date / end_date:
            日期范围，格式 "YYYY-MM-DD"
            注意：API 内部使用 format_datetime_for_api() 转换为 "YYYYMMDDTHHMM" 格式

    【日期格式转换】

        Alpha Vantage 的 NEWS_SENTIMENT API 要求时间是 YYYYMMDDTHHMM 格式：

        用户输入：    "2024-01-15"     → format_datetime_for_api() → "20240115T000000"
        用户输入：    "2024-01-31T23:59" → format_datetime_for_api() → "20240131T235900"

        这就是为什么需要 format_datetime_for_api() 工具函数。

    【API 返回的数据结构】

        Alpha Vantage 返回 JSON 格式的数据：

        {
            "items": "50",   ← 返回的新闻总数
            "feed": [
                {
                    "title": "NVIDIA Reports Record Earnings",
                    "summary": "NVIDIA reported fourth-quarter earnings...",
                    "banner_image": "https://...",
                    "source": "Reuters",
                    "overall_sentiment_score": 0.35,    ← 整体情感分数
                    "overall_sentiment_label": "Positive",← 情感标签
                    "time_published": "2024-01-15 10:30:00",
                    "authors": ["John Doe"],
                    "url": "https://...",
                    "source_domain": "reuters.com",
                    "ticker_sentiment": [
                        {
                            "ticker": "NVDA",
                            "sentiment_score": 0.42,
                            "sentiment": "Positive",
                            "relevance_score": "0.9"    ← 相关性分数
                        }
                    ]
                },
                { ... }
            ]
        }

    【关键字段解读】

        ┌─────────────────────────────────────────────────────────────────────┐
        │  字段                      │  解读                                    │
        ├────────────────────────────┼────────────────────────────────────────┤
        │  overall_sentiment_score  │  整条新闻的情感分数（-1 到 +1）          │
        │  overall_sentiment_label  │  情感标签：Positive / Negative / Neutral│
        │  ticker_sentiment         │  针对每个提及股票的情感                  │
        │  relevance_score          │  与该 ticker 的相关性（0 到 1）          │
        │  source_domain            │  来源网站域名，用于判断来源可信度        │
        └─────────────────────────────────────────────────────────────────────┘

    【返回值的处理】
        本函数直接返回 _make_api_request() 的结果（JSON 字符串）。
        这个 JSON 字符串会被传给 LLM，LLM 可以解析 JSON 结构来获取：
        • 新闻标题和摘要
        • 情感分数和标签
        • 每只提及股票的情感贡献
    """
    # 【教学】构建 API 参数
    # tickers: 股票代码
    # time_from / time_to: 日期范围（需要格式化）
    params = {
        "tickers": ticker,
        "time_from": format_datetime_for_api(start_date),
        "time_to": format_datetime_for_api(end_date),
    }

    # 【教学】调用 NEWS_SENTIMENT API
    # 返回值是 JSON 字符串，包含新闻列表和情感分数
    return _make_api_request("NEWS_SENTIMENT", params)


# ==============================================================================
# 函数 2: get_global_news() — 获取全球宏观经济新闻
# ==============================================================================

def get_global_news(
    curr_date: str,
    look_back_days: int = 7,
    limit: int = 50
) -> dict[str, str] | str:
    """
    【函数功能】
        获取全球宏观经济和市场相关的新闻文章。

    【使用的 API】
        Alpha Vantage API: NEWS_SENTIMENT（不带 tickers 参数）

    【与 get_news() 的区别】

        ┌─────────────────┬─────────────────────────────┬─────────────────────────────┐
        │      维度        │       get_news()            │     get_global_news()       │
        ├─────────────────┼─────────────────────────────┼─────────────────────────────┤
        │   新闻范围       │   特定股票的新闻            │   全球宏观经济新闻          │
        │   过滤方式       │   tickers 参数             │   topics 参数              │
        │   用途           │   分析个股                  │   分析大盘/宏观              │
        │   是否带情感分数  │   ✅ 是                    │     ✅ 是                  │
        └─────────────────┴─────────────────────────────┴─────────────────────────────┘

    【topics 参数的设计】

        本函数使用 topics = "financial_markets,economy_macro,economy_monetary"
        这个组合覆盖了交易员最关心的宏观新闻：

        • financial_markets：
          股市整体动态、指数涨跌、市场情绪

        • economy_macro：
          宏观经济数据（GDP、CPI、PPI）、经济趋势

        • economy_monetary：
          货币政策、央行决策、利率变化

    【为什么不用 tickers 参数？】

        因为 get_news() 是分析特定股票，需要 tickers 参数来过滤
        而 get_global_news() 是分析大盘，不绑定特定股票

        如果给 get_global_news() 传入 tickers，它就会变成 get_news()
        所以这里故意不加 tickers 参数

    【curr_date 和 look_back_days 的关系】

        ┌─────────────────────────────────────────────────────────────────────┐
        │                                                                           │
        │  curr_date = "2024-06-15", look_back_days = 7                          │
        │                                                                           │
        │  计算步骤：                                                               │
        │    1. curr_dt = 2024-06-15                                             │
        │    2. start_dt = curr_dt - 7天 = 2024-06-08                            │
        │    3. API 请求 time_from=20240608T000000, time_to=20240615T235959      │
        │                                                                           │
        │  含义：获取从 6月8日 到 6月15日 的全球宏观经济新闻                         │
        │                                                                           │
        └─────────────────────────────────────────────────────────────────────┘

    【limit 参数的作用】

        Alpha Vantage 的 NEWS_SENTIMENT API 支持 limit 参数：
        • 范围：1 到 1000
        • 默认值：50（本函数设为 50，yfinance 版本默认 10）
        • 作用：限制返回的新闻数量

        注意：API 可能返回超过 limit 数量的新闻（因为按 ticker 分组），
        所以这个参数是"软限制"，实际返回数量可能略多

    【与 yfinance_news.py 的 get_global_news_yfinance() 对比】

        ┌─────────────────┬─────────────────────────────┬─────────────────────────────┐
        │      维度        │   Alpha Vantage 版本        │     yfinance 版本          │
        ├─────────────────┼─────────────────────────────┼─────────────────────────────┤
        │   新闻来源       │   NEWS_SENTIMENT API        │     yf.Search() 搜索       │
        │   情感分析       │   ✅ 自带情感分数           │     ❌ 无                  │
        │   主题过滤       │   ✅ topics 参数            │     ❌ 无                  │
        │   搜索词         │   无（按主题分类）          │     手动定义 4 个搜索词     │
        │   去重           │   API 内部处理              │     手动基于标题去重       │
        │   默认数量       │   50                       │     10                     │
        └─────────────────┴─────────────────────────────┴─────────────────────────────┘

        结论：Alpha Vantage 版本更精准（按主题过滤 + 情感分析），
        yfinance 版本更灵活（可以自定义搜索词）
    """
    from datetime import datetime, timedelta

    # Calculate start date
    # 【教学】计算 look_back_days 天前的日期
    # 与 yfinance 版本使用 relativedelta 不同，这里用 timedelta
    # 因为只做天数运算，timedelta 足够了
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = curr_dt - timedelta(days=look_back_days)
    start_date = start_dt.strftime("%Y-%m-%d")

    # 【教学】构建 API 参数
    # 注意：没有 tickers 参数（这是与 get_news() 的关键区别）
    params = {
        "topics": "financial_markets,economy_macro,economy_monetary",
        # ↑ 按主题过滤，不绑定特定股票
        "time_from": format_datetime_for_api(start_date),
        "time_to": format_datetime_for_api(curr_date),
        "limit": str(limit),  # ← 转换为字符串（API 要求）
    }

    # 【教学】调用 NEWS_SENTIMENT API（不带 tickers 参数）
    return _make_api_request("NEWS_SENTIMENT", params)


# ==============================================================================
# 函数 3: get_insider_transactions() — 获取内部人员交易
# ==============================================================================

def get_insider_transactions(
    symbol: str
) -> dict[str, str] | str:
    """
    【函数功能】
        获取公司内部人员的股票交易记录。

    【使用的 API】
        Alpha Vantage API: INSIDER_TRANSACTIONS

    【什么是"内部人员"？】

        Alpha Vantage 对"内部人员"的定义遵循 SEC 规定：

        ┌─────────────────────────────────────────────────────────────────────┐
        │  内部人员类型                    │  说明                             │
        ├─────────────────────────────────────────────────────────────────────┤
        │  创始人 (Founder)               │  公司创办人                       │
        │  董事会成员 (Director)           │  董事会成员                       │
        │  高管 (Officer)                 │  CEO, CFO, CTO 等高管             │
        │  主要股东 (10% Owner)            │  持股 ≥ 10% 的大股东              │
        └─────────────────────────────────────────────────────────────────────┘

    【SEC 申报规定】

        美国 SEC 规定：
        • 内部人员交易后 2 个工作日内必须向 SEC 申报
        • 申报信息公开，Yahoo Finance / Alpha Vantage 整合这些数据

    【API 返回的数据结构】

        {
            "symbol": "NVDA",
            "data": [
                {
                    "name": "Jensen Huang",
                    "relationship": "Director",        ← 关系：创始人/董事/高管
                    "transactionDate": "2024-01-15",    ← 交易日期
                    "transactionType": "Sell",         ← 交易类型
                    "sharesTraded": 10000,              ← 交易股数
                    "sharePrice": 500.00,               ← 成交价
                    "totalValue": 5000000.00,           ← 总金额
                    "SECForm4": "https://..."          ← SEC 申报链接
                },
                { ... }
            ]
        }

    【交易类型解读】

        ┌─────────────────────────────────────────────────────────────────────┐
        │  交易类型          │  解读                                          │
        ├────────────────────┼──────────────────────────────────────────────┤
        │  P (Purchase)     │  买入 → 内部人看好公司（看多信号）             │
        │  S (Sale)         │  卖出 → 需要分析背景：                         │
        │                    │  • 可能是薪酬需要（无意义）                     │
        │                    │  • 可能是认为股价高估（谨慎）                   │
        │  D (Disposition)  │  处置（期权行权后卖出）                        │
        │  G (Gift)         │  赠予                                          │
        │  M (Option Exer) │  期权行权                                       │
        └─────────────────────────────────────────────────────────────────────┘

    【与 yfinance_news.py 的 get_insider_transactions() 对比】

        两个版本的实现非常相似，都调用各自数据源的 insider_transactions 接口。
        主要区别在于：
        • Alpha Vantage 版本返回格式可能更规范（符合 SEC 标准）
        • yfinance 版本可能覆盖更多非美国市场的数据

    【投资参考价值】

        ┌─────────────────────────────────────────────────────────────────────┐
        │  信号类型                  │  解读                                   │
        ├────────────────────────────┼────────────────────────────────────────┤
        │  大额买入 (Purchase)       │  强烈看多信号                            │
        │  大额卖出 (Sale)           │  谨慎对待，需分析背景                     │
        │  多人同时卖出              │  可能有问题，关注                         │
        │  期权行权后卖出            │  中性（可能是薪酬结构）                    │
        │  买入后很快卖出            │  内部人可能不看好                        │
        └─────────────────────────────────────────────────────────────────────┘

        重要提示：内幕交易信号应该结合其他分析一起看，
        不能作为唯一的投资依据。
    """

    # 【教学】构建 API 参数
    # INSIDER_TRANSACTIONS API 只需要 symbol 参数
    params = {
        "symbol": symbol,
    }

    # 【教学】调用 INSIDER_TRANSACTIONS API
    # 返回值是 JSON 字符串，包含内部人员交易列表
    return _make_api_request("INSIDER_TRANSACTIONS", params)
