"""
China A-share macro economics data tools.

This module provides specialized tools for accessing mainland China
macro economic indicators, including:
- GDP, CPI, PPI, M2 money supply
- Interest rates (LPR,存款准备金率)
- Exchange rates (RMB/USD)
- Trade data (import/export)

These tools are dynamically mounted based on the instrument's CN market profile.
"""

try:  # pragma: no cover - optional runtime dependency
    from langchain_core.tools import tool
except Exception:  # pragma: no cover
    def tool(func=None, **kwargs):
        if func is None:
            return lambda f: f
        setattr(func, "name", getattr(func, "__name__", "tool"))
        return func
from typing import Annotated, List

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_cn_macro_data(
    indicators: Annotated[List[str], "List of macro indicators to retrieve: gdp/cpi/ppi/m2/loan/industrial_production"] = None,
    period: Annotated[str, "Data period: quarterly/monthly"] = "quarterly",
    limit: Annotated[int, "Maximum number of data points to return"] = 8,
) -> str:
    """
    Retrieve mainland China macroeconomic indicator data.

    Available indicators:
    - gdp: GDP growth rate (国内生产总值增速)
    - cpi: Consumer Price Index (居民消费价格指数)
    - ppi: Producer Price Index (工业生产者出厂价格指数)
    - m2: M2 money supply growth (广义货币供应量增速)
    - loan: Social financing / loan growth (社融/贷款增速)
    - industrial_production: Industrial production index (工业增加值)

    Args:
        indicators: List of indicators to retrieve (default: all)
        period: Data period - "quarterly" or "monthly" (default: quarterly)
        limit: Maximum number of data points to return (default: 8)

    Returns:
        Formatted macro economic indicator data report
    """
    if indicators is None:
        indicators = ["gdp", "cpi", "ppi", "m2", "loan"]

    return route_to_vendor(
        "get_cn_macro_data",
        indicators,
        period,
        limit
    )


@tool
def get_cn_rate_outlook(
    focus: Annotated[str, "Rate focus: lpr/deposit_reserve/exchange/all"] = "all",
) -> str:
    """
    Retrieve mainland China interest rate and exchange rate outlook.

    This tool covers:
    - LPR (Loan Prime Rate) - 贷款市场报价利率
    - Deposit Reserve Ratio (RRR) changes - 存款准备金率调整
    - RMB/USD Exchange Rate trends - 人民币汇率走势
    - PBOC policy signals - 央行政策信号

    Args:
        focus: Rate focus area:
            - "lpr": Focus on LPR changes
            - "deposit_reserve": Focus on RRR adjustments
            - "exchange": Focus on RMB exchange rate
            - "all": Comprehensive rate outlook (default)

    Returns:
        Formatted interest rate and exchange rate outlook report
    """
    return route_to_vendor(
        "get_cn_rate_outlook",
        focus
    )


@tool
def get_cn_trade_data(
    months: Annotated[int, "Number of months to look back"] = 12,
    focus: Annotated[str, "Trade focus: import/export/balance/all"] = "all",
) -> str:
    """
    Retrieve mainland China import/export trade data.

    This tool covers:
    - Export data (出口数据)
    - Import data (进口数据)
    - Trade balance (贸易顺差/逆差)
    - Key trading partner breakdown (主要贸易伙伴)
    - Key commodity breakdown (主要商品类别)

    Args:
        months: Number of months to look back (default: 12)
        focus: Trade focus area:
            - "import": Focus on import data
            - "export": Focus on export data
            - "balance": Focus on trade balance
            - "all": Comprehensive trade data (default)

    Returns:
        Formatted trade data report
    """
    return route_to_vendor(
        "get_cn_trade_data",
        months,
        focus
    )


# ============================================================================
# Configuration for macro tool mounting
# ============================================================================

# CN macro tools are typically mounted for news analyst on CN equities
# when the market is in a volatile period or during major policy shifts

MACRO_TOOL_SKILLS = [
    "cn_macro_news",  # Skill that triggers macro tool mounting
]


def should_mount_macro_tools(skills: List[str]) -> bool:
    """
    Determine if macro tools should be mounted.

    Args:
        skills: List of skills from instrument profile

    Returns:
        True if macro tools should be mounted
    """
    for skill in MACRO_TOOL_SKILLS:
        if skill in skills:
            return True
    return False
