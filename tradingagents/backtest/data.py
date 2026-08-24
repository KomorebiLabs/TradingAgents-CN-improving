"""Backtest data access (R1): pool close prices + index benchmark.

Uses the project's own ScreenerDataAccess for constituent bars and AkShare
for the CSI300 index benchmark, so the backtest exercises the same data
pipeline the live screener uses (no separate data vendor story).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd

from tradingagents.screener.data_access import ScreenerDataAccess


@dataclass(frozen=True)
class MarketData:
    """Aligned point-in-time market fields used by the execution simulator."""

    close: pd.DataFrame
    volume: pd.DataFrame


def fetch_market_data(
    data_access: ScreenerDataAccess,
    tickers: List[str],
    start_date: str,
    end_date: str,
) -> MarketData:
    """Fetch aligned close and volume frames without synthesizing missing bars."""
    close_frames = []
    volume_frames = []
    for ticker in tickers:
        df = data_access.fetch_hist(ticker, start_date, end_date)
        if df is None or getattr(df, "empty", True) or "date" not in df.columns or "close" not in df.columns:
            continue
        normalized = df.copy()
        normalized["date"] = pd.to_datetime(normalized["date"])
        normalized = normalized.set_index("date").sort_index()
        close = pd.to_numeric(normalized["close"], errors="coerce").dropna()
        close.name = ticker
        close_frames.append(close)
        if "volume" in normalized.columns:
            volume = pd.to_numeric(normalized["volume"], errors="coerce")
            volume.name = ticker
            volume_frames.append(volume)

    close_frame = pd.concat(close_frames, axis=1).sort_index() if close_frames else pd.DataFrame()
    volume_frame = pd.concat(volume_frames, axis=1).sort_index() if volume_frames else pd.DataFrame(index=close_frame.index)
    close_frame.index.name = "date"
    volume_frame = volume_frame.reindex(close_frame.index)
    volume_frame.index.name = "date"
    return MarketData(close=close_frame, volume=volume_frame)


def fetch_close_prices(
    data_access: ScreenerDataAccess,
    tickers: List[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Daily close prices for a list of tickers; columns = tickers, index = date.

    Tickers with no data in the window are skipped (never synthetic).
    """
    return fetch_market_data(data_access, tickers, start_date, end_date).close


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
