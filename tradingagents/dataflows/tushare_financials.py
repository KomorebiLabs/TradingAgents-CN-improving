"""Optional Tushare Pro adapter for independent financial statements."""

from __future__ import annotations

from datetime import date
import os
from typing import Any, Dict, Iterable, List

import requests


TUSHARE_API_URL = "https://api.tushare.pro"
_STATEMENT_APIS = {"income": "income", "balance_sheet": "balancesheet", "cashflow": "cashflow"}
_FIELD_LABELS = {
    "income": {
        "revenue": "Revenue",
        "total_revenue": "Revenue",
        "operate_profit": "Operating Income",
        "n_income": "Net Income",
        "n_income_attr_p": "Net Income",
        "basic_eps": "EPS",
    },
    "balance_sheet": {
        "total_assets": "Total Assets",
        "total_cur_assets": "Current Assets",
        "inventories": "Inventory",
        "total_liab": "Total Liabilities",
        "total_cur_liab": "Current Liabilities",
        "total_hldr_eqy_exc_min_int": "Stockholders Equity",
        "money_cap": "Cash",
        "total_debt": "Total Debt",
    },
    "cashflow": {
        "n_cashflow_act": "Operating Cash Flow",
        "n_cashflow_inv_act": "Investing Cash Flow",
        "n_cash_flows_fnc_act": "Financing Cash Flow",
        "free_cashflow": "Free Cash Flow",
        "c_pay_equity": "Cash Dividends Paid",
    },
}


def _token() -> str:
    value = os.getenv("TUSHARE_TOKEN", "").strip()
    if value:
        return value
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass
    return os.getenv("TUSHARE_TOKEN", "").strip()


def _normalize_ticker(ticker: str) -> str:
    raw = str(ticker or "").strip().upper()
    if "." in raw:
        return raw
    if raw.startswith(("60", "68")):
        return f"{raw}.SH"
    return f"{raw}.SZ"


def _date_text(value: Any) -> str:
    return str(value or "").replace("-", "")[:8]


def _rows_before_trade_date(rows: Iterable[Dict[str, Any]], curr_date: str, freq: str) -> List[Dict[str, Any]]:
    cutoff = _date_text(curr_date) if curr_date else "99999999"
    result = []
    for row in rows:
        period = _date_text(row.get("end_date"))
        announced = _date_text(row.get("ann_date") or row.get("f_ann_date"))
        if not period or period > cutoff or (announced and announced > cutoff):
            continue
        if freq.lower() == "annual" and not period.endswith("1231"):
            continue
        result.append(row)
    return sorted(result, key=lambda item: _date_text(item.get("end_date")), reverse=True)


def get_tushare_financial_statement(
    ticker: str,
    statement: str,
    freq: str = "annual",
    curr_date: str | None = None,
) -> str:
    """Fetch and render PIT-safe Tushare Pro statement rows.

    Tushare permissions vary by account. Permission failures are returned as
    explicit degraded text so the router can continue to other sources.
    """
    api_name = _STATEMENT_APIS.get(statement)
    if api_name is None:
        raise ValueError(f"Unsupported Tushare statement: {statement}")
    token = _token()
    if not token:
        return f"No Tushare Pro token configured for {statement}"

    payload = {
        "api_name": api_name,
        "token": token,
        "params": {"ts_code": _normalize_ticker(ticker)},
        "fields": "",
    }
    if curr_date:
        payload["params"]["end_date"] = _date_text(curr_date)
    response = requests.post(TUSHARE_API_URL, json=payload, timeout=20)
    response.raise_for_status()
    body = response.json()
    if body.get("code") == 2002:
        return f"No Tushare Pro permission for {statement}: {body.get('msg', 'permission denied')}"
    if body.get("code") not in (0, None):
        return f"Error retrieving Tushare {statement}: {body.get('msg', 'unknown API error')}"
    data = body.get("data") or {}
    fields = list(data.get("fields") or [])
    rows = [dict(zip(fields, values)) for values in data.get("items") or []]
    rows = _rows_before_trade_date(rows, curr_date or "", freq)
    if not rows:
        return f"No Tushare Pro {statement} data found for {ticker}"

    lines = [
        f"# {statement.replace('_', ' ').title()} data for {_normalize_ticker(ticker)}",
        "# Vendor: tushare.pro",
        "# Unit: CNY yuan for currency fields; EPS and ratios retain native units",
        "",
    ]
    labels = _FIELD_LABELS[statement]
    for row in rows[:8]:
        period = f"{_date_text(row.get('end_date'))[:4]}-{_date_text(row.get('end_date'))[4:6]}-{_date_text(row.get('end_date'))[6:8]}"
        announced_raw = _date_text(row.get("ann_date") or row.get("f_ann_date"))
        announced = f"{announced_raw[:4]}-{announced_raw[4:6]}-{announced_raw[6:8]}" if announced_raw else "unknown"
        for field, label in labels.items():
            value = row.get(field)
            if value is None:
                continue
            suffix = " 元" if field not in {"basic_eps"} else ""
            try:
                rendered = f"{float(value):.2f}"
            except (TypeError, ValueError):
                rendered = str(value)
            lines.append(f"{label} ({period}): {rendered}{suffix} | Published date: {announced}")
    return "\n".join(lines)


def get_tushare_income_statement(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    return get_tushare_financial_statement(ticker, "income", freq, curr_date)


def get_tushare_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    return get_tushare_financial_statement(ticker, "balance_sheet", freq, curr_date)


def get_tushare_cashflow(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    return get_tushare_financial_statement(ticker, "cashflow", freq, curr_date)
