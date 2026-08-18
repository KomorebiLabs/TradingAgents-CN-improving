"""AkShare financial-statement vendors: balance sheet, cashflow, income."""
from __future__ import annotations

import time
import threading
from datetime import datetime, timedelta
from io import StringIO
from typing import Iterable, Tuple

import pandas as pd

from tradingagents.dataflows.akshare._shared import _normalize_cn_symbol, _render_bullets, _require_akshare, _throttle_eastmoney


def _prepare_financial_statement(df: pd.DataFrame, statement_type: str, limit: int = 8) -> pd.DataFrame:
    """Prepare financial statement data for display."""
    if df.empty:
        return df

    working = df.copy()

    # Ensure date column is properly formatted
    date_columns = ["报告日期", "日期", "截止日期", "报告期"]
    date_col = None
    for col in date_columns:
        if col in working.columns:
            date_col = col
            break

    if date_col:
        working = working.sort_values(date_col, ascending=False)

    return working.head(limit).copy()


def _render_financial_statement(df: pd.DataFrame, statement_type: str, code: str) -> str:
    """Render financial statement data for display."""
    if df.empty:
        return f"No {statement_type} data available for {code}"

    entries = []
    for _, row in df.iterrows():
        lines = []
        for col, val in row.items():
            if pd.notna(val):
                # Format numeric values
                if isinstance(val, (int, float)):
                    val_str = f"{val:,.2f}" if abs(val) >= 1 else f"{val:.4f}"
                else:
                    val_str = str(val)
                lines.append(f"{col}: {val_str}")
        if lines:
            entries.append(_render_bullets(lines))

    return f"# {code} {statement_type}\n\n" + "\n\n".join(entries)


def get_akshare_balance_sheet(symbol: str, period: str = "quarterly", limit: int = 8) -> str:
    """
    Get A-share balance sheet data.

    Args:
        symbol: A-share ticker (e.g., "600519.SH" or "000001.SZ")
        period: Data period - "quarterly" (default) or "annual"
        limit: Maximum number of periods to return

    Returns:
        Balance sheet data in formatted string
    """
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    try:
        # Try to get balance sheet data
        df = ak.stock_balance_sheet_by_report_em(symbol=code)

        if df.empty:
            return f"No balance sheet data available for {code}.{exchange.upper()}"

        prepared = _prepare_financial_statement(df, "Balance Sheet", code)

        header = (
            f"# {code}.{exchange.upper()} Balance Sheet\n"
            f"# Period: {period}\n"
            f"# Vendor: akshare.stock_balance_sheet_by_report_em\n"
            f"# Records: {len(prepared)}\n\n"
        )

        return header + _render_financial_statement(prepared, "Balance Sheet", code)

    except Exception as e:
        return f"Balance sheet data unavailable for {code}.{exchange.upper()}: {str(e)}"


def get_akshare_cashflow(symbol: str, period: str = "quarterly", limit: int = 8) -> str:
    """
    Get A-share cash flow statement data.

    Args:
        symbol: A-share ticker (e.g., "600519.SH" or "000001.SZ")
        period: Data period - "quarterly" (default) or "annual"
        limit: Maximum number of periods to return

    Returns:
        Cash flow statement data in formatted string
    """
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    try:
        # Try to get cash flow data
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=code)

        if df.empty:
            return f"No cash flow data available for {code}.{exchange.upper()}"

        prepared = _prepare_financial_statement(df, "Cash Flow Statement", code)

        header = (
            f"# {code}.{exchange.upper()} Cash Flow Statement\n"
            f"# Period: {period}\n"
            f"# Vendor: akshare.stock_cash_flow_sheet_by_report_em\n"
            f"# Records: {len(prepared)}\n\n"
        )

        return header + _render_financial_statement(prepared, "Cash Flow Statement", code)

    except Exception as e:
        return f"Cash flow data unavailable for {code}.{exchange.upper()}: {str(e)}"


def get_akshare_income_statement(symbol: str, period: str = "quarterly", limit: int = 8) -> str:
    """
    Get A-share income statement data.

    Args:
        symbol: A-share ticker (e.g., "600519.SH" or "000001.SZ")
        period: Data period - "quarterly" (default) or "annual"
        limit: Maximum number of periods to return

    Returns:
        Income statement data in formatted string
    """
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    try:
        # Try to get income statement data
        df = ak.stock_profit_sheet_by_report_em(symbol=code)

        if df.empty:
            return f"No income statement data available for {code}.{exchange.upper()}"

        prepared = _prepare_financial_statement(df, "Income Statement", code)

        header = (
            f"# {code}.{exchange.upper()} Income Statement\n"
            f"# Period: {period}\n"
            f"# Vendor: akshare.stock_profit_sheet_by_report_em\n"
            f"# Records: {len(prepared)}\n\n"
        )

        return header + _render_financial_statement(prepared, "Income Statement", code)

    except Exception as e:
        return f"Income statement data unavailable for {code}.{exchange.upper()}: {str(e)}"
