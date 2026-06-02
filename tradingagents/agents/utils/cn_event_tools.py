"""
China A-share event-driven data tools.

This module provides specialized tools for accessing event-driven
information in the mainland China stock market, including:
- Earnings calendar (财报日历)
- IPO data (IPO 上市数据)
- M&A news (并购重组)

These tools help capture event-driven trading opportunities and risks.
"""

try:  # pragma: no cover - optional runtime dependency
    from langchain_core.tools import tool
except Exception:  # pragma: no cover
    def tool(func=None, **kwargs):
        if func is None:
            return lambda f: f
        setattr(func, "name", getattr(func, "__name__", "tool"))
        return func
from typing import Annotated

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_cn_earnings_calendar(
    look_forward_days: Annotated[int, "Number of days to look forward"] = 30,
    market: Annotated[str, "Market filter: main/chinext/star/bse/all"] = "all",
) -> str:
    """
    Retrieve upcoming earnings announcement calendar for A-share listed companies.

    This tool provides:
    - Upcoming earnings report dates (业绩报告发布日)
    - Earnings forecast dates (业绩预告/快报)
    - Dividend announcement dates (分红配股公告)

    Args:
        look_forward_days: Number of days to look forward (default: 30)
        market: Market filter:
            - "main": Shanghai/Shenzhen main board only
            - "chinext": ChiNext only
            - "star": STAR Market only
            - "bse": Beijing Stock Exchange only
            - "all": All markets (default)

    Returns:
        Formatted earnings calendar report
    """
    return route_to_vendor(
        "get_cn_earnings_calendar",
        look_forward_days,
        market
    )


@tool
def get_cn_ipo_data(
    status: Annotated[str, "IPO status: upcoming/recently_listed/all"] = "upcoming",
    limit: Annotated[int, "Maximum number of IPO entries to return"] = 20,
) -> str:
    """
    Retrieve IPO (Initial Public Offering) data for A-share market.

    This tool provides:
    - Upcoming IPOs (即将上市)
    - Recently listed companies (近期上市)
    - IPO subscription statistics (打新数据)

    Args:
        status: IPO status filter:
            - "upcoming": IPOs scheduled for listing
            - "recently_listed": Recently listed companies
            - "all": All IPO data (default)
        limit: Maximum number of entries to return (default: 20)

    Returns:
        Formatted IPO data report
    """
    return route_to_vendor(
        "get_cn_ipo_data",
        status,
        limit
    )


@tool
def get_cn_m_a_news(
    ticker: Annotated[str, "Ticker symbol of the company"],
    look_back_days: Annotated[int, "Number of days to look back"] = 90,
    limit: Annotated[int, "Maximum number of M&A news entries to return"] = 10,
) -> str:
    """
    Retrieve merger & acquisition (M&A) related news for a specific company.

    This tool focuses on:
    - Acquisition announcements (收购公告)
    - Merger plans (并购重组)
    - Strategic investment news (战略投资)
    - Restructuring news (资产重组)

    Args:
        ticker: Stock ticker symbol (e.g., "600519.SH")
        look_back_days: Number of days to look back (default: 90)
        limit: Maximum number of news entries to return (default: 10)

    Returns:
        Formatted M&A news report
    """
    return route_to_vendor(
        "get_cn_m_a_news",
        ticker,
        look_back_days,
        limit
    )


@tool
def get_cn_stock_pledge(
    ticker: Annotated[str, "Ticker symbol of the company"],
    look_back_days: Annotated[int, "Number of days to look back"] = 30,
) -> str:
    """
    Retrieve stock pledge (股权质押) information for a specific company.

    This tool provides:
    - Major shareholder pledge status (大股东质押情况)
    - Pledge ratio changes (质押比例变动)
    - Pledge risk warnings (质押风险提示)

    Useful for assessing:
    - Corporate governance risk
    - Major shareholder liquidity stress
    - Potential forced selling pressure

    Args:
        ticker: Stock ticker symbol (e.g., "600519.SH")
        look_back_days: Number of days to look back (default: 30)

    Returns:
        Formatted stock pledge report
    """
    return route_to_vendor(
        "get_cn_stock_pledge",
        ticker,
        look_back_days
    )


@tool
def get_cn_limit_up_stocks(
    trade_date: Annotated[str, "Trade date in yyyy-mm-dd format"],
    limit: Annotated[int, "Maximum number of limit-up stocks to return"] = 30,
) -> str:
    """
    Retrieve stocks that hit daily price limit (涨停) on a specific date.

    This tool provides:
    - Limit-up stocks list (涨停股列表)
    - Limit-down stocks list (跌停股列表)
    - Market sentiment indicators (市场情绪指标)

    Useful for:
    - Identifying market hotspots
    - Tracking momentum plays
    - Detecting abnormal trading patterns

    Args:
        trade_date: Trade date in yyyy-mm-dd format
        limit: Maximum number of entries to return (default: 30)

    Returns:
        Formatted limit-up/limit-down stocks report
    """
    return route_to_vendor(
        "get_cn_limit_up_stocks",
        trade_date,
        limit
    )
