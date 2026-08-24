"""Sina fetch paths (AkShare-backed) plus LHB (dragon-tiger) detail APIs.

Extracted from ScreenerDataAccess (data_access.py) during the Phase 4 split.
Guarded by `vendor_call` (task R3): failures logged, None contract kept.
"""

from __future__ import annotations

from tradingagents.screener.ticker_formats import normalize_ticker_for_sina
from tradingagents.screener.vendor_http import VendorHttp
from tradingagents.screener.vendors._guard import vendor_call

__all__ = [
    "fetch_spot",
    "fetch_hist",
    "fetch_concept",
    "fetch_index",
    "fetch_tick",
    "fetch_lhb_detail",
    "fetch_lhb_ggtj",
    "fetch_lhb_jgzz",
    "fetch_index_cons_weight",
    "fetch_index_cons_sina",
]


@vendor_call("sina.fetch_spot")
def fetch_spot(http: VendorHttp, market: str = "all"):
    import akshare as ak

    http.sleep_for_vendor("sina")
    with http.spoof():
        if market == "kcb":
            return ak.stock_zh_kcb_spot()
        elif market == "bj":
            return None  # Sina 不直接支持北交所
        else:
            return ak.stock_zh_a_spot()


@vendor_call("sina.fetch_hist")
def fetch_hist(http: VendorHttp, ticker: str, start_date: str, end_date: str, adjust: str = "qfq"):
    import akshare as ak

    sym = normalize_ticker_for_sina(ticker)
    sd = start_date.replace("-", "")
    ed = end_date.replace("-", "")
    http.sleep_for_vendor("sina")
    with http.spoof():
        return ak.stock_zh_a_daily(symbol=sym, start_date=sd, end_date=ed, adjust=adjust)


@vendor_call("sina.fetch_concept")
def fetch_concept(http: VendorHttp):
    """获取新浪概念板块 (需要正确的 symbol 参数).

    stock_classify_sina 需要中文参数，当前环境可能有编码问题；
    失败返回 None 让备源 THS 接管。
    """
    import akshare as ak

    http.sleep_for_vendor("sina")
    with http.spoof():
        df = ak.stock_classify_sina(symbol="概念分类")
    if df is not None and not df.empty:
        df = df.copy()
        df["source"] = "sina"
        return df
    return None


@vendor_call("sina.fetch_index")
def fetch_index(http: VendorHttp):
    import akshare as ak

    http.sleep_for_vendor("sina")
    with http.spoof():
        return ak.stock_zh_index_spot_sina()


@vendor_call("sina.fetch_tick")
def fetch_tick(http: VendorHttp, symbol: str):
    import akshare as ak

    sym = symbol.lower()
    http.sleep_for_vendor("sina")
    with http.spoof():
        return ak.stock_intraday_sina(symbol=sym)


@vendor_call("sina.fetch_lhb_detail")
def fetch_lhb_detail(http: VendorHttp, trade_date: str):
    """获取龙虎榜明细."""
    import akshare as ak

    target = trade_date.replace("-", "")
    http.sleep_for_vendor("sina")
    with http.spoof():
        return ak.stock_lhb_detail_daily_sina(date=target)


@vendor_call("sina.fetch_lhb_ggtj")
def fetch_lhb_ggtj(http: VendorHttp, recent_days: str = "5"):
    """获取龙虎榜个股上榜统计."""
    import akshare as ak

    http.sleep_for_vendor("sina")
    with http.spoof():
        return ak.stock_lhb_ggtj_sina(symbol=recent_days)


@vendor_call("sina.fetch_lhb_jgzz")
def fetch_lhb_jgzz(http: VendorHttp, recent_days: str = "5"):
    """获取龙虎榜机构席位追踪."""
    import akshare as ak

    http.sleep_for_vendor("sina")
    with http.spoof():
        return ak.stock_lhb_jgzz_sina(symbol=recent_days)


@vendor_call("sina.fetch_index_cons_weight")
def fetch_index_cons_weight(http: VendorHttp, index_code: str):
    """获取指数成分股列表（真实成分股，非指数代码本身）.

    使用 akshare 的 index_stock_cons_weight_csindex 接口。
    """
    import akshare as ak

    http.sleep_for_vendor("sina")
    with http.spoof():
        return ak.index_stock_cons_weight_csindex(symbol=index_code)


@vendor_call("sina.fetch_index_cons_sina")
def fetch_index_cons_sina(http: VendorHttp, index_code: str):
    """Fallback constituent list that does not depend on CSI Excel payloads."""
    import akshare as ak

    http.sleep_for_vendor("sina")
    with http.spoof():
        return ak.index_stock_cons_sina(symbol=index_code)
