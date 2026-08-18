"""AkShare macro vendors: macro indicators, rate outlook, trade data."""
from __future__ import annotations

import time
import threading
from datetime import datetime, timedelta
from io import StringIO
from typing import Iterable, Tuple

import pandas as pd

from tradingagents.dataflows.akshare._shared import _normalize_cn_symbol, _render_bullets, _require_akshare, _throttle_eastmoney


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
