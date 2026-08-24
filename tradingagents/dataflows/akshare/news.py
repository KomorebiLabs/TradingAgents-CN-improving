"""AkShare news vendors: stock news, global/policy news, sector news."""
from __future__ import annotations

import time
import threading
from datetime import datetime, timedelta
from io import StringIO
from typing import Iterable, Tuple

import pandas as pd

from tradingagents.dataflows.akshare._shared import _normalize_cn_symbol, _render_bullets, _require_akshare, _throttle_eastmoney, _throttle_news, _truncate_text

import logging
logger = logging.getLogger(__name__)

_STOCK_NEWS_CACHE = {}
_STOCK_NEWS_CACHE_TTL_SECONDS = 300.0
_STOCK_NEWS_CACHE_LOCK = threading.Lock()


def _get_stock_news_snapshot(ak, code: str) -> pd.DataFrame:
    """Fetch one EastMoney snapshot per symbol during the short cache window.

    The analyst commonly asks for several overlapping date ranges. Repeating
    the same EastMoney request for each range is both wasteful and likely to
    trigger HTTP 403 responses. Date filtering remains local and PIT-safe.
    """
    now = time.monotonic()
    with _STOCK_NEWS_CACHE_LOCK:
        cached = _STOCK_NEWS_CACHE.get(code)
        if cached and now - cached[0] < _STOCK_NEWS_CACHE_TTL_SECONDS:
            return cached[1].copy()

    _throttle_eastmoney.wait()
    snapshot = ak.stock_news_em(symbol=code)
    if snapshot is None:
        snapshot = pd.DataFrame()
    with _STOCK_NEWS_CACHE_LOCK:
        _STOCK_NEWS_CACHE[code] = (time.monotonic(), snapshot.copy())
    return snapshot


def _prepare_cn_stock_news(df: pd.DataFrame, start_date: str, end_date: str, limit: int = 8) -> pd.DataFrame:
    if df.empty:
        return df

    working = df.copy()
    if "发布时间" in working.columns:
        published = pd.to_datetime(working["发布时间"], errors="coerce")
        mask = (published >= pd.Timestamp(start_date)) & (
            published < pd.Timestamp(end_date) + pd.Timedelta(days=1)
        )
        working = working.loc[mask].copy()
        working["_published"] = published.loc[working.index]
        working = working.sort_values("_published", ascending=False)

    keep_columns = [col for col in ["发布时间", "新闻标题", "文章来源", "关键词", "新闻内容", "新闻链接"] if col in working.columns]
    if not keep_columns:
        return pd.DataFrame()

    prepared = working[keep_columns].head(limit).copy()
    if "新闻内容" in prepared.columns:
        prepared["新闻内容"] = prepared["新闻内容"].map(lambda value: _truncate_text(value, 160))
    if "新闻标题" in prepared.columns:
        prepared["新闻标题"] = prepared["新闻标题"].map(lambda value: _truncate_text(value, 80))
    return prepared


def _render_cn_stock_news(prepared: pd.DataFrame) -> str:
    entries = []
    for _, row in prepared.iterrows():
        published = row.get("发布时间", "N/A")
        title = row.get("新闻标题", "No title")
        source = row.get("文章来源", "Unknown")
        keyword = row.get("关键词", "")
        summary = row.get("新闻内容", "")
        link = row.get("新闻链接", "")

        lines = [
            f"Date: {published}",
            f"Title: {title}",
            f"Source: {source}",
        ]
        if keyword:
            lines.append(f"Keyword: {keyword}")
        if summary:
            lines.append(f"Summary: {summary}")
        if link:
            lines.append(f"Link: {link}")
        entries.append(_render_bullets(lines))

    return "\n\n".join(entries)


