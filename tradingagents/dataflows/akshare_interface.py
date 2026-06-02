from __future__ import annotations

import time
import threading
from datetime import datetime, timedelta
from io import StringIO
from typing import Iterable, Tuple

import pandas as pd


# ============================================================
# 请求节流机制：避免被当作爬虫封禁
# ============================================================
class RequestThrottle:
    """请求节流器，控制 API 请求频率"""

    def __init__(self, min_interval: float = 1.0):
        """
        Args:
            min_interval: 最小请求间隔（秒），默认 1 秒
        """
        self.min_interval = min_interval
        self._last_request_time = 0.0
        self._lock = threading.Lock()

    def wait(self):
        """等待直到可以发送下一个请求"""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            self._last_request_time = time.time()

    def reset(self):
        """重置节流器"""
        with self._lock:
            self._last_request_time = 0.0


# 全局节流器：不同数据源使用不同的节流器
_throttle_tencent = RequestThrottle(min_interval=1.0)   # 腾讯财经：1秒间隔
_throttle_eastmoney = RequestThrottle(min_interval=1.5)  # 东方财富：1.5秒间隔
_throttle_news = RequestThrottle(min_interval=2.0)        # 新闻数据：2秒间隔


def _require_akshare():
    try:
        import akshare as ak
    except ImportError as exc:
        raise ImportError(
            "AkShare is required for vendor 'akshare'. Install it with `pip install akshare`."
        ) from exc
    return ak


def _normalize_cn_symbol(symbol: str) -> Tuple[str, str]:
    value = symbol.strip().upper()
    if "." in value:
        code, exchange = value.split(".", 1)
        exchange = exchange.upper()
        if exchange in {"SZ", "XSHE"}:
            return code, "sz"
        if exchange in {"SH", "XSHG"}:
            return code, "sh"
        if exchange in {"BJ", "BSE"}:
            return code, "bj"
    if value.startswith(("6", "9")):
        return value, "sh"
    if value.startswith(("0", "2", "3")):
        return value, "sz"
    if value.startswith(("4", "8")):
        return value, "bj"
    raise ValueError(
        f"Unsupported CN ticker format '{symbol}'. Use A-share symbols like 600519.SH or 000001.SZ."
    )


def _prune_cn_daily_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    rename_map = {
        "日期": "Date",
        "开盘": "Open",
        "收盘": "Close",
        "最高": "High",
        "最低": "Low",
        "成交量": "Volume",
        "成交额": "Turnover",
        "振幅": "AmplitudePct",
        "涨跌幅": "ChangePct",
        "涨跌额": "ChangeAmount",
        "换手率": "TurnoverRatePct",
    }

    available = [col for col in rename_map if col in df.columns]
    pruned = df[available].rename(columns={col: rename_map[col] for col in available}).copy()
    if "Date" in pruned.columns:
        pruned["Date"] = pd.to_datetime(pruned["Date"]).dt.strftime("%Y-%m-%d")

    numeric_columns = [
        "Open",
        "Close",
        "High",
        "Low",
        "Turnover",
        "AmplitudePct",
        "ChangePct",
        "ChangeAmount",
        "TurnoverRatePct",
    ]
    for column in numeric_columns:
        if column in pruned.columns:
            pruned[column] = pd.to_numeric(pruned[column], errors="coerce").round(2)
    if "Volume" in pruned.columns:
        pruned["Volume"] = pd.to_numeric(pruned["Volume"], errors="coerce")

    return pruned


def _truncate_text(value: object, limit: int = 180) -> str:
    text = "" if value is None else str(value).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _safe_to_datetime(value: object) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed


def _coerce_number(value: object, digits: int = 2) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return "N/A"
    return str(round(float(numeric), digits))


def _normalize_akshare_info_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "item": "Item",
        "value": "Value",
        "项目": "Item",
        "最新": "Value",
    }
    available = {column: rename_map[column] for column in df.columns if column in rename_map}
    normalized = df.rename(columns=available).copy()
    if "Item" not in normalized.columns or "Value" not in normalized.columns:
        raise ValueError("AkShare fundamentals response does not contain recognizable item/value columns.")
    return normalized[["Item", "Value"]]


