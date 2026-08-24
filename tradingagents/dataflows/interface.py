from __future__ import annotations

import importlib
import logging
import os
import re
import time
from datetime import date
from typing import Callable, Dict, List

from .config import get_config
from .errors import VendorRateLimited, VendorUnavailable
from .vendor_health import (
    TRACKER as VENDOR_HEALTH,
    classify_exception,
    classify_provider_text,
    redact_error,
)

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
    "announcement_data": {
        "description": "Official listed-company disclosures",
        "tools": ["get_announcements"],
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
    "cninfo": "cninfo_official",
    "cninfo_official": "cninfo_official",
    "tushare": "tushare_pro",
    "tushare_pro": "tushare_pro",
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
    "cninfo_official",
    "tushare_pro",
]


def _load_attr(module_name: str, attr_name: str):
    module = importlib.import_module(module_name, package=__package__)
    return getattr(module, attr_name)


def _looks_like_unavailable(text: str) -> bool:
    """Detect placeholder/unavailable tool output (task R3: make fake success visible).

    Stage-2 vendors return human-readable strings; an empty result is NOT
    signalled by an empty string — it comes back as "No … found/unavailable"
    prose that a downstream LLM consumes as if it were data. Logging these
    makes silent data loss observable.
    """
    low = text.strip().lower()
    return (
        low.startswith("no ")
        or low.startswith("error ")
        or "unavailable" in low
        # Alpha Vantage news uses a JSON envelope with an empty feed instead
        # of a prose placeholder; without this check it becomes fake success.
        or bool(re.search(r'"items"\s*:\s*["\']?0["\']?', low)
                and re.search(r'"feed"\s*:\s*\[\s*\]', low))
        # News/social payloads may already be wrapped by the untrusted-data
        # boundary before the router sees them.
        or "\nno " in low
    )


def _lazy_callable(module_name: str, attr_name: str) -> Callable:
    from tradingagents.agents.utils.untrusted_wrap import sanitize_untrusted, should_wrap

    def _call(*args, **kwargs):
        func = _load_attr(module_name, attr_name)
        result = func(*args, **kwargs)
        if isinstance(result, str) and _looks_like_unavailable(result):
            logger.warning(
                "[dataflow:%s] returned placeholder/unavailable text (%.100s)",
                attr_name,
                result,
            )
        # A6 layer 2/3: news/social text is untrusted input — strip
        # instruction-shaped sentences and wrap in salted delimiters before
        # it reaches any LLM context.
        if isinstance(result, str) and should_wrap(attr_name):
            result = sanitize_untrusted(result, source=attr_name)
        return result

    _call.__name__ = attr_name
    _call._vendor_source = (module_name, attr_name)
    return _call