def _prepare_macro_events(df: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    if df.empty:
        return df

    working = df.copy()
    if "重要性" in working.columns:
        working["重要性"] = pd.to_numeric(working["重要性"], errors="coerce")
        working = working.sort_values(by="重要性", ascending=False, na_position="last")

    keep_columns = [col for col in ["日期", "时间", "地区", "事件", "公布", "预期", "前值", "重要性"] if col in working.columns]
    return working[keep_columns].head(limit).copy()


def _render_macro_events(prepared: pd.DataFrame) -> str:
    entries = []
    for _, row in prepared.iterrows():
        lines = [
            f"Date: {row.get('日期', 'N/A')} {row.get('时间', '')}".strip(),
            f"Region: {row.get('地区', 'N/A')}",
            f"Event: {_truncate_text(row.get('事件', ''), 120)}",
            f"Importance: {row.get('重要性', 'N/A')}",
            f"Actual: {row.get('公布', 'N/A')}",
            f"Forecast: {row.get('预期', 'N/A')}",
            f"Previous: {row.get('前值', 'N/A')}",
        ]
        entries.append(_render_bullets(lines))
    return "\n\n".join(entries)


def get_akshare_news(ticker: str, start_date: str, end_date: str) -> str:
    # Tool schemas call the first argument ``ticker``. Keep a local ``symbol``
    # name for the normalization/rendering logic below and accept positional
    # calls from existing dataflow code as before.
    symbol = ticker
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    df = _get_stock_news_snapshot(ak, code)
    if df.empty:
        return f"No CN stock news found for symbol '{symbol}' between {start_date} and {end_date}"

    prepared = _prepare_cn_stock_news(df, start_date, end_date, limit=8)
    if prepared.empty:
        return f"No CN stock news found for symbol '{symbol}' between {start_date} and {end_date}"

    return (
        f"# CN A-share stock news for {code}.{exchange.upper()} from {start_date} to {end_date}\n"
        "# Vendor: akshare.stock_news_em\n"
        "# Fields pruned for LLM consumption: publish time, title, source, keyword, truncated summary, link\n"
        f"# Total articles included: {len(prepared)}\n\n"
        + _render_cn_stock_news(prepared)
    )


def get_akshare_global_news(curr_date: str, look_back_days: int = 7, limit: int = 5) -> str:
    target_date = datetime.strptime(curr_date, "%Y-%m-%d")
    ak = _require_akshare()

    _throttle_news.wait()  # 节流：等待 2 秒

    frames = []
    for offset in range(max(look_back_days, 1)):
        date_str = (target_date - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            frames.append(ak.news_economic_baidu(date=date_str))
        except Exception as _exc_e3:
            logger.warning("[E3] news.py: previously-silent failure surfaced: %s", _exc_e3)
        continue

    if not frames:
        return f"No macro news found around {curr_date}"

    df = pd.concat(frames, ignore_index=True)
    prepared = _prepare_macro_events(df, limit=limit)
    return (
        f"# CN / global macro events up to {curr_date} (look_back_days={look_back_days})\n"
        "# Vendor: akshare.news_economic_baidu\n"
        "# Fields pruned for LLM consumption: date, time, region, event, actual, forecast, previous, importance\n"
        f"# Total events included: {len(prepared)}\n\n"
        + _render_macro_events(prepared)
    )


def get_akshare_cn_policy_news(curr_date: str, look_back_days: int = 7, limit: int = 6) -> str:
    target_date = datetime.strptime(curr_date, "%Y-%m-%d")
    ak = _require_akshare()

    _throttle_news.wait()  # 节流：等待 2 秒

    frames = []
    for offset in range(max(look_back_days, 1)):
        date_str = (target_date - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            frames.append(ak.news_economic_baidu(date=date_str))
        except Exception as _exc_e3:
            logger.warning("[E3] news.py: previously-silent failure surfaced: %s", _exc_e3)
        continue

    if not frames:
        return f"No CN policy-sensitive macro events found around {curr_date}"

    df = pd.concat(frames, ignore_index=True)
    if "地区" in df.columns:
        region_mask = df["地区"].astype(str).str.contains("中国|China", case=False, na=False)
        df = df.loc[region_mask].copy()
    if "事件" in df.columns:
        keyword_mask = df["事件"].astype(str).str.contains(
            "政策|监管|央行|利率|LPR|MLF|科技|半导体|创新|制造|补贴",
            case=False,
            na=False,
        )
        df = df.loc[keyword_mask].copy()

    prepared = _prepare_macro_events(df, limit=limit)
    if prepared.empty:
        return f"No CN policy-sensitive macro events found around {curr_date}"

    return (
        f"# CN policy and regulation-sensitive events up to {curr_date} (look_back_days={look_back_days})\n"
        "# Vendor: akshare.news_economic_baidu\n"
        "# Filters applied: China-region and policy / regulation / liquidity-sensitive event keywords\n"
        f"# Total events included: {len(prepared)}\n\n"
        + _render_macro_events(prepared)
    )


def _prepare_sector_news(
    df: pd.DataFrame,
    keywords: list,
    start_date: str,
    end_date: str,
    limit: int = 6
) -> pd.DataFrame:
    """Filter news by sector keywords and prepare for display."""
    if df.empty:
        return df

    working = df.copy()

    # Filter by publish time
    if "发布时间" in working.columns:
        published = pd.to_datetime(working["发布时间"], errors="coerce")
        mask = (published >= pd.Timestamp(start_date)) & (
            published < pd.Timestamp(end_date) + pd.Timedelta(days=1)
        )
        working = working.loc[mask].copy()

    # Filter by sector keywords
    if "新闻标题" in working.columns and keywords:
        keyword_pattern = "|".join(keywords)
        mask = working["新闻标题"].astype(str).str.contains(keyword_pattern, case=False, na=False)
        working = working.loc[mask].copy()

    # Sort by publish time descending
    if "发布时间" in working.columns:
        working = working.sort_values("发布时间", ascending=False, na_position="last")

    # Keep relevant columns
    keep_columns = [col for col in ["发布时间", "新闻标题", "文章来源", "关键词", "新闻内容", "新闻链接"] if col in working.columns]
    if not keep_columns:
        return pd.DataFrame()

    return working[keep_columns].head(limit).copy()


def _prepare_macro_sector_news(
    df: pd.DataFrame,
    keywords: list,
    limit: int = 6
) -> pd.DataFrame:
    """Filter macro events by sector keywords."""
    if df.empty:
        return df

    working = df.copy()

    # Filter by sector keywords in event column
    if "事件" in working.columns and keywords:
        keyword_pattern = "|".join(keywords)
        mask = working["事件"].astype(str).str.contains(keyword_pattern, case=False, na=False)
        working = working.loc[mask].copy()

    # Sort by importance
    if "重要性" in working.columns:
        working["重要性"] = pd.to_numeric(working["重要性"], errors="coerce")
        working = working.sort_values(by="重要性", ascending=False, na_position="last")

    keep_columns = [col for col in ["日期", "时间", "地区", "事件", "公布", "预期", "前值", "重要性"] if col in working.columns]
    return working[keep_columns].head(limit).copy()


def get_akshare_cn_tech_sector_news(
    symbol: str,
    curr_date: str,
    look_back_days: int = 7,
    limit: int = 6
) -> str:
    """Get technology/semiconductor sector news for a specific stock."""
    target_date = datetime.strptime(curr_date, "%Y-%m-%d")
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    # Get stock-specific news
    stock_news = []
    try:
        stock_df = ak.stock_news_em(symbol=code)
        if not stock_df.empty:
            stock_news.append(stock_df)
    except Exception as _exc_e3:
        logger.warning("[E3] news.py: previously-silent failure surfaced: %s", _exc_e3)
    pass

    # Get macro tech news from economic calendar
    macro_news = []
    for offset in range(max(look_back_days, 1)):
        date_str = (target_date - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            macro_df = ak.news_economic_baidu(date=date_str)
            if not macro_df.empty:
                macro_news.append(macro_df)
        except Exception as _exc_e3:
            logger.warning("[E3] news.py: previously-silent failure surfaced: %s", _exc_e3)
        continue

    # Prepare stock news with tech keywords
    tech_keywords = [
        "半导体", "芯片", "集成电路", "AI", "人工智能", "云计算", "大数据",
        "软件", "5G", "通信", "电子", "科技", "算力", "服务器", "国产替代"
    ]

    start_date = (target_date - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
    end_date = curr_date

    results = []

    # Process stock news
    if stock_news:
        stock_df = pd.concat(stock_news, ignore_index=True)
        prepared = _prepare_sector_news(stock_df, tech_keywords, start_date, end_date, limit)
        if not prepared.empty:
            results.append(("# Stock-specific technology news\n" + _render_cn_stock_news(prepared)))

    # Process macro news
    if macro_news:
        macro_df = pd.concat(macro_news, ignore_index=True)
        # Filter for China + tech keywords
        if "地区" in macro_df.columns:
            macro_df = macro_df[macro_df["地区"].astype(str).str.contains("中国|China", case=False, na=False)]
        prepared = _prepare_macro_sector_news(macro_df, tech_keywords, limit)
        if not prepared.empty:
            results.append(("# Macro technology policy news\n" + _render_macro_events(prepared)))

    if not results:
        return f"No technology sector news found for {code}.{exchange.upper()} around {curr_date}"

    header = (
        f"# CN technology/semiconductor sector news for {code}.{exchange.upper()} around {curr_date}\n"
        "# Vendor: akshare.stock_news_em + akshare.news_economic_baidu\n"
        f"# Keywords: {', '.join(tech_keywords[:5])}...\n"
        f"# Look-back days: {look_back_days}\n\n"
    )
    return header + "\n\n".join(results)


def get_akshare_cn_new_energy_news(
    symbol: str,
    curr_date: str,
    look_back_days: int = 7,
    limit: int = 6
) -> str:
    """Get new energy sector news for a specific stock."""
    target_date = datetime.strptime(curr_date, "%Y-%m-%d")
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    # Get macro new energy news
    frames = []
    for offset in range(max(look_back_days, 1)):
        date_str = (target_date - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            frames.append(ak.news_economic_baidu(date=date_str))
        except Exception as _exc_e3:
            logger.warning("[E3] news.py: previously-silent failure surfaced: %s", _exc_e3)
        continue

    if not frames:
        return f"No new energy sector news found around {curr_date}"

    df = pd.concat(frames, ignore_index=True)

    # Filter for China
    if "地区" in df.columns:
        df = df[df["地区"].astype(str).str.contains("中国|China", case=False, na=False)]

    # Filter for new energy keywords
    new_energy_keywords = [
        "新能源", "锂电池", "锂电", "光伏", "储能", "电动汽车", "电动车",
        "动力电池", "风电", "氢能", "充电桩", "碳中和", "可再生能源",
        "电池材料", "固态电池", "汽车电动化"
    ]

    prepared = _prepare_macro_sector_news(df, new_energy_keywords, limit)

    if prepared.empty:
        return f"No new energy sector news found around {curr_date}"

    header = (
        f"# CN new energy sector news for {code}.{exchange.upper()} around {curr_date}\n"
        "# Vendor: akshare.news_economic_baidu\n"
        f"# Keywords: {', '.join(new_energy_keywords[:5])}...\n"
        f"# Look-back days: {look_back_days}\n\n"
    )
    return header + _render_macro_events(prepared)


def get_akshare_cn_pharma_news(
    symbol: str,
    curr_date: str,
    look_back_days: int = 7,
    limit: int = 6
) -> str:
    """Get pharmaceutical/healthcare sector news for a specific stock."""
    target_date = datetime.strptime(curr_date, "%Y-%m-%d")
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    # Get macro pharma news
    frames = []
    for offset in range(max(look_back_days, 1)):
        date_str = (target_date - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            frames.append(ak.news_economic_baidu(date=date_str))
        except Exception as _exc_e3:
            logger.warning("[E3] news.py: previously-silent failure surfaced: %s", _exc_e3)
        continue

    if not frames:
        return f"No pharmaceutical sector news found around {curr_date}"

    df = pd.concat(frames, ignore_index=True)

    # Filter for China
    if "地区" in df.columns:
        df = df[df["地区"].astype(str).str.contains("中国|China", case=False, na=False)]

    # Filter for pharma keywords
    pharma_keywords = [
        "医药", "创新药", "医疗器械", "中药", "生物医药", "疫苗", "抗体",
        "化学制药", "原料药", "CXO", "CRO", "CDMO", "医疗", "医保",
        "仿制药", "新药审批", "临床试验"
    ]

    prepared = _prepare_macro_sector_news(df, pharma_keywords, limit)

    if prepared.empty:
        return f"No pharmaceutical sector news found around {curr_date}"

    header = (
        f"# CN pharmaceutical/healthcare sector news for {code}.{exchange.upper()} around {curr_date}\n"
        "# Vendor: akshare.news_economic_baidu\n"
        f"# Keywords: {', '.join(pharma_keywords[:5])}...\n"
        f"# Look-back days: {look_back_days}\n\n"
    )
    return header + _render_macro_events(prepared)


def get_akshare_cn_real_estate_news(
    curr_date: str,
    look_back_days: int = 7,
    limit: int = 6
) -> str:
    """Get real estate sector news (market-wide)."""
    target_date = datetime.strptime(curr_date, "%Y-%m-%d")
    ak = _require_akshare()

    # Get macro real estate news
    frames = []
    for offset in range(max(look_back_days, 1)):
        date_str = (target_date - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            frames.append(ak.news_economic_baidu(date=date_str))
        except Exception as _exc_e3:
            logger.warning("[E3] news.py: previously-silent failure surfaced: %s", _exc_e3)
        continue

    if not frames:
        return f"No real estate sector news found around {curr_date}"

    df = pd.concat(frames, ignore_index=True)

    # Filter for China
    if "地区" in df.columns:
        df = df[df["地区"].astype(str).str.contains("中国|China", case=False, na=False)]

    # Filter for real estate keywords
    real_estate_keywords = [
        "房地产", "地产", "购房", "房贷", "土地拍卖", "限购", "限售",
        "调控", "保障房", "长租公寓", "物业", "商业地产", "城镇化",
        "万科", "碧桂园", "恒大", "房价", "楼盘"
    ]

    prepared = _prepare_macro_sector_news(df, real_estate_keywords, limit)

    if prepared.empty:
        return f"No real estate sector news found around {curr_date}"

    header = (
        f"# CN real estate sector news around {curr_date}\n"
        "# Vendor: akshare.news_economic_baidu\n"
        f"# Keywords: {', '.join(real_estate_keywords[:5])}...\n"
        f"# Look-back days: {look_back_days}\n\n"
    )
    return header + _render_macro_events(prepared)


def get_akshare_cn_fintech_news(
    symbol: str,
    curr_date: str,
    look_back_days: int = 7,
    limit: int = 6
) -> str:
    """Get financial technology sector news for a specific stock."""
    target_date = datetime.strptime(curr_date, "%Y-%m-%d")
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    # Get macro fintech news
    frames = []
    for offset in range(max(look_back_days, 1)):
        date_str = (target_date - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            frames.append(ak.news_economic_baidu(date=date_str))
        except Exception as _exc_e3:
            logger.warning("[E3] news.py: previously-silent failure surfaced: %s", _exc_e3)
        continue

    if not frames:
        return f"No financial technology sector news found around {curr_date}"

    df = pd.concat(frames, ignore_index=True)

    # Filter for China
    if "地区" in df.columns:
        df = df[df["地区"].astype(str).str.contains("中国|China", case=False, na=False)]

    # Filter for fintech keywords
    fintech_keywords = [
        "数字货币", "区块链", "第三方支付", "移动支付", "金融科技",
        "互联网金融", "云计算金融", "大数据金融", "人工智能金融",
        "智能投顾", "央行数字货币", "CBDC", "数字人民币", "支付牌照"
    ]

    prepared = _prepare_macro_sector_news(df, fintech_keywords, limit)

    if prepared.empty:
        return f"No financial technology sector news found around {curr_date}"

    header = (
        f"# CN financial technology sector news for {code}.{exchange.upper()} around {curr_date}\n"
        "# Vendor: akshare.news_economic_baidu\n"
        f"# Keywords: {', '.join(fintech_keywords[:5])}...\n"
        f"# Look-back days: {look_back_days}\n\n"
    )
    return header + _render_macro_events(prepared)
