from __future__ import annotations

import importlib
import logging
from typing import Callable, Dict, List

from .config import get_config
from .errors import VendorRateLimited, VendorUnavailable

logger = logging.getLogger(__name__)


TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": ["get_stock_data"],
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": ["get_indicators"],
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement",
        ],
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
            "get_cn_policy_news",
            "get_cn_market_flow",
            "get_cn_tech_sector_news",
            "get_cn_new_energy_news",
            "get_cn_pharma_news",
            "get_cn_real_estate_news",
            "get_cn_fintech_news",
        ],
    },
    "cn_macro_data": {
        "description": "China macro economic data",
        "tools": [
            "get_cn_macro_data",
            "get_cn_rate_outlook",
            "get_cn_trade_data",
        ],
    },
    "cn_event_data": {
        "description": "China A-share event-driven data",
        "tools": [
            "get_cn_earnings_calendar",
            "get_cn_ipo_data",
            "get_cn_m_a_news",
            "get_cn_stock_pledge",
            "get_cn_limit_up_stocks",
        ],
    },
}


VENDOR_ALIASES = {
    "tencent": "tencent_finance",
    "tencent_finance": "tencent_finance",
    "sina": "sina_finance",
    "sina_finance": "sina_finance",
    "ths": "ths_data",
    "ths_data": "ths_data",
    "baidu": "baidu_finance",
    "baidu_finance": "baidu_finance",
    "baostock": "baostock_data",
    "baostock_data": "baostock_data",
    "akshare": "legacy_akshare",
    "legacy_akshare": "legacy_akshare",
    "yfinance": "legacy_yfinance",
    "legacy_yfinance": "legacy_yfinance",
    "alpha_vantage": "legacy_alpha_vantage",
    "legacy_alpha_vantage": "legacy_alpha_vantage",
}


VENDOR_LIST = [
    "tencent_finance",
    "sina_finance",
    "ths_data",
    "baidu_finance",
    "baostock_data",
    "legacy_akshare",
    "legacy_yfinance",
    "legacy_alpha_vantage",
]


def _load_attr(module_name: str, attr_name: str):
    module = importlib.import_module(module_name, package=__package__)
    return getattr(module, attr_name)


def _lazy_callable(module_name: str, attr_name: str) -> Callable:
    def _call(*args, **kwargs):
        func = _load_attr(module_name, attr_name)
        return func(*args, **kwargs)

    _call.__name__ = attr_name
    return _call


def _coerce_tabular(result) -> str:
    if result is None:
        return "No data available."
    if hasattr(result, "empty") and getattr(result, "empty", False):
        return "No data available."
    if hasattr(result, "to_csv"):
        try:
            return result.to_csv(index=False)
        except Exception:
            pass
    return str(result)


def _raise_vendor_unavailable(vendor: str, method: str) -> Callable:
    def _call(*args, **kwargs):
        raise VendorUnavailable(
            f"Vendor '{vendor}' is not implemented for method '{method}' in the Tencent-first interface baseline."
        )

    _call.__name__ = f"{vendor}_{method}_unavailable"
    return _call


