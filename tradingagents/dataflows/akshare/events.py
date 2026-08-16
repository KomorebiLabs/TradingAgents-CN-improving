"""AkShare event vendors: earnings calendar, IPO, M&A, pledge, limit-up."""
from __future__ import annotations

import time
import threading
from datetime import datetime, timedelta
from io import StringIO
from typing import Iterable, Tuple

import pandas as pd

from tradingagents.dataflows.akshare._shared import _normalize_cn_symbol, _render_bullets, _require_akshare, _throttle_eastmoney
from tradingagents.dataflows.akshare.news import (
    _prepare_cn_stock_news,
    _render_cn_stock_news,
)


def _render_calendar_entry(title: str, date: str, details: str = "") -> str:
    """Render a calendar entry for display."""
    lines = [
        f"Date: {date}",
        f"Event: {title}",
    ]
    if details:
        lines.append(f"Details: {details}")
    return _render_bullets(lines)


def _render_ipo_entry(company: str, code: str, date: str, details: str = "") -> str:
    """Render an IPO entry for display."""
    lines = [
        f"Company: {company}",
        f"Code: {code}",
        f"Listing Date: {date}",
    ]
    if details:
        lines.append(f"Details: {details}")
    return _render_bullets(lines)


def get_akshare_cn_earnings_calendar(
    look_forward_days: int = 30,
    market: str = "all"
) -> str:
    """Get A-share earnings calendar."""
    ak = _require_akshare()

    try:
        # Get earnings forecast calendar
        df = ak.stock_zh_a_disclosure_calendar(start_date=datetime.now().strftime("%Y%m%d"))
        if df.empty:
            return "No upcoming earnings calendar data available"

        # Filter by market if specified
        if market != "all":
            market_codes = {
                "main": ("0", "1", "6"),      # Main board
                "chinext": ("3",),             # ChiNext
                "star": ("8",),                # STAR Market
                "bse": ("4",),                 # BSE
            }
            if market in market_codes:
                prefixes = market_codes[market]
                df = df[df["股票代码"].astype(str).str[0].isin(prefixes)]

        # Filter future dates only
        future_df = df.head(look_forward_days * 5)  # Approximate filtering

        entries = []
        for _, row in future_df.head(30).iterrows():
            code = row.get("股票代码", "N/A")
            name = row.get("股票简称", code)
            date = row.get("财报发布日", row.get("预约日期", "N/A"))
            entry_type = row.get("公告类型", "")

            lines = [
                f"Code: {code}",
                f"Name: {name}",
                f"Date: {date}",
                f"Type: {entry_type}",
            ]
            entries.append(_render_bullets(lines))

        if not entries:
            return "No upcoming earnings calendar data available"

        return (
            f"# China A-share Earnings Calendar\n"
            f"# Look-forward: {look_forward_days} days\n"
            f"# Market: {market}\n"
            "# Vendor: akshare.stock_zh_a_disclosure_calendar\n\n"
            + "\n\n".join(entries)
        )

    except Exception as e:
        return f"Earnings calendar data unavailable: {str(e)}"


def get_akshare_cn_ipo_data(
    status: str = "upcoming",
    limit: int = 20
) -> str:
    """Get A-share IPO data."""
    ak = _require_akshare()

    try:
        # Get IPO calendar
        df = ak.stock_ipo_summary_cn()
        if df.empty:
            return "No IPO data available"

        # Filter by status
        if status == "upcoming":
            # Filter for upcoming IPOs
            df = df[df["状态"].astype(str).str.contains("待上市|申购", na=False)]
        elif status == "recently_listed":
            # Filter for recently listed
            df = df[df["状态"].astype(str).str.contains("上市", na=False)]

        entries = []
        for _, row in df.head(limit).iterrows():
            code = row.get("股票代码", "N/A")
            name = row.get("股票名称", "N/A")
            date = row.get("上市日期", row.get("申购日期", "N/A"))
            price = row.get("发行价格", "N/A")
            pe = row.get("市盈率", "N/A")

            lines = [
                f"Code: {code}",
                f"Name: {name}",
                f"Date: {date}",
                f"Issue Price: {price}",
                f"PE Ratio: {pe}",
            ]
            entries.append(_render_bullets(lines))

        if not entries:
            return "No IPO data available for the specified status"

        return (
            f"# China A-share IPO Data\n"
            f"# Status: {status}\n"
            "# Vendor: akshare.stock_ipo_summary_cn\n\n"
            + "\n\n".join(entries)
        )

    except Exception as e:
        return f"IPO data unavailable: {str(e)}"