def _coerce_tabular(result) -> str:
    if result is None:
        return "No data available."
    if hasattr(result, "empty") and getattr(result, "empty", False):
        return "No data available."
    if hasattr(result, "to_csv"):
        try:
            return result.to_csv(index=False)
        except Exception as exc:  # E3: never silent — a failed table render
            # degrades to str(), but the failure itself must be observable.
            logger.warning("[dataflow] to_csv render failed (%s); falling back to str()", exc)
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
        "tushare_pro": _lazy_callable(".tushare_financials", "get_tushare_balance_sheet"),
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_balance_sheet"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_balance_sheet"),
        "legacy_yfinance": _lazy_callable(".y_finance", "get_balance_sheet"),
        "legacy_alpha_vantage": _lazy_callable(".alpha_vantage", "get_balance_sheet"),
    },
    "get_cashflow": {
        "tushare_pro": _lazy_callable(".tushare_financials", "get_tushare_cashflow"),
        "ths_data": _lazy_callable(".akshare_interface", "get_akshare_cashflow"),
        "legacy_akshare": _lazy_callable(".akshare_interface", "get_akshare_cashflow"),
        "legacy_yfinance": _lazy_callable(".y_finance", "get_cashflow"),
        "legacy_alpha_vantage": _lazy_callable(".alpha_vantage", "get_cashflow"),
    },
    "get_income_statement": {
        "tushare_pro": _lazy_callable(".tushare_financials", "get_tushare_income_statement"),
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
    "get_announcements": {
        "cninfo_official": _lazy_callable(".cninfo_announcements", "get_cninfo_announcements"),
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
    "fundamental_data": "tushare_pro,ths_data,legacy_akshare,legacy_yfinance",
    "news_data": "ths_data,baidu_finance,legacy_akshare,legacy_yfinance",
    "announcement_data": "cninfo_official",
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


def _tushare_enabled() -> bool:
    """Require an explicit opt-in before using the token-backed provider."""
    value = os.getenv("TUSHARE_ENABLED", "").strip().lower()
    if not value:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except Exception:
            pass
        value = os.getenv("TUSHARE_ENABLED", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


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
    if category == "fundamental_data" and not _tushare_enabled():
        configured = ",".join(
            item for item in configured.split(",") if _normalize_vendor_name(item) != "tushare_pro"
        )
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


_DATE_ARGUMENTS = {
    "get_stock_data": (2,),
    "get_indicators": (2,),
    "get_news": (2,),
    "get_global_news": (0,),
    "get_fundamentals": (1,),
    "get_balance_sheet": (2,),
    "get_cashflow": (2,),
    "get_income_statement": (2,),
    "get_announcements": (1, 2),
    "get_cn_policy_news": (0,),
    "get_cn_tech_sector_news": (1,),
    "get_cn_new_energy_news": (1,),
    "get_cn_pharma_news": (1,),
    "get_cn_real_estate_news": (0,),
    "get_cn_fintech_news": (1,),
    "get_cn_limit_up_stocks": (0,),
}


def _clamp_vendor_dates(method: str, args: tuple, kwargs: dict) -> tuple[tuple, dict]:
    """Prevent model-generated vendor dates from exceeding the run cutoff."""
    cutoff_text = get_config().get("trade_date")
    if not cutoff_text:
        return args, kwargs
    try:
        cutoff = date.fromisoformat(str(cutoff_text)[:10])
    except (TypeError, ValueError):
        return args, kwargs

    bounded_args = list(args)
    changed = False
    for index in _DATE_ARGUMENTS.get(method, ()):
        if index >= len(bounded_args) or bounded_args[index] is None:
            continue
        try:
            requested = date.fromisoformat(str(bounded_args[index])[:10])
        except (TypeError, ValueError):
            continue
        if requested > cutoff:
            logger.warning(
                "[PIT] clamped %s argument %s from %s to %s",
                method,
                index,
                bounded_args[index],
                cutoff.isoformat(),
            )
            bounded_args[index] = cutoff.isoformat()
            changed = True

    keyword_names = {
        "end_date": "end_date",
        "curr_date": "curr_date",
        "trade_date": "trade_date",
    }
    bounded_kwargs = dict(kwargs)
    for key in keyword_names:
        value = bounded_kwargs.get(key)
        if value is None:
            continue
        try:
            requested = date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            continue
        if requested > cutoff:
            logger.warning(
                "[PIT] clamped %s keyword %s from %s to %s",
                method,
                key,
                value,
                cutoff.isoformat(),
            )
            bounded_kwargs[key] = cutoff.isoformat()
            changed = True

    if not changed:
        return args, kwargs
    return tuple(bounded_args), bounded_kwargs


def route_to_vendor(method: str, *args, **kwargs):
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [item.strip() for item in vendor_config.split(",") if item.strip()]
    explicit_single_vendor = len(primary_vendors) == 1

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")
    args, kwargs = _clamp_vendor_dates(method, args, kwargs)

    registered = VENDOR_METHODS[method]
    fallback_vendors: List[str] = []
    for vendor in primary_vendors + list(registered.keys()):
        normalized = _normalize_vendor_name(vendor)
        if normalized and normalized not in fallback_vendors:
            fallback_vendors.append(normalized)

    optional_vendor_errors = []
    runtime_errors = []
    placeholder_results = []
    attempted_sources = set()

    for vendor in fallback_vendors:
        impl_func = registered.get(vendor)
        if impl_func is None and vendor in VENDOR_ALIASES:
            impl_func = registered.get(VENDOR_ALIASES[vendor])
        if impl_func is None:
            if vendor in VENDOR_LIST:
                optional_vendor_errors.append(f"{vendor}: not registered for {method}")
                continue

        source_key = getattr(impl_func, "_vendor_source", None)
        if source_key is not None and source_key in attempted_sources:
            logger.info(
                "[dataflow:%s] skipping duplicate implementation for vendor %s",
                method,
                vendor,
            )
            continue
        if source_key is not None:
            attempted_sources.add(source_key)

        started = time.perf_counter()
        try:
            result = impl_func(*args, **kwargs)
            if isinstance(result, str) and _looks_like_unavailable(result):
                excerpt = " ".join(result.split())[:180]
                placeholder_results.append(f"{vendor}: {excerpt}")
                VENDOR_HEALTH.record(
                    vendor,
                    status=classify_provider_text(result),
                    elapsed=time.perf_counter() - started,
                    error=excerpt,
                )
                logger.warning(
                    "[dataflow:%s] vendor %s returned placeholder; trying fallback",
                    method,
                    vendor,
                )
                continue
            VENDOR_HEALTH.record(vendor, status="ok", elapsed=time.perf_counter() - started)
            return result
        except ImportError as exc:
            safe_error = redact_error(f"{type(exc).__name__}: {exc}")
            VENDOR_HEALTH.record(
                vendor,
                status="not_configured",
                elapsed=time.perf_counter() - started,
                error=safe_error,
            )
            optional_vendor_errors.append(f"{vendor}: {safe_error}")
            continue
        except Exception as exc:
            if _is_rate_limit_error(exc):
                VENDOR_HEALTH.record(
                    vendor,
                    status="rate_limited",
                    elapsed=time.perf_counter() - started,
                    error="rate limited",
                )
                runtime_errors.append(f"{vendor}: rate limited")
                logger.warning(
                    "[dataflow:%s] vendor %s rate limited; trying fallback",
                    method,
                    vendor,
                )
                continue
            safe_error = redact_error(f"{type(exc).__name__}: {exc}")
            VENDOR_HEALTH.record(
                vendor,
                status=classify_exception(exc),
                elapsed=time.perf_counter() - started,
                error=safe_error,
            )
            if explicit_single_vendor:
                raise
            runtime_errors.append(f"{vendor}: {safe_error}")
            logger.warning(
                "[dataflow:%s] vendor %s failed (%s); trying fallback",
                method,
                vendor,
                safe_error,
            )
            continue

    detail_parts = []
    if runtime_errors:
        detail_parts.append(f"runtime failures: {'; '.join(runtime_errors)}")
    if optional_vendor_errors:
        detail_parts.append(f"optional vendor failures: {'; '.join(optional_vendor_errors)}")
    if placeholder_results:
        detail_parts.append(f"placeholder responses: {'; '.join(placeholder_results)}")
    detail = " | ".join(detail_parts) if detail_parts else "no registered vendors"
    return (
        f"[DATA_UNAVAILABLE] method={method}; no vendor returned usable data. "
        f"Attempts: {detail}. Treat this result as unverified and do not infer "
        "company facts from it."
    )


# NOTE (2026-08-16): an abandoned RAG-enhancement hook (route_to_vendor_with_rag
# and helpers) lived here. It had zero callers — the live RAG integration is
# tradingagents/agents/utils/rag_news_tools.py and rag/rag_middleware.py, which
# call plain route_to_vendor(). Its module-level import of the rag package was
# one edge of the interface -> rag -> cn_news_retriever -> tools -> interface
# cycle; removing the dead code breaks that cycle at the import-graph level.
