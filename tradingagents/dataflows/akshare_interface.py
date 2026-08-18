"""AkShare vendor facade.

Historically this 1600-line module held every AkShare implementation.
Since the Phase-4 split the implementations live in ``dataflows/akshare/``
(one module per domain); this file re-exports the public API so the
VENDOR_METHODS string registry (interface.py) and any direct importers
keep resolving unchanged.
"""

from tradingagents.dataflows.akshare.events import get_akshare_cn_earnings_calendar, get_akshare_cn_ipo_data, get_akshare_cn_limit_up_stocks, get_akshare_cn_m_a_news, get_akshare_cn_stock_pledge
from tradingagents.dataflows.akshare.financials import get_akshare_balance_sheet, get_akshare_cashflow, get_akshare_income_statement
from tradingagents.dataflows.akshare.flow import get_akshare_cn_market_flow, get_akshare_fund_flow
from tradingagents.dataflows.akshare.macro import get_akshare_cn_macro_data, get_akshare_cn_rate_outlook, get_akshare_cn_trade_data
from tradingagents.dataflows.akshare.news import get_akshare_cn_fintech_news, get_akshare_cn_new_energy_news, get_akshare_cn_pharma_news, get_akshare_cn_policy_news, get_akshare_cn_real_estate_news, get_akshare_cn_tech_sector_news, get_akshare_global_news, get_akshare_news
from tradingagents.dataflows.akshare.stock import get_akshare_fundamentals, get_akshare_stock_data

__all__ = [
    "get_akshare_balance_sheet",
    "get_akshare_cashflow",
    "get_akshare_cn_earnings_calendar",
    "get_akshare_cn_fintech_news",
    "get_akshare_cn_ipo_data",
    "get_akshare_cn_limit_up_stocks",
    "get_akshare_cn_m_a_news",
    "get_akshare_cn_macro_data",
    "get_akshare_cn_market_flow",
    "get_akshare_cn_new_energy_news",
    "get_akshare_cn_pharma_news",
    "get_akshare_cn_policy_news",
    "get_akshare_cn_rate_outlook",
    "get_akshare_cn_real_estate_news",
    "get_akshare_cn_stock_pledge",
    "get_akshare_cn_tech_sector_news",
    "get_akshare_cn_trade_data",
    "get_akshare_fund_flow",
    "get_akshare_fundamentals",
    "get_akshare_global_news",
    "get_akshare_income_statement",
    "get_akshare_news",
    "get_akshare_stock_data",
]
