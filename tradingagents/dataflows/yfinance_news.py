"""
================================================================================
                     YFINANCE_NEWS.PY 详解
                   Yahoo Finance 新闻数据获取层
================================================================================

【模块定位】
    本文件是 TradingAgents 的"新闻数据获取层"，专门处理新闻相关的工具函数。

    在项目中的定位：
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                        interface.py (路由层)                            │
    │                              │                                          │
    │        VENDOR_METHODS["get_news"]["yfinance"]         → 本文件       │
    │        VENDOR_METHODS["get_global_news"]["yfinance"]  → 本文件       │
    └─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                   yfinance_news.py (当前文件)                            │
    │                                                                          │
    │  函数列表：                                                              │
    │    1. _extract_article_data()       → 工具函数：解析新闻文章结构        │
    │    2. get_news_yfinance()           → 获取指定股票的新闻                  │
    │    3. get_global_news_yfinance()    → 获取全球/宏观经济新闻              │
    │                                                                          │
    └─────────────────────────────────────────────────────────────────────────┘

【新闻数据的特殊性】
    与股票数据不同，新闻数据有几个独特的挑战：

    1. 结构不统一
       • Yahoo Finance 的新闻 API 返回格式经常变化
       • 可能返回"扁平结构"或"嵌套结构"
       • _extract_article_data() 需要处理这两种情况

    2. 日期过滤复杂
       • 新闻发布时间可能带有时区信息
       • 需要处理周末/假日的非交易日
       • 全球新闻需要防止"未来信息泄漏"

    3. 去重需求
       • 不同搜索词可能返回相同的新闻
       • 需要基于标题去重

【与 Alpha Vantage 新闻的区别】
    ┌─────────────────┬─────────────────────────────┬─────────────────────────────┐
    │      维度        │   Alpha Vantage 新闻        │     yfinance 新闻           │
    ├─────────────────┼─────────────────────────────┼─────────────────────────────┤
    │   数据来源       │   NEWS_SENTIMENT API       │   Yahoo Finance 新闻聚合     │
    │   情感分析       │   自带情感分数              │   无（需 LLM 判断）          │
    │   搜索能力       │   有限（按 ticker 过滤）     │   强大（yf.Search）         │
    │   全球新闻       │   有限                      │   支持（搜索词驱动）         │
    │   内幕交易       │   有专门的 API              │   在 y_finance.py           │
    └─────────────────┴─────────────────────────────┴─────────────────────────────┘

================================================================================
"""

# ==============================================================================
# 导入层解析
# ==============================================================================
# 本文件使用的外部依赖：
#   • yfinance as yf       → Yahoo Finance Python 包（核心数据源）
#   • datetime             → 日期时间处理
#   • dateutil.relativedelta → 灵活的日期计算

import yfinance as yf
from datetime import datetime
from dateutil.relativedelta import relativedelta

# 【教学】yf_retry 是 stockstats_utils.py 中定义的重试包装器
# 原理：当网络请求失败时，自动重试 3 次
# 作用：提高稳定性，应对临时的网络波动
from .stockstats_utils import normalize_yfinance_symbol, yf_retry


# ==============================================================================
# 工具函数 1: _extract_article_data() — 新闻文章数据提取
# ==============================================================================

