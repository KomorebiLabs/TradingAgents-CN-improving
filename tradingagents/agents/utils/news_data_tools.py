"""
News Data Tools with RAG Enhancement.

This module wraps the dataflow interface with LangChain tools,
providing automatic RAG enhancement for news-related queries.
"""

import os
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

# Import RAG middleware
try:
    from tradingagents.agents.utils.rag import get_middleware, RAGMiddleware
    MIDDLEWARE_AVAILABLE = True
except ImportError:
    MIDDLEWARE_AVAILABLE = False
    get_middleware = None


def _get_rag_middleware():
    """Get or create the RAG middleware instance."""
    if not MIDDLEWARE_AVAILABLE:
        return None
    return get_middleware()


@tool
def get_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve news data for a given ticker symbol.
    Automatically enhanced with RAG when enabled.
    Args:
        ticker (str): Ticker symbol
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted string containing news data, possibly with RAG enhancement
    """
    middleware = _get_rag_middleware()
    if middleware and middleware.config.auto_intercept:
        return middleware.execute(
            "get_news",
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
        )
    return route_to_vendor("get_news", ticker, start_date, end_date)


@tool
def get_global_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of articles to return"] = 5,
) -> str:
    """
    Retrieve global news data.
    Automatically enhanced with RAG when enabled.
    Args:
        curr_date (str): Current date in yyyy-mm-dd format
        look_back_days (int): Number of days to look back (default 7)
        limit (int): Maximum number of articles to return (default 5)
    Returns:
        str: A formatted string containing global news data
    """
    middleware = _get_rag_middleware()
    if middleware and middleware.config.auto_intercept:
        return middleware.execute(
            "get_global_news",
            curr_date=curr_date,
            look_back_days=look_back_days,
            limit=limit,
        )
    return route_to_vendor("get_global_news", curr_date, look_back_days, limit)


@tool
def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve insider transaction information about a company.
    Uses the configured news_data vendor.
    Args:
        ticker (str): Ticker symbol of the company
    Returns:
        str: A report of insider transaction data
    """
    return route_to_vendor("get_insider_transactions", ticker)


@tool
def get_cn_policy_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of policy-sensitive events to return"] = 6,
) -> str:
    """
    Retrieve mainland China policy, regulation, and macro-liquidity sensitive news.
    Automatically enhanced with RAG when enabled.
    """
    middleware = _get_rag_middleware()
    if middleware and middleware.config.auto_intercept:
        return middleware.execute(
            "get_cn_policy_news",
            curr_date=curr_date,
            look_back_days=look_back_days,
            limit=limit,
        )
    return route_to_vendor("get_cn_policy_news", curr_date, look_back_days, limit)


@tool
def get_cn_market_flow(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve mainland China market-flow proxy data for a single stock.
    Uses the configured news_data vendor.
    """
    return route_to_vendor("get_cn_market_flow", ticker)
