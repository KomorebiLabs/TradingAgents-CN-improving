"""Misc vendors: EastMoney fund-flow fallback and Baidu auxiliary data
(policy news, valuation, sentiment vote).

Extracted from ScreenerDataAccess (data_access.py) during the Phase 4 split.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from tradingagents.screener.vendor_http import VendorHttp

__all__ = [
    "fetch_fund_flow_em",
    "fetch_policy_news_baidu",
    "fetch_valuation_baidu",
    "fetch_vote_baidu",
]


def fetch_fund_flow_em(http: VendorHttp):
    """获取东方财富资金流向大盘数据（个股资金流向排名）.

    H4 FIX: 当 THS 主源失败时使用 AkShare 的 stock_individual_fund_flow_em，
    比 Baostock 更可靠且数据更丰富。
    """
    import akshare as ak

    try:
        http.sleep_for_vendor("sina")
        with http.spoof():
            return ak.stock_individual_fund_flow_em(symbol="即时")
    except Exception:
        return None


def fetch_policy_news_baidu(http: VendorHttp, curr_date: str, look_back_days: int = 7, limit: int = 12):
    """获取政策/监管/流动性敏感宏观事件."""
    try:
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
    except Exception:
        return None


def fetch_valuation_baidu():
    """获取A股估值数据 (Baidu 辅助)."""
    import akshare as ak

    try:
        return ak.stock_zh_valuation_baidu()
    except Exception:
        return None


def fetch_vote_baidu(symbol: str = "000001"):
    """获取股票人气投票数据."""
    import akshare as ak

    try:
        return ak.stock_zh_vote_baidu(symbol=symbol)
    except Exception:
        return None
