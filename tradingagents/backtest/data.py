"""Backtest data access (R1): pool close prices + index benchmark.

Uses the project's own ScreenerDataAccess for constituent bars and AkShare
for the CSI300 index benchmark, so the backtest exercises the same data
pipeline the live screener uses (no separate data vendor story).
"""

from __future__ import annotations

from typing import List

import pandas as pd

from tradingagents.screener.data_access import ScreenerDataAccess


def fetch_close_prices(
    data_access: ScreenerDataAccess,
    tickers: List[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Daily close prices for a list of tickers; columns = tickers, index = date.

    Tickers with no data in the window are skipped (never synthetic).
    """
    frames = []
    for ticker in tickers:
        df = data_access.fetch_hist(ticker, start_date, end_date)
        if df is None or getattr(df, "empty", True) or "date" not in df.columns:
            continue
        series = df[["date", "close"]].copy()
        series["date"] = pd.to_datetime(series["date"])
        series = series.dropna(subset=["close"]).set_index("date")["close"]
        series.name = ticker
        frames.append(series)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, axis=1).sort_index()
    out.index.name = "date"
    return out


def fetch_benchmark(
    start_date: str,
    end_date: str,
    symbol: str = "sh000300",
) -> pd.Series:
    """CSI300 index daily close as a benchmark (AkShare Sina index daily)."""
    import akshare as ak

    df = ak.stock_zh_index_daily(symbol=symbol)
    df["date"] = pd.to_datetime(df["date"])
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    df = df[(df["date"] >= start) & (df["date"] <= end)]
    out = df.set_index("date")["close"].astype(float).sort_index()
    out.name = "benchmark"
    return out
