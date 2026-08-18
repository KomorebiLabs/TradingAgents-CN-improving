"""AkShare fund-flow vendors: individual + market money flow."""
from __future__ import annotations

import time
import threading
from datetime import datetime, timedelta
from io import StringIO
from typing import Iterable, Tuple

import pandas as pd

from tradingagents.dataflows.akshare._shared import _normalize_cn_symbol, _render_bullets, _require_akshare, _throttle_eastmoney


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