VENDOR_METHODS: Dict[str, Dict[str, Callable]] = {
    "get_stock_data": {
        "tencent_finance": _lazy_callable(".akshare_interface", "get_akshare_stock_data"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_stock_data"),
        "legacy_yfinance": _lazy_callable(".y_finance", "get_YFin_data_online"),
        "legacy_alpha_vantage": _lazy_callable(".alpha_vantage", "get_stock"),
    },
    "get_indicators": {
        "tencent_finance": _lazy_callable(".cn_indicators", "get_cn_indicators"),
        "sina_finance": _lazy_callable(".cn_indicators", "get_cn_indicators"),
        "legacy_alpha_vantage": _lazy_callable(".alpha_vantage", "get_indicator"),
        "legacy_yfinance": _lazy_callable(".y_finance", "get_stock_stats_indicators_window"),
    },
    "get_fundamentals": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_fundamentals"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_fundamentals"),
        "legacy_yfinance": _lazy_callable(".y_finance", "get_fundamentals"),
        "legacy_alpha_vantage": _lazy_callable(".alpha_vantage", "get_fundamentals"),
    },
    "get_balance_sheet": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_balance_sheet"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_balance_sheet"),
        "legacy_yfinance": _lazy_callable(".y_finance", "get_balance_sheet"),
        "legacy_alpha_vantage": _lazy_callable(".alpha_vantage", "get_balance_sheet"),
    },
    "get_cashflow": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_cashflow"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cashflow"),
        "legacy_yfinance": _lazy_callable(".y_finance", "get_cashflow"),
        "legacy_alpha_vantage": _lazy_callable(".alpha_vantage", "get_cashflow"),
    },
    "get_income_statement": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_income_statement"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_income_statement"),
        "legacy_yfinance": _lazy_callable(".y_finance", "get_income_statement"),
        "legacy_alpha_vantage": _lazy_callable(".alpha_vantage", "get_income_statement"),
    },
    "get_news": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_news"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_news"),
        "legacy_yfinance": _lazy_callable(".yfinance_news", "get_news_yfinance"),
        "legacy_alpha_vantage": _lazy_callable(".alpha_vantage", "get_news"),
    },
    "get_global_news": {
        "baidu_finance": _lazy_callable(".akshare_interface", "get_akshare_global_news"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_global_news"),
        "legacy_yfinance": _lazy_callable(".yfinance_news", "get_global_news_yfinance"),
        "legacy_alpha_vantage": _lazy_callable(".alpha_vantage", "get_global_news"),
    },
    "get_insider_transactions": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_fund_flow"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_fund_flow"),
        "legacy_yfinance": _lazy_callable(".y_finance", "get_insider_transactions"),
        "legacy_alpha_vantage": _lazy_callable(".alpha_vantage", "get_insider_transactions"),
    },
    "get_cn_policy_news": {
        "baidu_finance": _lazy_callable(".akshare_interface", "get_akshare_cn_policy_news"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_policy_news"),
    },
    "get_cn_market_flow": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_cn_market_flow"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_market_flow"),
    },
    "get_cn_tech_sector_news": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_cn_tech_sector_news"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_tech_sector_news"),
    },
    "get_cn_new_energy_news": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_cn_new_energy_news"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_new_energy_news"),
    },
    "get_cn_pharma_news": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_cn_pharma_news"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_pharma_news"),
    },
    "get_cn_real_estate_news": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_cn_real_estate_news"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_real_estate_news"),
    },
    "get_cn_fintech_news": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_cn_fintech_news"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_fintech_news"),
    },
    "get_cn_macro_data": {
        "baidu_finance": _lazy_callable(".akshare_interface", "get_akshare_cn_macro_data"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_macro_data"),
    },
    "get_cn_rate_outlook": {
        "baidu_finance": _lazy_callable(".akshare_interface", "get_akshare_cn_rate_outlook"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_rate_outlook"),
    },
    "get_cn_trade_data": {
        "baidu_finance": _lazy_callable(".akshare_interface", "get_akshare_cn_trade_data"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_trade_data"),
    },
    "get_cn_earnings_calendar": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_cn_earnings_calendar"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_earnings_calendar"),
    },
    "get_cn_ipo_data": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_cn_ipo_data"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_ipo_data"),
    },
    "get_cn_m_a_news": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_cn_m_a_news"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_m_a_news"),
    },
    "get_cn_stock_pledge": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_cn_stock_pledge"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_stock_pledge"),
    },
    "get_cn_limit_up_stocks": {
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_cn_limit_up_stocks"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cn_limit_up_stocks"),
    },
}


def _attach_legacy_aliases() -> None:
    alias_pairs = {
        "tencent_finance": ["tencent"],
        "sina_finance": ["sina"],
        "ths_data": ["ths"],
        "baidu_finance": ["baidu"],
        "baostock_data": ["baostock"],
        "legacy_akshare": ["akshare"],
        "legacy_yfinance": ["yfinance"],
        "legacy_alpha_vantage": ["alpha_vantage"],
    }
    for method, vendor_map in VENDOR_METHODS.items():
        for canonical, aliases in alias_pairs.items():
            if canonical not in vendor_map:
                continue
            for alias in aliases:
                vendor_map.setdefault(alias, vendor_map[canonical])


