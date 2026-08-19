"""THS (同花顺) fetch paths: concept/industry boards, fund flow, and the
HTML-scraping constituent resolver with its concept-code lookup cache.

Extracted from ScreenerDataAccess (data_access.py) during the Phase 4 split.
The concept-code cache moved from instance state to module level (it is a
pure name->code lookup; process-level sharing is safe and avoids re-fetching).
Guarded by `vendor_call` (task R3): failures logged, None contract kept.
"""

from __future__ import annotations

from typing import Dict

from tradingagents.screener.response_parsers import parse_ths_board_table
from tradingagents.screener.vendor_http import VendorHttp
from tradingagents.screener.vendors._guard import vendor_call

__all__ = [
    "fetch_concept_boards",
    "fetch_industry_boards",
    "fetch_fund_flow",
    "fetch_concept_constituents_html",
    "reset_concept_code_cache",
]

# Module-level lookup cache: THS concept name -> board code
_concept_code_cache: Dict[str, str] = {}


def reset_concept_code_cache() -> None:
    """Test hook: clear the concept-code lookup cache."""
    _concept_code_cache.clear()


@vendor_call("ths.fetch_concept_boards")
def fetch_concept_boards(http: VendorHttp):
    import akshare as ak

    http.sleep_for_vendor("ths")
    with http.spoof():
        df = ak.stock_board_concept_name_ths()
    if df is not None and not df.empty:
        df = df.copy()
        df["source"] = "ths"
    return df


@vendor_call("ths.fetch_industry_boards")
def fetch_industry_boards(http: VendorHttp):
    import akshare as ak

    http.sleep_for_vendor("ths")
    with http.spoof():
        df = ak.stock_board_industry_name_ths()
    if df is not None and not df.empty:
        df = df.copy()
        df["source"] = "ths"
    return df


@vendor_call("ths.fetch_fund_flow")
def fetch_fund_flow(http: VendorHttp, symbol: str = "即时", symbol_type: str = "individual"):
    import akshare as ak

    http.sleep_for_vendor("ths")
    with http.spoof():
        if symbol_type == "individual":
            return ak.stock_fund_flow_individual(symbol=symbol)
        elif symbol_type == "concept":
            return ak.stock_fund_flow_concept(symbol=symbol)
        elif symbol_type == "industry":
            return ak.stock_fund_flow_industry(symbol=symbol)
    return None


def _resolve_concept_code(http: VendorHttp, concept_name: str) -> str | None:
    """Resolve a concept name to its THS board code (e.g., "AI PC" -> "309121")."""
    if not _concept_code_cache:
        try:
            import akshare as ak

            http.sleep_for_vendor("ths")
            with http.spoof():
                df = ak.stock_board_concept_name_ths()
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    name = str(row.get("name", ""))
                    code = str(row.get("code", ""))
                    if name and code:
                        _concept_code_cache[name] = code
        except Exception:
            # cache warm-up failure: fall through to fuzzy match on an empty cache
            pass

    if concept_name in _concept_code_cache:
        return _concept_code_cache[concept_name]

    # Fuzzy match: try contains
    for cached_name, cached_code in _concept_code_cache.items():
        if concept_name in cached_name or cached_name in concept_name:
            return cached_code

    return None


@vendor_call("ths.fetch_concept_constituents_html")
def fetch_concept_constituents_html(http: VendorHttp, concept_name: str, max_stocks: int = 50):
    """Fetch concept constituents by scraping the THS board detail page.

    The standard AkShare THS APIs return concept metadata instead of
    constituent stocks; this scrapes the HTML board detail page which
    contains the actual constituent table.

    URL pattern: http://q.10jqka.com.cn/gn/detail/code/{ths_code}/
    """
    import pandas as pd

    ths_code = _resolve_concept_code(http, concept_name)
    if ths_code is None:
        return None

    url = f"http://q.10jqka.com.cn/gn/detail/code/{ths_code}/"
    text = http.tencent_direct(url, timeout=15.0)
    if text is None:
        return None

    rows = parse_ths_board_table(text, max_stocks)
    if not rows:
        return None

    return pd.DataFrame(rows)
