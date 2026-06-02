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
def get_fundamentals(
    ticker: Annotated[str, "ticker symbol, e.g. AAPL for US stocks, 600519.SH for China A-shares"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
) -> str:
    """
    Retrieve comprehensive fundamental data for a given ticker symbol.

    Returns company overview including:
    - Valuation metrics: P/E ratio, P/B ratio, Market Cap
    - Share structure: Total shares, Float shares
    - Company info: Industry, Listing date
    - For US stocks: EPS, Dividend yield, 52-week range
    - For CN A-shares: Total market cap, Float market cap

    Args:
        ticker (str): Ticker symbol (US: AAPL, NVDA | CN: 600519.SH, 000001.SZ)
        curr_date (str): Current date, format: yyyy-mm-dd

    Returns:
        Formatted string containing company fundamentals snapshot
    """
    return route_to_vendor("get_fundamentals", ticker, curr_date)


@tool
def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol, e.g. AAPL or 600519.SH"],
    freq: Annotated[str, "reporting frequency: 'annual' for yearly or 'quarterly' for quarterly reports"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve balance sheet data showing company's financial position.

    Balance sheet components:
    - Assets: Cash, Receivables, Inventory, Total Assets
    - Liabilities: Accounts Payable, Short/Long-term debt, Total Liabilities
    - Equity: Shareholders' Equity, Retained Earnings

    Key ratios derivable:
    - Debt-to-Equity = Total Liabilities / Shareholders' Equity
    - Current Ratio = Current Assets / Current Liabilities

    Args:
        ticker (str): Ticker symbol (US: AAPL | CN: 600519.SH)
        freq (str): 'annual' or 'quarterly' (default: quarterly)
        curr_date (str): Current date for CN A-shares reference (yyyy-mm-dd)

    Returns:
        Formatted string with balance sheet data for recent periods
    """
    return route_to_vendor("get_balance_sheet", ticker, freq, curr_date)


@tool
def get_cashflow(
    ticker: Annotated[str, "ticker symbol, e.g. AAPL or 600519.SH"],
    freq: Annotated[str, "reporting frequency: 'annual' for yearly or 'quarterly' for quarterly reports"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve cash flow statement showing cash movement.

    Cash flow categories:
    - Operating: Net income, Depreciation, Working capital changes
    - Investing: CapEx, Asset sales, M&A activities
    - Financing: Dividends, Share buybacks, Debt issuance/repayment

    Key metrics:
    - Free Cash Flow = Operating Cash Flow - CapEx
    - Positive FCF indicates ability to fund growth/dividends

    Args:
        ticker (str): Ticker symbol (US: AAPL | CN: 600519.SH)
        freq (str): 'annual' or 'quarterly' (default: quarterly)
        curr_date (str): Current date for CN A-shares reference (yyyy-mm-dd)

    Returns:
        Formatted string with cash flow data for recent periods
    """
    return route_to_vendor("get_cashflow", ticker, freq, curr_date)


@tool
def get_income_statement(
    ticker: Annotated[str, "ticker symbol, e.g. AAPL or 600519.SH"],
    freq: Annotated[str, "reporting frequency: 'annual' for yearly or 'quarterly' for quarterly reports"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve income statement showing profitability.

    Income statement components:
    - Revenue/Sales: Total revenue, Net revenue
    - Gross Profit: Revenue - COGS, Gross margin
    - Operating Income: EBIT, Operating margin
    - Net Income: After taxes, EPS (Earnings Per Share)

    Key metrics:
    - Profit Margins: Gross, Operating, Net
    - YoY Growth: Revenue growth, Profit growth
    - For CN A-shares: Operating revenue, Total profit, Net profit attributable

    Args:
        ticker (str): Ticker symbol (US: AAPL | CN: 600519.SH)
        freq (str): 'annual' or 'quarterly' (default: quarterly)
        curr_date (str): Current date for CN A-shares reference (yyyy-mm-dd)

    Returns:
        Formatted string with income statement data for recent periods
    """
    return route_to_vendor("get_income_statement", ticker, freq, curr_date)