def _extract_fundamentals_snapshot(df: pd.DataFrame) -> dict:
    normalized = _normalize_akshare_info_columns(df)
    value_map = {
        str(row["Item"]).strip(): row["Value"]
        for _, row in normalized.iterrows()
        if str(row["Item"]).strip()
    }
    return {
        "code": value_map.get("股票代码", ""),
        "name": value_map.get("股票简称", ""),
        "industry": value_map.get("行业", value_map.get("所属行业", "N/A")),
        "listing_date": value_map.get("上市时间", "N/A"),
        "latest_price": value_map.get("最新", "N/A"),
        "total_market_cap": value_map.get("总市值", "N/A"),
        "float_market_cap": value_map.get("流通市值", "N/A"),
        "total_shares": value_map.get("总股本", "N/A"),
        "float_shares": value_map.get("流通股", "N/A"),
    }


def _render_bullets(lines: Iterable[str]) -> str:
    return "\n".join(f"- {line}" for line in lines if line)


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


def _prepare_fund_flow(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    if df.empty:
        return df

    keep_columns = [
        col
        for col in [
            "日期",
            "收盘价",
            "涨跌幅",
            "主力净流入-净额",
            "主力净流入-净占比",
            "超大单净流入-净额",
            "超大单净流入-净占比",
            "大单净流入-净额",
            "大单净流入-净占比",
        ]
        if col in df.columns
    ]
    prepared = df[keep_columns].head(limit).copy()
    return prepared


def _render_fund_flow(prepared: pd.DataFrame) -> str:
    entries = []
    for _, row in prepared.iterrows():
        lines = [
            f"Date: {row.get('日期', 'N/A')}",
            f"Close: {row.get('收盘价', 'N/A')}",
            f"ChangePct: {row.get('涨跌幅', 'N/A')}",
            f"MainForceNetInflow: {row.get('主力净流入-净额', 'N/A')}",
            f"MainForceNetInflowPct: {row.get('主力净流入-净占比', 'N/A')}",
            f"ExtraLargeOrderNetInflow: {row.get('超大单净流入-净额', 'N/A')}",
            f"ExtraLargeOrderNetInflowPct: {row.get('超大单净流入-净占比', 'N/A')}",
            f"LargeOrderNetInflow: {row.get('大单净流入-净额', 'N/A')}",
            f"LargeOrderNetInflowPct: {row.get('大单净流入-净占比', 'N/A')}",
        ]
        entries.append(_render_bullets(lines))
    return "\n\n".join(entries)


def get_akshare_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    # 腾讯财经接口（stock_zh_a_hist_tx）更稳定，不容易被封
    # 格式：exchange + code，如 'sz000001', 'sh600519', 'bj430685'
    tx_symbol = f"{exchange}{code}"

    df = None
    used_vendor = "unknown"

    # 方案1: 腾讯财经接口
    try:
        _throttle_tencent.wait()  # 节流：等待 1 秒
        df = ak.stock_zh_a_hist_tx(
            symbol=tx_symbol,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
        used_vendor = "Tencent Finance (stock_zh_a_hist_tx)"
    except Exception as e:
        em_error = str(e)
        # 检查是否是东方财富连接错误，如果是则不使用东方财富
        if "push2his.eastmoney.com" in em_error or "RemoteDisconnected" in str(type(e).__name__):
            em_error = None

    # 方案2: 东方财富接口（仅在腾讯失败且不是连接问题时使用）
    if df is None or (df is not None and df.empty):
        try:
            _throttle_eastmoney.wait()  # 节流：等待 1.5 秒
            start_compact = start_date.replace("-", "")
            end_compact = end_date.replace("-", "")

            # 科创板(688)和北交所(4,8开头)需要特殊处理
            if code.startswith(("688")):
                # 科创板使用 sh 前缀
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_compact,
                    end_date=end_compact,
                    adjust="qfq",
                )
            elif code.startswith(("4", "8")):
                # 北交所使用 bj 前缀
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_compact,
                    end_date=end_compact,
                    adjust="qfq",
                )
            else:
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_compact,
                    end_date=end_compact,
                    adjust="qfq",
                )
            used_vendor = "EastMoney (stock_zh_a_hist)"
        except Exception:
            df = None

    if df is None or df.empty:
        return f"No CN A-share data found for symbol '{symbol}' between {start_date} and {end_date}"

    # 腾讯接口返回的列名不同，需要重命名
    if 'date' in df.columns:
        df = df.rename(columns={
            'date': '日期',
            'open': '开盘',
            'close': '收盘',
            'high': '最高',
            'low': '最低',
            'amount': '成交量',
        })

    pruned = _prune_cn_daily_dataframe(df)

    if pruned.empty:
        return f"No CN A-share data found for symbol '{symbol}' between {start_date} and {end_date}"

    csv_buffer = StringIO()
    pruned.to_csv(csv_buffer, index=False)

    header = (
        f"# CN A-share stock data for {code}.{exchange.upper()} from {start_date} to {end_date}\n"
        f"# Vendor: akshare.{used_vendor}\n"
        f"# Fields pruned for LLM consumption: {', '.join(pruned.columns)}\n"
        f"# Total records: {len(pruned)}\n"
        f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    return header + csv_buffer.getvalue()


def get_akshare_fundamentals(symbol: str, curr_date: str) -> str:
    datetime.strptime(curr_date, "%Y-%m-%d")
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    _throttle_eastmoney.wait()  # 节流：等待 1.5 秒
    info_df = ak.stock_individual_info_em(symbol=code)
    snapshot = _extract_fundamentals_snapshot(info_df)

    snapshot_lines = [
        f"Code: {snapshot['code'] or code}",
        f"Name: {snapshot['name'] or 'N/A'}",
        f"Industry: {snapshot['industry']}",
        f"ListingDate: {snapshot['listing_date']}",
        f"LatestPrice: {snapshot['latest_price']}",
        f"TotalMarketCap: {snapshot['total_market_cap']}",
        f"FloatMarketCap: {snapshot['float_market_cap']}",
        f"TotalShares: {snapshot['total_shares']}",
        f"FloatShares: {snapshot['float_shares']}",
    ]

    lines = [
        f"# CN A-share fundamentals snapshot for {code}.{exchange.upper()} as of {curr_date}",
        "# Vendor: akshare.stock_individual_info_em",
        "# Fields pruned for LLM consumption: code, name, industry, listing date, latest price, total/float market cap, total/float shares",
        "",
        _render_bullets(snapshot_lines),
    ]
    return "\n".join(lines)


def get_akshare_news(symbol: str, start_date: str, end_date: str) -> str:
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    _throttle_eastmoney.wait()  # 节流：等待 1.5 秒
    df = ak.stock_news_em(symbol=code)
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
        except Exception:
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
        except Exception:
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


def get_akshare_fund_flow(symbol: str) -> str:
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    df = ak.stock_individual_fund_flow(stock=code, market=exchange)
    if df.empty:
        return f"No CN fund-flow data found for symbol '{symbol}'"

    prepared = _prepare_fund_flow(df, limit=10)
    return (
        f"# CN A-share fund-flow proxy for {code}.{exchange.upper()}\n"
        "# Vendor: akshare.stock_individual_fund_flow\n"
        "# This replaces insider transactions in the minimal CN stack with main-force fund-flow data.\n"
        "# Fields pruned for LLM consumption: close, daily change, main-force / extra-large / large-order net inflows and ratios\n"
        f"# Total sessions included: {len(prepared)}\n\n"
        + _render_fund_flow(prepared)
    )


def get_akshare_cn_market_flow(symbol: str) -> str:
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    _throttle_eastmoney.wait()  # 节流：等待 1.5 秒
    df = ak.stock_individual_fund_flow(stock=code, market=exchange)
    if df.empty:
        return f"No CN market-flow proxy data found for symbol '{symbol}'"

    prepared = _prepare_fund_flow(df, limit=5)
    return (
        f"# CN market-flow proxy for {code}.{exchange.upper()}\n"
        "# Vendor: akshare.stock_individual_fund_flow\n"
        "# Intended use: execution-risk, liquidity, and main-force flow proxy for mainland China equities.\n"
        f"# Total sessions included: {len(prepared)}\n\n"
        + _render_fund_flow(prepared)
    )


# ================================================================================
# 行业新闻工具实现 (Sector News Tools)
# ================================================================================

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
    except Exception:
        pass

    # Get macro tech news from economic calendar
    macro_news = []
    for offset in range(max(look_back_days, 1)):
        date_str = (target_date - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            macro_df = ak.news_economic_baidu(date=date_str)
            if not macro_df.empty:
                macro_news.append(macro_df)
        except Exception:
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
        except Exception:
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
        except Exception:
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
        except Exception:
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
        except Exception:
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


# ================================================================================
# 宏观数据工具实现 (Macro Data Tools)
# ================================================================================

def _render_macro_indicator(df: pd.DataFrame, indicator_name: str) -> str:
    """Render macro indicator data for display."""
    if df.empty:
        return f"No data available for {indicator_name}"

    entries = []
    for _, row in df.iterrows():
        lines = []
        for col, val in row.items():
            if pd.notna(val):
                lines.append(f"{col}: {val}")
        if lines:
            entries.append(_render_bullets(lines))

    return f"## {indicator_name}\n\n" + "\n\n".join(entries)


def get_akshare_cn_macro_data(
    indicators: list,
    period: str = "quarterly",
    limit: int = 8
) -> str:
    """Get China macro economic indicator data."""
    ak = _require_akshare()

    results = []
    indicator_map = {
        "gdp": ("gdp", "quarterly" if period == "quarterly" else "monthly"),
        "cpi": ("cpi", "monthly"),
        "ppi": ("ppi", "monthly"),
        "m2": ("m2", "monthly"),
        "loan": ("social_financing", "monthly"),
        "industrial_production": ("industrial_production", "monthly"),
    }

    for indicator in indicators:
        if indicator not in indicator_map:
            continue

        func_name, data_period = indicator_map[indicator]

        try:
            if func_name == "gdp":
                df = ak.macro_china_gdp()
            elif func_name == "cpi":
                df = ak.macro_china_cpi()
            elif func_name == "ppi":
                df = ak.macro_china_ppi()
            elif func_name == "m2":
                df = ak.macro_china_m2()
            elif func_name == "social_financing":
                df = ak.macro_china_shibor()
            elif func_name == "industrial_production":
                df = ak.macro_china_industrial_production()
            else:
                continue

            if not df.empty:
                prepared = df.head(limit).copy()
                results.append(_render_macro_indicator(prepared, indicator.upper()))

        except Exception:
            continue

    if not results:
        return "No macro data available for the requested indicators"

    header = (
        f"# China Macro Economic Indicators ({period})\n"
        f"# Indicators: {', '.join(indicators)}\n"
        f"# Data points per indicator: {limit}\n"
        "# Vendor: akshare macro series\n\n"
    )
    return header + "\n\n".join(results)


def get_akshare_cn_rate_outlook(focus: str = "all") -> str:
    """Get China interest rate and exchange rate outlook."""
    ak = _require_akshare()

    results = []

    # LPR data
    if focus in ["lpr", "all"]:
        try:
            lpr_df = ak.macro_china_lpr()
            if not lpr_df.empty:
                prepared = lpr_df.head(12).copy()
                results.append("# Loan Prime Rate (LPR)\n\n" + _render_macro_indicator(prepared, "LPR"))
        except Exception:
            results.append("# Loan Prime Rate (LPR)\n\nNo LPR data available")

    # SHIBOR data (proxy for interbank rates)
    if focus in ["deposit_reserve", "all"]:
        try:
            shibor_df = ak.macro_china_shibor()
            if not shibor_df.empty:
                prepared = shibor_df.head(12).copy()
                results.append("# SHIBOR (Shanghai Interbank Offered Rate)\n\n" + _render_macro_indicator(prepared, "SHIBOR"))
        except Exception:
            results.append("# SHIBOR\n\nNo SHIBOR data available")

    # Exchange rate
    if focus in ["exchange", "all"]:
        try:
            # Try to get USD/CNY rate
            currency_df = ak.currency_china_spot()
            if not currency_df.empty:
                prepared = currency_df.head(5).copy()
                results.append("# USD/CNY Exchange Rate\n\n" + _render_macro_indicator(prepared, "USD/CNY"))
        except Exception:
            try:
                # Alternative: try macro forex data
                forex_df = ak.macro_china_fx()
                if not forex_df.empty:
                    prepared = forex_df.head(10).copy()
                    results.append("# China Forex Reserve\n\n" + _render_macro_indicator(prepared, "Forex"))
            except Exception:
                results.append("# Exchange Rate\n\nNo exchange rate data available")

    if not results:
        return "No rate outlook data available"

    header = (
        f"# China Interest Rate & Exchange Rate Outlook\n"
        f"# Focus: {focus}\n"
        "# Vendor: akshare macro series\n\n"
    )
    return header + "\n\n".join(results)


def get_akshare_cn_trade_data(months: int = 12, focus: str = "all") -> str:
    """Get China trade data."""
    ak = _require_akshare()

    results = []

    # Trade balance
    if focus in ["balance", "all"]:
        try:
            balance_df = ak.macro_china_trade_balance()
            if not balance_df.empty:
                prepared = balance_df.head(months).copy()
                results.append("# China Trade Balance\n\n" + _render_macro_indicator(prepared, "Trade Balance"))
        except Exception:
            results.append("# China Trade Balance\n\nNo trade balance data available")

    # Export data
    if focus in ["export", "all"]:
        try:
            export_df = ak.macro_china_exports()
            if not export_df.empty:
                prepared = export_df.head(months).copy()
                results.append("# China Exports\n\n" + _render_macro_indicator(prepared, "Exports"))
        except Exception:
            results.append("# China Exports\n\nNo export data available")

    # Import data
    if focus in ["import", "all"]:
        try:
            import_df = ak.macro_china_imports()
            if not import_df.empty:
                prepared = import_df.head(months).copy()
                results.append("# China Imports\n\n" + _render_macro_indicator(prepared, "Imports"))
        except Exception:
            results.append("# China Imports\n\nNo import data available")

    if not results:
        return "No trade data available"

# ================================================================================
# 事件数据工具实现 (Event Data Tools)
# ================================================================================

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


# ================================================================================
# A股完整财报工具实现 (CN Financial Statements)
# ================================================================================

def _prepare_financial_statement(df: pd.DataFrame, statement_type: str, limit: int = 8) -> pd.DataFrame:
    """Prepare financial statement data for display."""
    if df.empty:
        return df

    working = df.copy()

    # Ensure date column is properly formatted
    date_columns = ["报告日期", "日期", "截止日期", "报告期"]
    date_col = None
    for col in date_columns:
        if col in working.columns:
            date_col = col
            break

    if date_col:
        working = working.sort_values(date_col, ascending=False)

    return working.head(limit).copy()


def _render_financial_statement(df: pd.DataFrame, statement_type: str, code: str) -> str:
    """Render financial statement data for display."""
    if df.empty:
        return f"No {statement_type} data available for {code}"

    entries = []
    for _, row in df.iterrows():
        lines = []
        for col, val in row.items():
            if pd.notna(val):
                # Format numeric values
                if isinstance(val, (int, float)):
                    val_str = f"{val:,.2f}" if abs(val) >= 1 else f"{val:.4f}"
                else:
                    val_str = str(val)
                lines.append(f"{col}: {val_str}")
        if lines:
            entries.append(_render_bullets(lines))

    return f"# {code} {statement_type}\n\n" + "\n\n".join(entries)


def get_akshare_balance_sheet(symbol: str, period: str = "quarterly", limit: int = 8) -> str:
    """
    Get A-share balance sheet data.

    Args:
        symbol: A-share ticker (e.g., "600519.SH" or "000001.SZ")
        period: Data period - "quarterly" (default) or "annual"
        limit: Maximum number of periods to return

    Returns:
        Balance sheet data in formatted string
    """
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    try:
        # Try to get balance sheet data
        df = ak.stock_balance_sheet_by_report_em(symbol=code)

        if df.empty:
            return f"No balance sheet data available for {code}.{exchange.upper()}"

        prepared = _prepare_financial_statement(df, "Balance Sheet", code)

        header = (
            f"# {code}.{exchange.upper()} Balance Sheet\n"
            f"# Period: {period}\n"
            f"# Vendor: akshare.stock_balance_sheet_by_report_em\n"
            f"# Records: {len(prepared)}\n\n"
        )

        return header + _render_financial_statement(prepared, "Balance Sheet", code)

    except Exception as e:
        return f"Balance sheet data unavailable for {code}.{exchange.upper()}: {str(e)}"


def get_akshare_cashflow(symbol: str, period: str = "quarterly", limit: int = 8) -> str:
    """
    Get A-share cash flow statement data.

    Args:
        symbol: A-share ticker (e.g., "600519.SH" or "000001.SZ")
        period: Data period - "quarterly" (default) or "annual"
        limit: Maximum number of periods to return

    Returns:
        Cash flow statement data in formatted string
    """
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    try:
        # Try to get cash flow data
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=code)

        if df.empty:
            return f"No cash flow data available for {code}.{exchange.upper()}"

        prepared = _prepare_financial_statement(df, "Cash Flow Statement", code)

        header = (
            f"# {code}.{exchange.upper()} Cash Flow Statement\n"
            f"# Period: {period}\n"
            f"# Vendor: akshare.stock_cash_flow_sheet_by_report_em\n"
            f"# Records: {len(prepared)}\n\n"
        )

        return header + _render_financial_statement(prepared, "Cash Flow Statement", code)

    except Exception as e:
        return f"Cash flow data unavailable for {code}.{exchange.upper()}: {str(e)}"


def get_akshare_income_statement(symbol: str, period: str = "quarterly", limit: int = 8) -> str:
    """
    Get A-share income statement data.

    Args:
        symbol: A-share ticker (e.g., "600519.SH" or "000001.SZ")
        period: Data period - "quarterly" (default) or "annual"
        limit: Maximum number of periods to return

    Returns:
        Income statement data in formatted string
    """
    ak = _require_akshare()
    code, exchange = _normalize_cn_symbol(symbol)

    try:
        # Try to get income statement data
        df = ak.stock_profit_sheet_by_report_em(symbol=code)

        if df.empty:
            return f"No income statement data available for {code}.{exchange.upper()}"

        prepared = _prepare_financial_statement(df, "Income Statement", code)

        header = (
            f"# {code}.{exchange.upper()} Income Statement\n"
            f"# Period: {period}\n"
            f"# Vendor: akshare.stock_profit_sheet_by_report_em\n"
            f"# Records: {len(prepared)}\n\n"
        )

        return header + _render_financial_statement(prepared, "Income Statement", code)

    except Exception as e:
        return f"Income statement data unavailable for {code}.{exchange.upper()}: {str(e)}"


# ================================================================================
# 统一错误处理和速率限制
# ================================================================================

class AkShareRateLimitError(Exception):
    """Raised when AkShare API rate limit is exceeded."""
    pass


class DataSourceError(Exception):
    """Base exception for data source errors."""
    pass


class DataNotFoundError(DataSourceError):
    """Raised when requested data is not found."""
    pass


class InvalidParameterError(DataSourceError):
    """Raised when parameters are invalid."""
    pass


def _handle_rate_limit(vendor: str, error: Exception) -> None:
    """
    Handle rate limiting for different vendors.

    Args:
        vendor: The vendor name (e.g., "akshare", "alpha_vantage")
        error: The original exception

    Raises:
        Appropriate rate limit exception based on vendor
    """
    import time

    if vendor == "akshare":
        # AkShare generally doesn't have strict rate limits but may throttle
        # Add a small delay and continue
        time.sleep(0.5)
    elif vendor == "alpha_vantage":
        # Alpha Vantage has strict rate limits (5 calls/min for free tier)
        raise AlphaVantageRateLimitError(
            f"Alpha Vantage rate limit exceeded. Wait before retrying."
        ) from error
    else:
        raise error


# Rate limiting state
_rate_limit_state = {
    "akshare": {
        "last_call_time": 0,
        "min_interval": 0.1,  # 100ms minimum between calls
    },
    "alpha_vantage": {
        "last_call_time": 0,
        "min_interval": 12,  # 12 seconds for free tier (5 calls/min)
    }
}


def _check_rate_limit(vendor: str) -> None:
    """
    Check and enforce rate limiting for vendor calls.

    Args:
        vendor: The vendor name

    Raises:
        AkShareRateLimitError if rate limit is exceeded
    """
    import time

    if vendor not in _rate_limit_state:
        return

    state = _rate_limit_state[vendor]
    current_time = time.time()
    time_since_last_call = current_time - state["last_call_time"]

    if time_since_last_call < state["min_interval"]:
        sleep_time = state["min_interval"] - time_since_last_call
        time.sleep(sleep_time)

    state["last_call_time"] = time.time()


def _reset_rate_limit_state():
    """Reset rate limit state (mainly for testing)."""
    for vendor in _rate_limit_state:
        _rate_limit_state[vendor]["last_call_time"] = 0

