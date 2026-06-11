"""
A-share Technical Indicators Module.

Provides technical indicator calculations for Chinese A-share stocks using
Tencent/Sina K-line data via ScreenerDataAccess and stockstats library.

This module is registered as the implementation for:
    VENDOR_METHODS["get_indicators"]["tencent_finance"]
    VENDOR_METHODS["get_indicators"]["sina_finance"]

Usage:
    result = get_cn_indicators("sh600519", "rsi", "2026-01-15", look_back_days=60)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Annotated, Optional

import pandas as pd
from stockstats import wrap

from tradingagents.dataflows.config import get_config
from tradingagents.screener.data_access import ScreenerDataAccess

logger = logging.getLogger(__name__)


def _normalize_date(s: str) -> str:
    """Convert YYYYMMDD to YYYY-MM-DD, pass through already formatted dates."""
    s = s.strip()
    if not s:
        return s
    if "-" in s:
        return s
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def _get_cn_hist_data(
    symbol: str,
    curr_date: str,
    look_back_days: int = 30,
) -> pd.DataFrame | None:
    """
    Fetch historical K-line data for A-share stocks from Tencent/Sina via ScreenerDataAccess.

    Args:
        symbol: A-share ticker, supports formats like sh600519, sz000001, 600519, etc.
        curr_date: Current date in YYYY-MM-DD or YYYYMMDD format.
        look_back_days: Number of historical trading days to fetch.

    Returns:
        DataFrame with stockstats-compatible columns (Date, Open, High, Low, Close, Volume),
        or None if data fetch fails.
    """
    try:
        access = ScreenerDataAccess(config=get_config())

        end_date = _normalize_date(curr_date)
        start_dt = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=look_back_days * 2)
        start_date = start_dt.strftime("%Y-%m-%d")

        df = access.fetch_hist(
            ticker=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )

        if df is None or (hasattr(df, "empty") and df.empty):
            logger.warning(f"No historical data returned for {symbol}")
            return None

        df = df.copy()

        col_map = {
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
        for old_col, new_col in col_map.items():
            if old_col in df.columns and old_col != new_col:
                df.rename(columns={old_col: new_col}, inplace=True)

        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date"])

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["Close"])
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = df[col].ffill().bfill()

        df = df.sort_values("Date").reset_index(drop=True)

        return df

    except Exception as exc:
        logger.error(f"Failed to fetch CN hist data for {symbol}: {exc}")
        return None


def _calculate_cn_indicator(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int = 30,
) -> str:
    """
    Calculate a technical indicator for an A-share stock using Tencent/Sina data.

    Args:
        symbol: A-share ticker symbol.
        indicator: Technical indicator name supported by stockstats (e.g., rsi, macd, bollinger).
        curr_date: Current date in YYYY-MM-DD format.
        look_back_days: Historical lookback window.

    Returns:
        CSV-formatted string with indicator values for matching date,
        or error message string.
    """
    df = _get_cn_hist_data(symbol, curr_date, look_back_days)

    if df is None or df.empty:
        return "N/A: Failed to fetch historical data"

    try:
        stock_df = wrap(df)

        curr_date_str = pd.to_datetime(curr_date).strftime("%Y-%m-%d")
        stock_df["Date"] = stock_df["Date"].dt.strftime("%Y-%m-%d")

        stock_df[indicator]

        matching_rows = stock_df[stock_df["Date"].str.startswith(curr_date_str)]

        if matching_rows.empty:
            return f"N/A: {curr_date} is not a trading day (weekend or holiday)"

        result_df = matching_rows[["Date", indicator]].copy()
        return result_df.to_csv(index=False)

    except KeyError:
        return f"N/A: Indicator '{indicator}' not supported by stockstats"
    except Exception as exc:
        logger.error(f"Indicator calculation failed for {symbol}/{indicator}: {exc}")
        return f"N/A: Calculation error - {exc}"


def get_cn_indicators(
    symbol: Annotated[str, "A-share ticker symbol (e.g. sh600519, sz000001)"],
    indicator: Annotated[
        str,
        "Technical indicator name (e.g. rsi, macd, bollinger, sma, ema, adx, cci, willr)",
    ],
    curr_date: Annotated[str, "Current date in YYYY-MM-DD format"],
    look_back_days: Annotated[
        int, "Number of historical trading days to fetch for calculation"
    ] = 30,
) -> str:
    """
    Get technical indicators for Chinese A-share stocks.

    This function is registered in VENDOR_METHODS as the implementation for:
        - VENDOR_METHODS["get_indicators"]["tencent_finance"]
        - VENDOR_METHODS["get_indicators"]["sina_finance"]

    It fetches K-line data from Tencent Finance (primary) via ScreenerDataAccess,
    then calculates technical indicators using the stockstats library.

    Supported indicators include:
        - rsi: Relative Strength Index
        - macd: Moving Average Convergence Divergence
        - macds: MACD Signal
        - macdh: MACD Histogram
        - bollinger: Bollinger Bands
        - sma: Simple Moving Average
        - ema: Exponential Moving Average
        - adx: Average Directional Index
        - cci: Commodity Channel Index
        - willr: Williams %R
        - mfi: Money Flow Index
        - obv: On Balance Volume
        - adl: Accumulation/Distribution Line
        - tr: True Range
        - atr: Average True Range

    Args:
        symbol: A-share ticker in formats like sh600519, sz000001, 600519.SS, etc.
        indicator: Technical indicator name recognized by stockstats.
        curr_date: Current/reference date in YYYY-MM-DD format.
        look_back_days: Historical window for calculation (default 30 trading days).

    Returns:
        CSV string with Date and indicator columns, or "N/A" message if unavailable.

    Example:
        >>> result = get_cn_indicators("sh600519", "rsi", "2026-01-15", 60)
        >>> print(result)
        Date,rsi
        2026-01-15,45.23
    """
    return _calculate_cn_indicator(symbol, indicator, curr_date, look_back_days)