def _extract_article_data(article: dict) -> dict:
    """
    【函数功能】
        从 yfinance 新闻 API 返回的原始数据中，提取标准化的文章信息。

    【为什么需要这个函数？】
        Yahoo Finance 新闻 API 的返回格式不固定：

        ┌─────────────────────────────────────────────────────────────────────┐
        │  格式 A：嵌套结构 (nested)                                           │
        │  ┌─────────────────────────────────────────────────────────────┐   │
        │  │ {                                                             │   │
        │  │     "content": {                                             │   │
        │  │         "title": "NVIDIA reports record earnings",            │   │
        │  │         "summary": "...",                                    │   │
        │  │         "provider": {"displayName": "Reuters"},               │   │
        │  │         "pubDate": "2024-01-15T10:30:00Z",                   │   │
        │  │         "canonicalUrl": {"url": "https://..."}               │   │
        │  │     }                                                         │   │
        │  │ }                                                             │   │
        │  └─────────────────────────────────────────────────────────────┘   │
        ├─────────────────────────────────────────────────────────────────────┤
        │  格式 B：扁平结构 (flat)                                            │
        │  ┌─────────────────────────────────────────────────────────────┐   │
        │  │ {                                                             │   │
        │  │     "title": "NVIDIA reports record earnings",                │   │
        │  │     "summary": "...",                                        │   │
        │  │     "publisher": "Reuters",                                  │   │
        │  │     "link": "https://..."                                    │   │
        │  │ }                                                             │   │
        │  └─────────────────────────────────────────────────────────────┘   │
        └─────────────────────────────────────────────────────────────────────┘

        这个函数统一处理两种格式，输出标准化字典：
        {
            "title": ...,
            "summary": ...,
            "publisher": ...,
            "link": ...,
            "pub_date": ... (datetime 对象或 None)
        }

    【参数】
        article: dict — yfinance 返回的原始新闻条目

    【返回值】
        dict — 标准化后的文章数据，包含：
        • title: 文章标题
        • summary: 文章摘要
        • publisher: 发布媒体
        • link: 文章链接
        • pub_date: 发布时间 (datetime 对象)
    """
    # Handle nested content structure
    # 【教学】检查是否是嵌套结构
    # "content" 键存在 → 嵌套结构（格式 A）
    # 不存在 → 扁平结构（格式 B）
    if "content" in article:
        content = article["content"]
        title = content.get("title", "No title")
        summary = content.get("summary", "")
        provider = content.get("provider", {})
        publisher = provider.get("displayName", "Unknown")

        # Get URL from canonicalUrl or clickThroughUrl
        # 【教学】URL 可能出现在两个字段中
        # canonicalUrl：官方链接（首选）
        # clickThroughUrl：跳转链接（备选）
        # 用 or 运算符实现"短路"，优先取 canonicalUrl
        url_obj = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
        link = url_obj.get("url", "")

        # Get publish date
        # 【教学】解析发布时间
        # 格式：ISO 8601 格式，如 "2024-01-15T10:30:00Z"
        # datetime.fromisoformat() 可以解析这种格式
        # 但 Z 需要替换为 +00:00（UTC 时区）
        pub_date_str = content.get("pubDate", "")
        pub_date = None
        if pub_date_str:
            try:
                # .replace("Z", "+00:00") 处理 ISO 8601 的 Z 表示法
                pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                # 解析失败时返回 None，不中断流程
                pass

        return {
            "title": title,
            "summary": summary,
            "publisher": publisher,
            "link": link,
            "pub_date": pub_date,
        }
    else:
        # Fallback for flat structure
        # 【教学】扁平结构的处理
        # 直接从根字典取值，缺失的字段返回默认值
        return {
            "title": article.get("title", "No title"),
            "summary": article.get("summary", ""),
            "publisher": article.get("publisher", "Unknown"),
            "link": article.get("link", ""),
            "pub_date": None,
        }


# ==============================================================================
# 函数 2: get_news_yfinance() — 获取指定股票的新闻
# ==============================================================================