def get_akshare_cn_m_a_news(
    ticker: str,
    look_back_days: int = 90,
    limit: int = 10
) -> str:
    """Get M&A news for a specific company."""
    target_date = datetime.now()
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(ticker)

    results = []

    # Search news for M&A keywords
    for offset in range(max(look_back_days // 7, 1)):  # Check weekly
        date_str = (target_date - timedelta(days=offset * 7)).strftime("%Y%m%d")
        try:
            news_df = ak.stock_news_em(symbol=code)
            if not news_df.empty:
                # Filter for M&A keywords
                keyword_pattern = "|".join([
                    "并购", "收购", "重组", "资产", "战略", "投资",
                    "收购", "定向", "增发", "发行", "募资"
                ])
                mask = news_df["新闻标题"].astype(str).str.contains(keyword_pattern, na=False)
                results.append(news_df[mask])
        except Exception:
            continue

    if not results:
        # Fallback: try stock concept news
        try:
            concept_df = ak.stock_board_industry_cons_em(symbol=code)
            if not concept_df.empty:
                return (
                    f"# {code}.{exchange.upper()} Related Industry News\n"
                    "# (M&A specific news not found, showing industry context)\n\n"
                    + _render_cn_stock_news(concept_df.head(limit))
                )
        except Exception:
            pass

        return f"No M&A related news found for {code}.{exchange.upper()} in the past {look_back_days} days"

    combined_df = pd.concat(results, ignore_index=True).drop_duplicates()
    prepared = _prepare_cn_stock_news(
        combined_df,
        (target_date - timedelta(days=look_back_days)).strftime("%Y-%m-%d"),
        target_date.strftime("%Y-%m-%d"),
        limit
    )

    if prepared.empty:
        return f"No M&A related news found for {code}.{exchange.upper()} in the past {look_back_days} days"

    return (
        f"# {code}.{exchange.upper()} M&A News\n"
        f"# Look-back: {look_back_days} days\n"
        "# Keywords: 并购, 收购, 重组, 资产, 战略, 投资\n"
        "# Vendor: akshare.stock_news_em\n\n"
        + _render_cn_stock_news(prepared)
    )


def get_akshare_cn_stock_pledge(
    ticker: str,
    look_back_days: int = 30
) -> str:
    """Get stock pledge information for a company."""
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(ticker)

    try:
        # Try to get pledge data
        df = ak.stock_share_pledge_exclusive_down_em(symbol=code)
        if df.empty:
            return f"No stock pledge data available for {code}.{exchange.upper()}"

        # Limit to recent entries
        prepared = df.head(20).copy()

        entries = []
        for _, row in prepared.iterrows():
            pledge_ratio = row.get("质押比例", "N/A")
            pledge_type = row.get("质押类型", "N/A")
            start_date = row.get("初始交易日", "N/A")
            deadline = row.get("购回交易日", "N/A")

            lines = [
                f"Pledge Ratio: {pledge_ratio}",
                f"Type: {pledge_type}",
                f"Start Date: {start_date}",
                f"Deadline: {deadline}",
            ]
            entries.append(_render_bullets(lines))

        return (
            f"# {code}.{exchange.upper()} Stock Pledge Information\n"
            f"# Look-back: {look_back_days} days\n"
            "# Vendor: akshare.stock_share_pledge_exclusive_down_em\n\n"
            + "\n\n".join(entries)
        )

    except Exception as e:
        return f"Stock pledge data unavailable for {code}.{exchange.upper()}: {str(e)}"


def get_akshare_cn_limit_up_stocks(
    trade_date: str,
    limit: int = 30
) -> str:
    """Get limit-up/limit-down stocks for a specific date."""
    ak = _require_akshare()

    _throttle_eastmoney.wait()  # 节流：等待 1.5 秒

    try:
        date_str = trade_date.replace("-", "")

        # Get limit-up stocks
        limit_up_df = ak.stock_zt_pool_previous_em(date=date_str)
        if limit_up_df.empty:
            return f"No limit-up data available for {trade_date}"

        entries = []
        for _, row in limit_up_df.head(limit).iterrows():
            code = row.get("代码", "N/A")
            name = row.get("名称", "N/A")
            close_price = row.get("最新价", "N/A")  # 实际列名是"最新价"
            change_pct = row.get("涨跌幅", "N/A")
            reason = row.get("所属行业", "N/A")  # 实际列名是"所属行业"

            lines = [
                f"Code: {code}",
                f"Name: {name}",
                f"Close: {close_price}",
                f"Change%: {change_pct}",
                f"Reason: {reason}",
            ]
            entries.append(_render_bullets(lines))

        return (
            f"# China A-share Limit-Up Stocks ({trade_date})\n"
            f"# Total: {len(limit_up_df)} stocks hit limit-up\n"
            f"# Showing top {limit}\n"
            "# Vendor: akshare.stock_zt_pool_previous\n\n"
            + "\n\n".join(entries)
        )

    except Exception as e:
        return f"Limit-up data unavailable for {trade_date}: {str(e)}"
