"""Pure response parsers for raw vendor payloads.

One reason to change: a vendor changes its response format. All functions are
pure (raw text/JSON in -> list/dict/DataFrame out) and unit-testable with
saved fixtures — no I/O.

Extracted from ScreenerDataAccess (data_access.py) during the Phase 4 split.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from tradingagents.screener.ticker_formats import safe_float

__all__ = [
    "parse_ths_board_table",
    "parse_tencent_kline",
    "parse_tencent_quote_lines",
    "parse_tencent_index_lines",
    "normalize_yfinance_hist_frame",
    "TENCENT_STOCK_QUOTE_MIN_PARTS",
]


# ---------------------------------------------------------------------------
# THS (同花顺) concept-board HTML table
# ---------------------------------------------------------------------------

def parse_ths_board_table(html_content: str, max_stocks: int = 50) -> List[Dict[str, Any]]:
    """Parse the constituent stock table from THS board HTML.

    The table has columns:
    - rank (排名)
    - code (股票代码) - 6-digit string
    - name (股票简称)
    - price (现价)
    - change_pct (涨跌幅)
    - turnover (换手率)
    - amount (成交额, converted 亿 -> 元)
    """
    rows = []
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", html_content, re.DOTALL)
    if not tbody_match:
        return rows

    tbody = tbody_match.group(1)
    tr_matches = re.findall(r"<tr>(.*?)</tr>", tbody, re.DOTALL)

    for tr_html in tr_matches[:max_stocks]:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr_html, re.DOTALL)
        if len(cells) < 5:
            continue

        def clean_cell(cell_html: str) -> str:
            return re.sub(r"<[^>]+>", "", cell_html).strip()

        try:
            rank = clean_cell(cells[0])
            code = clean_cell(cells[1])
            name = clean_cell(cells[2])
            if not re.match(r"^\d{6}$", code):
                continue

            change_str = clean_cell(cells[4]).replace("%", "").strip()
            try:
                change_pct = float(change_str)
            except ValueError:
                change_pct = None

            try:
                turnover = float(clean_cell(cells[5]))
            except ValueError:
                turnover = None

            try:
                # 成交额单位为亿元, 转换为元
                amount = float(clean_cell(cells[6])) * 1e8
            except ValueError:
                amount = None

            rows.append({
                "code": code,
                "name": name,
                "rank": rank,
                "change_pct": change_pct,
                "turnover": turnover,
                "amount": amount,
            })
        except (IndexError, ValueError):
            continue

    return rows


# ---------------------------------------------------------------------------
# Tencent direct HTTP payloads
# ---------------------------------------------------------------------------

def parse_tencent_kline(text: str, tx_symbol: str, adj: str):
    """Parse a Tencent fqkline JSON payload into a DataFrame.

    Payload arrives as ``var kline_dayqfq={...}``; returns None on any shape
    or parse error. Output columns: date/open/close/high/low/volume/amount.
    """
    import pandas as pd

    try:
        raw = text.strip()
        if raw.startswith("var "):
            raw = raw[raw.index("=") + 1:]
        data = json.loads(raw)

        if data.get("code") != 0 or not data.get("data"):
            return None

        data_payload = data.get("data", {})
        if isinstance(data_payload, list):
            return None  # param error, no data

        qt_data = data_payload.get(tx_symbol, {})
        arr_key = "qfqday" if adj == "qfq" else ("hfqday" if adj == "hfq" else "day")
        candles = qt_data.get(arr_key, qt_data.get("day", []))
        if not candles or not isinstance(candles, list):
            return None

        rows = []
        for c in candles:
            if not isinstance(c, (list, tuple)) or len(c) < 6:
                continue
            rows.append({
                "date": c[0],
                "open": safe_float(c[1]),
                "close": safe_float(c[2]),
                "high": safe_float(c[3]),
                "low": safe_float(c[4]),
                "volume": safe_float(c[5]),
            })
        if not rows:
            return None

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df["amount"] = None
        return df
    except Exception:
        return None


# Stock quote lines need >= 32 ~-separated fields
TENCENT_STOCK_QUOTE_MIN_PARTS = 32


def parse_tencent_quote_lines(text: str):
    """Parse Tencent qt.gtimg.cn stock quote lines into a DataFrame.

    Each line: ``v_sz000001="1~name~code~price~prev_close~..."``.
    Returns None when no row parses.
    """
    import pandas as pd

    try:
        lines = text.strip().split("\n")
        rows = []
        for line in lines:
            line = line.strip()
            if not line or not line.startswith("v_"):
                continue
            eq_idx = line.index("=")
            val = line[eq_idx + 1:].strip('"; ')
            parts = val.split("~")
            if len(parts) < TENCENT_STOCK_QUOTE_MIN_PARTS:
                continue
            try:
                symbol_raw = parts[2]
                sym = symbol_raw.lower()
                if sym.startswith("sh") or sym.startswith("sz"):
                    ticker_out = sym
                else:
                    ticker_out = symbol_raw
                rows.append({
                    "symbol": ticker_out,
                    "name": parts[1],
                    "trade": safe_float(parts[3]),
                    "prev_close": safe_float(parts[4]),
                    "open": safe_float(parts[5]),
                    "volume": safe_float(parts[6]),
                    "amount": safe_float(parts[37]) if len(parts) > 37 else None,
                    "change": safe_float(parts[31]) if len(parts) > 31 else None,
                    "changepercent": safe_float(parts[32]) if len(parts) > 32 else None,
                    "high": safe_float(parts[33]) if len(parts) > 33 else None,
                    "low": safe_float(parts[34]) if len(parts) > 34 else None,
                })
            except (IndexError, ValueError):
                continue
        if not rows:
            return None
        df = pd.DataFrame(rows)
        df["source"] = "tencent_direct"
        return df
    except Exception:
        return None


def parse_tencent_index_lines(text: str):
    """Parse Tencent index quote lines (fewer fields than stock quotes)."""
    import pandas as pd

    try:
        lines = text.strip().split("\n")
        rows = []
        for line in lines:
            line = line.strip()
            if not line or not line.startswith("v_"):
                continue
            eq_idx = line.index("=")
            val = line[eq_idx + 1:].strip('"; ')
            parts = val.split("~")
            if len(parts) < 6:
                continue
            try:
                rows.append({
                    "symbol": parts[2],
                    "name": parts[1],
                    "price": safe_float(parts[3]),
                    "change": safe_float(parts[4]),
                    "changepercent": safe_float(parts[5]),
                    "volume": safe_float(parts[6]) if len(parts) > 6 else None,
                    "amount": safe_float(parts[8]) if len(parts) > 8 else None,
                })
            except (IndexError, ValueError):
                continue
        if not rows:
            return None
        return pd.DataFrame(rows)
    except Exception:
        return None


def normalize_yfinance_hist_frame(df):
    """Best-effort index stringification for yfinance history frames."""
    if df is None or getattr(df, "empty", True):
        return df
    normalized = df.copy()
    try:
        normalized.index = normalized.index.astype(str)
    except Exception:
        pass
    return normalized
