"""AkShare stock-data + fundamentals-snapshot vendors.

One reason to change: the AkShare stock/fundamentals APIs change shape."""
from __future__ import annotations

import time
import threading
from datetime import datetime, timedelta
from io import StringIO
from typing import Iterable, Tuple

import pandas as pd

from tradingagents.dataflows.akshare._shared import _normalize_cn_symbol, _render_bullets, _require_akshare, _throttle_eastmoney, _throttle_tencent


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
