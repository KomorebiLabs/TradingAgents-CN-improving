"""Tencent fetch paths: AkShare-backed Tencent + direct-HTTP Tencent (primary).

Extracted from ScreenerDataAccess (data_access.py) during the Phase 4 split.
Behavior preserved verbatim, including hardcoded probe sample symbols.
All functions guarded by `vendor_call` (task R3): failures are logged,
return value contract unchanged (None on failure).
"""

from __future__ import annotations

from tradingagents.screener.response_parsers import (
    parse_tencent_index_lines,
    parse_tencent_kline,
    parse_tencent_quote_lines,
)
from tradingagents.screener.ticker_formats import (
    normalize_date_for_tencent,
    normalize_ticker_for_tencent,
)
from tradingagents.screener.vendor_http import VendorHttp
from tradingagents.screener.vendors._guard import vendor_call

__all__ = [
    "fetch_hist_akshare",
    "fetch_spot_akshare",
    "fetch_tick_akshare",
    "fetch_index_akshare",
    "fetch_hist_direct",
    "fetch_spot_direct",
    "fetch_index_direct",
]


# -- AkShare-backed Tencent ----------------------------------------------

@vendor_call("tencent.fetch_hist_akshare")
def fetch_hist_akshare(http: VendorHttp, ticker: str, start_date: str, end_date: str, adjust: str = "qfq"):
    import akshare as ak

    code, exchange = normalize_ticker_for_tencent(ticker)
    tx_symbol = f"{exchange}{code}"
    sd = start_date.replace("-", "")
    ed = end_date.replace("-", "")
    adj_map = {"qfq": "qfq", "hfq": "hfq", "": ""}
    adj = adj_map.get(adjust, "qfq")
    http.sleep_for_vendor("tencent")
    with http.spoof():
        return ak.stock_zh_a_hist_tx(
            symbol=tx_symbol, start_date=sd, end_date=ed, adjust=adj
        )


@vendor_call("tencent.fetch_spot_akshare")
def fetch_spot_akshare(http: VendorHttp, market: str = "all"):
    # stock_zh_a_spot_tx 未在 __init__ 导出, 需直接导入
    from akshare.stock.stock_zh_a_tx import stock_zh_a_spot_tx

    http.sleep_for_vendor("tencent")
    with http.spoof():
        df = stock_zh_a_spot_tx()
    if df is not None and not df.empty:
        df = df.copy()
        df["source"] = "tencent"
    return df


@vendor_call("tencent.fetch_tick_akshare")
def fetch_tick_akshare(http: VendorHttp, symbol: str):
    import akshare as ak

    http.sleep_for_vendor("tencent")
    with http.spoof():
        return ak.stock_zh_a_tick_tx_js(symbol=symbol.lower())


@vendor_call("tencent.fetch_index_akshare")
def fetch_index_akshare(http: VendorHttp):
    import akshare as ak

    http.sleep_for_vendor("tencent")
    with http.spoof():
        return ak.stock_zh_index_daily_tx(symbol="sh000001", start_date="20260101", end_date="20260110")


# -- Direct HTTP Tencent (primary CN source) ------------------------------

@vendor_call("tencent.fetch_hist_direct")
def fetch_hist_direct(http: VendorHttp, ticker: str, start_date: str, end_date: str, adjust: str = "qfq"):
    """Direct HTTP call to the Tencent kline API.

    API: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={ticker},day,{start},{end},{count},{adjust}
    Note: the API only accepts YYYY-MM-DD dates; YYYYMMDD yields param error.
    """
    code, exchange = normalize_ticker_for_tencent(ticker)
    tx_symbol = f"{exchange}{code}"

    sd = normalize_date_for_tencent(start_date)
    ed = normalize_date_for_tencent(end_date)
    adj_map = {"qfq": "qfq", "hfq": "hfq", "": ""}
    adj = adj_map.get(adjust, "qfq")
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tx_symbol},day,{sd},{ed},500,{adj}"
    text = http.tencent_direct(url)
    if text is None:
        return None
    return parse_tencent_kline(text, tx_symbol, adj)


@vendor_call("tencent.fetch_spot_direct")
def fetch_spot_direct(http: VendorHttp, market: str = "all"):
    """Direct HTTP call to the Tencent realtime quote API.

    API: https://qt.gtimg.cn/q={symbol1},{symbol2},...
    """
    text = http.tencent_direct("https://qt.gtimg.cn/q=sh600519,sz000001")
    if text is None:
        return None
    return parse_tencent_quote_lines(text)


@vendor_call("tencent.fetch_index_direct")
def fetch_index_direct(http: VendorHttp):
    """Direct HTTP call to the Tencent index quote API (fewer fields than stocks)."""
    symbols = "s_sh000001,s_sz399001,s_sz399006,s_sh000688,s_sh000300,s_sh000905,s_sz399673"
    text = http.tencent_direct(f"https://qt.gtimg.cn/q={symbols}")
    if text is None:
        return None
    return parse_tencent_index_lines(text)
