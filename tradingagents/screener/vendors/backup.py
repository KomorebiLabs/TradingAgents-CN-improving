"""Backup last-resort vendors: Baostock historical bars and yfinance.

Extracted from ScreenerDataAccess (data_access.py) during the Phase 4 split.
"""

from __future__ import annotations

from tradingagents.screener.response_parsers import normalize_yfinance_hist_frame
from tradingagents.screener.ticker_formats import (
    normalize_ticker_for_baostock,
    normalize_ticker_for_yfinance,
)
from tradingagents.screener.vendor_http import VendorHttp

__all__ = ["fetch_hist_baostock", "fetch_hist_yfinance"]


def fetch_hist_baostock(http: VendorHttp, ticker: str, start_date: str, end_date: str, adjust: str = "qfq"):
    try:
        import baostock as bs

        sym = normalize_ticker_for_baostock(ticker)
        sd = start_date.replace("-", "")
        ed = end_date.replace("-", "")

        login_result = bs.login()
        if login_result is None or login_result.error_code != "0":
            return None
        try:
            adjflag_map = {"qfq": "3", "hfq": "2", "": "1"}
            adjflag = adjflag_map.get(adjust, "3")
            rs = bs.query_history_k_data_plus(
                sym,
                "date,open,high,low,close,volume",
                start_date=sd,
                end_date=ed,
                frequency="d",
                adjustflag=adjflag,
            )
            if rs is None or rs.error_code != "0":
                return None
            data = rs.get_data()
        finally:
            bs.logout()

        if data is not None and not data.empty and len(data) > 0:
            import pandas as pd

            data.columns = ["date", "open", "high", "low", "close", "volume"]
            for col in ["open", "high", "low", "close", "volume"]:
                data[col] = pd.to_numeric(data[col], errors="coerce")
            data = data.dropna(subset=["date"])
            data["amount"] = None
            data = data.reset_index(drop=True)
            return data
        return None
    except Exception:
        return None


def fetch_hist_yfinance(http: VendorHttp, requester, ticker: str, start_date: str, end_date: str):
    try:
        import yfinance as yf

        sym = normalize_ticker_for_yfinance(ticker)
        ticker_obj = yf.Ticker(sym)
        with http.spoof():
            result = requester.request(
                ticker_obj.history, start=start_date, end=end_date
            )
        return normalize_yfinance_hist_frame(result)
    except Exception:
        return None