def get_news_yfinance(
    ticker: str,
    start_date: str,
    end_date: str,
) -> str:
    """
    【函数功能】
        获取指定股票在指定日期范围内的新闻文章。

    【在项目中的角色】
        这是 interface.py 中 VENDOR_METHODS["get_news"]["yfinance"] 的实现。
        供 News Analyst（新闻分析师）使用。

    【数据流】
        get_news_yfinance("NVDA", "2024-01-01", "2024-01-31")
                │
                ├──► yf.Ticker("NVDA")
                ├──► stock.get_news(count=20)
                │       获取最近 20 条新闻
                │
                ├──► _extract_article_data() 解析每条新闻
                │       处理嵌套/扁平两种格式
                │
                ├──► 日期过滤
                │       只保留 start_date 到 end_date 范围内的新闻
                │       注意：新闻发布时区可能被 strip
                │
                └──► 格式化输出
                        返回 Markdown 格式的新闻列表

    【返回值格式示例】
        ## NVDA News, from 2024-01-01 to 2024-01-31:

        ### NVIDIA Reports Record Q4 Earnings (source: Reuters)
        NVIDIA reported fourth-quarter earnings that exceeded analyst expectations,
        with revenue growing 265% year-over-year.
        Link: https://finance.yahoo.com/news/...

        ### AI Chip Demand Surges (source: Bloomberg)
        ...
    """
    try:
        # 【教学】创建 Ticker 对象并获取新闻
        # 注意：yfinance 的 get_news() 只返回最近的新闻
        # 不支持按日期范围过滤，所以在本地做日期过滤
        stock = yf.Ticker(normalize_yfinance_symbol(ticker))
        news = yf_retry(lambda: stock.get_news(count=20))

        if not news:
            return f"No news found for {ticker}"

        # Parse date range for filtering
        # 【教学】解析日期范围
        # 用于后续过滤：只保留范围内的新闻
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        news_str = ""
        filtered_count = 0

        for article in news:
            # 【教学】提取标准化文章数据
            data = _extract_article_data(article)

            # Filter by date if publish time is available
            # 【教学】日期过滤逻辑
            # 如果有发布时间，按照时间范围过滤
            # 如果没有发布时间（pub_date=None），跳过过滤（可能是旧数据）
            if data["pub_date"]:
                # 【教学】处理时区
                # pub_date 可能是 UTC 时间，strip 时区后与本地日期比较
                pub_date_naive = data["pub_date"].replace(tzinfo=None)

                # relativedelta(days=1) 是为了包含 end_date 当天的新闻
                # 因为有些新闻可能在美国东部时间发布，但转换为 UTC 时会"跨越"日期
                if not (start_dt <= pub_date_naive <= end_dt + relativedelta(days=1)):
                    continue

            # 【教学】构建 Markdown 格式输出
            # ### 标题 (source: 发布媒体)
            # 摘要
            # Link: 链接
            news_str += f"### {data['title']} (source: {data['publisher']})\n"
            if data["summary"]:
                news_str += f"{data['summary']}\n"
            if data["link"]:
                news_str += f"Link: {data['link']}\n"
            news_str += "\n"
            filtered_count += 1

        # 【教学】如果没有匹配的日期范围，返回提示
        if filtered_count == 0:
            return f"No news found for {ticker} between {start_date} and {end_date}"

        # 【教学】添加头部信息
        return f"## {ticker} News, from {start_date} to {end_date}:\n\n{news_str}"

    except Exception as e:
        return f"Error fetching news for {ticker}: {str(e)}"


# ==============================================================================
# 函数 3: get_global_news_yfinance() — 获取全球/宏观经济新闻
# ==============================================================================