_attach_legacy_aliases()


DEFAULT_VENDOR_PRIORITY = {
    "core_stock_apis": "tencent_finance,sina_finance,baostock_data,legacy_yfinance",
    "technical_indicators": "tencent_finance,sina_finance,legacy_alpha_vantage,legacy_yfinance",
    "fundamental_data": "ths_data,legacy_akshare,legacy_yfinance",
    "news_data": "ths_data,baidu_finance,legacy_akshare,legacy_yfinance",
    "cn_macro_data": "baidu_finance,legacy_akshare",
    "cn_event_data": "ths_data,legacy_akshare",
}


def get_category_for_method(method: str) -> str:
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")


def _normalize_vendor_name(vendor: str) -> str:
    value = str(vendor or "").strip()
    if not value:
        return value
    return VENDOR_ALIASES.get(value, value)


def get_vendor(category: str, method: str | None = None) -> str:
    config = get_config()
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            configured = str(tool_vendors[method])
            return ",".join(
                part for part in (_normalize_vendor_name(item) for item in configured.split(",")) if part
            )

    configured = str(config.get("data_vendors", {}).get(category, DEFAULT_VENDOR_PRIORITY.get(category, "")))
    if not configured:
        configured = DEFAULT_VENDOR_PRIORITY.get(category, "")
    return ",".join(
        part for part in (_normalize_vendor_name(item) for item in configured.split(",")) if part
    )


def _is_rate_limit_error(exc: Exception) -> bool:
    if isinstance(exc, VendorRateLimited):
        return True
    return exc.__class__.__name__ in {
        "AlphaVantageRateLimitError",
        "AkShareRateLimitError",
        "YFRateLimitError",
    }


def route_to_vendor(method: str, *args, **kwargs):
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [item.strip() for item in vendor_config.split(",") if item.strip()]
    explicit_single_vendor = len(primary_vendors) == 1

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    registered = VENDOR_METHODS[method]
    fallback_vendors: List[str] = []
    for vendor in primary_vendors + list(registered.keys()):
        normalized = _normalize_vendor_name(vendor)
        if normalized and normalized not in fallback_vendors:
            fallback_vendors.append(normalized)

    optional_vendor_errors = []
    runtime_errors = []

    for vendor in fallback_vendors:
        impl_func = registered.get(vendor)
        if impl_func is None and vendor in VENDOR_ALIASES:
            impl_func = registered.get(VENDOR_ALIASES[vendor])
        if impl_func is None:
            if vendor in VENDOR_LIST:
                optional_vendor_errors.append(f"{vendor}: not registered for {method}")
                continue

        try:
            return impl_func(*args, **kwargs)
        except ImportError as exc:
            optional_vendor_errors.append(f"{vendor}: {exc}")
            continue
        except Exception as exc:
            if _is_rate_limit_error(exc):
                runtime_errors.append(f"{vendor}: rate limited")
                continue
            if explicit_single_vendor:
                raise
            runtime_errors.append(f"{vendor}: {type(exc).__name__}: {exc}")
            continue

    detail_parts = []
    if runtime_errors:
        detail_parts.append(f"runtime failures: {'; '.join(runtime_errors)}")
    if optional_vendor_errors:
        detail_parts.append(f"optional vendor failures: {'; '.join(optional_vendor_errors)}")
    detail = " | ".join(detail_parts) if detail_parts else "no registered vendors"
    raise VendorUnavailable(
        f"No available vendor for '{method}' under Tencent-first routing baseline: {detail}"
    )


# NOTE (2026-08-16): an abandoned RAG-enhancement hook (route_to_vendor_with_rag
# and helpers) lived here. It had zero callers — the live RAG integration is
# tradingagents/agents/utils/rag_news_tools.py and rag/rag_middleware.py, which
# call plain route_to_vendor(). Its module-level import of the rag package was
# one edge of the interface -> rag -> cn_news_retriever -> tools -> interface
# cycle; removing the dead code breaks that cycle at the import-graph level.
