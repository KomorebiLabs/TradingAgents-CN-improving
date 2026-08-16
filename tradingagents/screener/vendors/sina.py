"""Sina fetch paths (AkShare-backed) plus LHB (dragon-tiger) detail APIs.

Extracted from ScreenerDataAccess (data_access.py) during the Phase 4 split.
"""

from __future__ import annotations

from tradingagents.screener.ticker_formats import normalize_ticker_for_sina
from tradingagents.screener.vendor_http import VendorHttp

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
]


def fetch_spot(http: VendorHttp, market: str = "all"):
    import akshare as ak

    try:
        http.sleep_for_vendor("sina")
        with http.spoof():
            if market == "kcb":
                return ak.stock_zh_kcb_spot()
            elif market == "bj":
                return None  # Sina 不直接支持北交所
            else:
                return ak.stock_zh_a_spot()
    except Exception:
        return None


def fetch_hist(http: VendorHttp, ticker: str, start_date: str, end_date: str, adjust: str = "qfq"):
    import akshare as ak

    try:
        sym = normalize_ticker_for_sina(ticker)
        sd = start_date.replace("-", "")
        ed = end_date.replace("-", "")
        http.sleep_for_vendor("sina")
        with http.spoof():
            return ak.stock_zh_a_daily(symbol=sym, start_date=sd, end_date=ed, adjust=adjust)
    except Exception:
        return None


def fetch_concept(http: VendorHttp):
    """获取新浪概念板块 (需要正确的 symbol 参数).

    stock_classify_sina 需要中文参数，当前环境可能有编码问题；
    失败返回 None 让备源 THS 接管。
    """
    try:
        import akshare as ak

        try:
            http.sleep_for_vendor("sina")
            with http.spoof():
                df = ak.stock_classify_sina(symbol="概念分类")
        except Exception:
            return None
        if df is not None and not df.empty:
            df = df.copy()
            df["source"] = "sina"
            return df
        return None
    except Exception:
        return None


def fetch_index(http: VendorHttp):
    import akshare as ak

    try:
        http.sleep_for_vendor("sina")
        with http.spoof():
            return ak.stock_zh_index_spot_sina()
    except Exception:
        return None


def fetch_tick(http: VendorHttp, symbol: str):
    import akshare as ak

    try:
        sym = symbol.lower()
        http.sleep_for_vendor("sina")
        with http.spoof():
            return ak.stock_intraday_sina(symbol=sym)
    except Exception:
        return None


def fetch_lhb_detail(http: VendorHttp, trade_date: str):
    """获取龙虎榜明细."""
    try:
        import akshare as ak

        target = trade_date.replace("-", "")
        http.sleep_for_vendor("sina")
        with http.spoof():
            return ak.stock_lhb_detail_daily_sina(date=target)
    except Exception:
        return None


def fetch_lhb_ggtj(http: VendorHttp, recent_days: str = "5"):
    """获取龙虎榜个股上榜统计."""
    try:
        import akshare as ak

        http.sleep_for_vendor("sina")
        with http.spoof():
            return ak.stock_lhb_ggtj_sina(symbol=recent_days)
    except Exception:
        return None


def fetch_lhb_jgzz(http: VendorHttp, recent_days: str = "5"):
    """获取龙虎榜机构席位追踪."""
    try:
        import akshare as ak

        http.sleep_for_vendor("sina")
        with http.spoof():
            return ak.stock_lhb_jgzz_sina(symbol=recent_days)
    except Exception:
        return None


def fetch_index_cons_weight(http: VendorHttp, index_code: str):
    """获取指数成分股列表（真实成分股，非指数代码本身）.

    使用 akshare 的 index_stock_cons_weight_csindex 接口。
    """
    try:
        import akshare as ak

        http.sleep_for_vendor("sina")
        with http.spoof():
            return ak.index_stock_cons_weight_csindex(symbol=index_code)
    except Exception:
        return None