def get_global_news_yfinance(
    curr_date: str,
    look_back_days: int = 7,
    limit: int = 10,
) -> str:
    """
    【函数功能】
        获取全球/宏观经济相关的新闻文章。

    【与 get_news_yfinance() 的区别】
        ┌─────────────────┬─────────────────────────────┬─────────────────────────────┐
        │      函数        │    get_news_yfinance()      │  get_global_news_yfinance() │
        ├─────────────────┼─────────────────────────────┼─────────────────────────────┤
        │   新闻来源       │   特定股票的新闻             │   全网宏观经济新闻          │
        │   获取方式       │   ticker.get_news()         │   yf.Search() 搜索         │
        │   过滤方式       │   按 ticker 过滤            │   按关键词搜索             │
        │   使用场景       │   News Analyst              │   News Analyst             │
        └─────────────────┴─────────────────────────────┴─────────────────────────────┘

    【在项目中的角色】
        这是 interface.py 中 VENDOR_METHODS["get_global_news"]["yfinance"] 的实现。
        供 News Analyst 分析"大盘走势"和"宏观经济环境"。

    【搜索关键词设计】
        search_queries 定义了"宏观经济"相关的搜索词：

        ┌─────────────────────────────────────────────────────────────┐
        │  关键词                       │  覆盖的新闻类型              │
        ├─────────────────────────────────────────────────────────────┤
        │  stock market economy         │   股市整体动态              │
        │  Federal Reserve interest rates│   美联储政策                │
        │  inflation economic outlook   │   通胀和经济前景             │
        │  global markets trading       │   全球市场交易              │
        └─────────────────────────────────────────────────────────────┘

    【防"未来信息泄漏"机制】
        ┌─────────────────────────────────────────────────────────────┐
        │  问题：新闻 API 返回的是当前时间附近的新闻                    │
        │  风险：如果 curr_date 是"过去某一天"，可能返回"未来"新闻      │
        │                                                               │
        │  解决方案：                                                   │
        │    1. 计算 look_back_days 天前作为起始日期                    │
        │    2. 过滤掉 pub_date > curr_date + 1 天的新闻               │
        │    3. 确保新闻不"泄露"到模拟交易日期之后                       │
        └─────────────────────────────────────────────────────────────┘

    【去重机制】
        ┌─────────────────────────────────────────────────────────────┐
        │  问题：不同搜索词可能返回相同的新闻                           │
        │  解决：用 seen_titles 集合记录已见过的标题                     │
        │                                                               │
        │  代码逻辑：                                                   │
        │    if title not in seen_titles:                             │
        │        seen_titles.add(title)                               │
        │        all_news.append(article)                             │
        └─────────────────────────────────────────────────────────────┘
    """
    # Search queries for macro/global news
    # 【教学】搜索关键词列表
    # 这些关键词覆盖了主要的宏观经济新闻类型
    # 注意：yfinance 的搜索功能基于 Yahoo 的新闻聚合，可能不够精准
    search_queries = [
        "stock market economy",
        "Federal Reserve interest rates",
        "inflation economic outlook",
        "global markets trading",
    ]

    all_news = []
    seen_titles = set()  # 【教学】去重集合

    try:
        for query in search_queries:
            # 【教学】执行搜索
            # yf.Search() 是 Yahoo Finance 的新闻搜索接口
            # 参数：
            #   • query: 搜索词
            #   • news_count: 返回的新闻数量
            #   • enable_fuzzy_query: 模糊匹配（启用）
            search = yf_retry(lambda q=query: yf.Search(
                query=q,
                news_count=limit,
                enable_fuzzy_query=True,
            ))

            if search.news:
                for article in search.news:
                    # Handle both flat and nested structures
                    # 【教学】处理嵌套/扁平两种格式
                    if "content" in article:
                        data = _extract_article_data(article)
                        title = data["title"]
                    else:
                        title = article.get("title", "")

                    # Deduplicate by title
                    # 【教学】基于标题去重
                    # 为什么不基于链接去重？
                    # 因为同一篇文章可能被多个来源转载，链接不同但标题相同
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        all_news.append(article)

            # 【教学】达到数量上限后停止搜索
            # 避免不必要的 API 调用
            if len(all_news) >= limit:
                break

        if not all_news:
            return f"No global news found for {curr_date}"

        # Calculate date range
        # 【教学】计算日期范围
        # start_date = curr_date - look_back_days
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_dt = curr_dt - relativedelta(days=look_back_days)
        start_date = start_dt.strftime("%Y-%m-%d")

        news_str = ""

        for article in all_news[:limit]:
            # 【教学】遍历新闻并格式化
            # 注意：这里有"未来信息泄漏"保护机制
            if "content" in article:
                data = _extract_article_data(article)

                # Skip articles published after curr_date (look-ahead guard)
                # 【教学】防止"未来信息泄漏"
                # 如果新闻发布日期在 curr_date 之后，说明这是"未来"新闻
                # 在模拟交易场景中不应该看到这些新闻
                if data.get("pub_date"):
                    pub_naive = data["pub_date"].replace(tzinfo=None) if hasattr(data["pub_date"], "replace") else data["pub_date"]
                    # relativedelta(days=1) 允许 1 天的时区误差
                    if pub_naive > curr_dt + relativedelta(days=1):
                        continue

                title = data["title"]
                publisher = data["publisher"]
                link = data["link"]
                summary = data["summary"]
            else:
                title = article.get("title", "No title")
                publisher = article.get("publisher", "Unknown")
                link = article.get("link", "")
                summary = ""

            # 【教学】构建 Markdown 输出
            news_str += f"### {title} (source: {publisher})\n"
            if summary:
                news_str += f"{summary}\n"
            if link:
                news_str += f"Link: {link}\n"
            news_str += "\n"

        # 【教学】添加头部信息
        return f"## Global Market News, from {start_date} to {curr_date}:\n\n{news_str}"

    except Exception as e:
        return f"Error fetching global news: {str(e)}"
