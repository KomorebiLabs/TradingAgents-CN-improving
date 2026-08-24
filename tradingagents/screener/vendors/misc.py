"""Misc vendors: EastMoney fund-flow fallback and Baidu auxiliary data
(policy news, valuation, sentiment vote).

Extracted from ScreenerDataAccess (data_access.py) during the Phase 4 split.
Guarded by `vendor_call` (task R3): failures logged, None contract kept.
NOTE: `fetch_policy_news_baidu` keeps its per-day try/continue (one day's
failure must not abort the multi-day loop) — that is not a swallowed error.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from tradingagents.screener.vendor_http import VendorHttp
from tradingagents.screener.vendors._guard import vendor_call

__all__ = [
    "fetch_fund_flow_em",
    "fetch_concept_em",
    "fetch_lhb_detail_em",
    "fetch_lhb_stats_em",
    "fetch_lhb_institutional_em",
    "fetch_policy_news_baidu",
    "fetch_valuation_baidu",
    "fetch_vote_baidu",
    "fetch_popularity_em",
]


@vendor_call("misc.fetch_fund_flow_em")
def fetch_fund_flow_em(http: VendorHttp):
    """获取东方财富资金流向大盘数据（个股资金流向排名）.

    Current AkShare exposes this EastMoney ranking through
    ``stock_individual_fund_flow_rank``; the former ``*_em`` name was removed.
    """
    import akshare as ak

    http.sleep_for_vendor("eastmoney")
    with http.spoof():
        return ak.stock_individual_fund_flow_rank(indicator="今日")


@vendor_call("misc.fetch_concept_em")
def fetch_concept_em(http: VendorHttp):
    """Independent EastMoney fallback for Sina concept JSON drift."""
    import akshare as ak

    http.sleep_for_vendor("eastmoney")
    with http.spoof():
        frame = ak.stock_board_concept_name_em()
    if frame is None or frame.empty:
        return None
    frame = frame.copy()
    frame["source"] = "eastmoney"
    return frame


def _lhb_window(recent_days: str) -> str:
    try:
        days = int(recent_days)
    except (TypeError, ValueError):
        days = 5
    if days <= 1:
        return "近一日"
    if days <= 10:
        return "近一月"
    if days <= 90:
        return "近三月"
    return "近一年"


@vendor_call("misc.fetch_lhb_detail_em")
def fetch_lhb_detail_em(http: VendorHttp, trade_date: str):
    """EastMoney daily dragon-tiger detail fallback."""
    import akshare as ak

    target = trade_date.replace("-", "")
    http.sleep_for_vendor("eastmoney")
    with http.spoof():
        return ak.stock_lhb_detail_em(start_date=target, end_date=target)


@vendor_call("misc.fetch_lhb_stats_em")
def fetch_lhb_stats_em(http: VendorHttp, recent_days: str = "5"):
    """EastMoney stock-on-list statistics fallback."""
    import akshare as ak

    http.sleep_for_vendor("eastmoney")
    with http.spoof():
        return ak.stock_lhb_stock_statistic_em(symbol=_lhb_window(recent_days))


@vendor_call("misc.fetch_lhb_institutional_em")
def fetch_lhb_institutional_em(http: VendorHttp, recent_days: str = "5"):
    """EastMoney institutional-seat statistics fallback."""
    import akshare as ak

    http.sleep_for_vendor("eastmoney")
    with http.spoof():
        return ak.stock_lhb_jgstatistic_em(symbol=_lhb_window(recent_days))


@vendor_call("misc.fetch_policy_news_baidu")
def fetch_policy_news_baidu(http: VendorHttp, curr_date: str, look_back_days: int = 7, limit: int = 12):
    """获取政策/监管/流动性敏感宏观事件."""
    import pandas as pd
    import akshare as ak

    target_date = datetime.strptime(curr_date, "%Y-%m-%d")
    frames = []
    for offset in range(max(look_back_days, 1)):
        date_str = (target_date - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            http.sleep_for_vendor("baidu")
            with http.spoof():
                frames.append(ak.news_economic_baidu(date=date_str))
        except Exception:
            continue

    if not frames:
        return None

    df = pd.concat(frames, ignore_index=True)
    if "地区" in df.columns:
        region_mask = df["地区"].astype(str).str.contains("中国|China", case=False, na=False)
        df = df.loc[region_mask].copy()
    if "事件" in df.columns:
        keyword_mask = df["事件"].astype(str).str.contains(
            "政策|监管|央行|利率|LPR|MLF|科技|半导体|创新|制造|补贴|算力|人工智能|机器人|新能源",
            case=False,
            na=False,
        )
        df = df.loc[keyword_mask].copy()
    if df.empty:
        return None
    return df.head(limit).reset_index(drop=True)


@vendor_call("misc.fetch_valuation_baidu")
def fetch_valuation_baidu():
    """获取A股估值数据 (Baidu 辅助)."""
    import akshare as ak

    return ak.stock_zh_valuation_baidu()


@vendor_call("misc.fetch_vote_baidu")
def fetch_vote_baidu(symbol: str = "000001"):
    """获取股票人气投票数据."""
    import akshare as ak

    return ak.stock_zh_vote_baidu(symbol=symbol, indicator="股票")


@vendor_call("misc.fetch_popularity_em")
def fetch_popularity_em(symbol: str = "000001"):
    """Use an explicit EastMoney fund-flow heat proxy when Baidu drifts.

    The EastMoney app popularity endpoint is frequently proxy-blocked.  The
    bulk fund-flow ranking uses a separate, verified endpoint; its ``source``
    label makes clear that this is a degradation proxy, not a user vote.
    """
    import akshare as ak

    frame = ak.stock_individual_fund_flow_rank(indicator="今日")
    if frame is None or frame.empty:
        return None
    code_columns = [
        col for col in frame.columns
        if "代码" in str(col) or "code" in str(col).lower()
    ]
    if not code_columns:
        return None
    normalized = frame[code_columns[0]].astype(str).str.extract(
        r"(\d{6})", expand=False
    )
    matches = frame[normalized.eq(symbol.zfill(6))]
    if matches.empty:
        return None
    frame = matches.copy()
    frame = frame.copy()
    frame["source"] = "eastmoney_fund_flow_proxy"
    return frame
