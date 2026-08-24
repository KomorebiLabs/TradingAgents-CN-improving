"""Capability probing, capability-matrix construction, and probe caching.

One reason to change: probing policy / capability reporting / probe cache
strategy. Pure with respect to vendors — probe targets are passed in as
callables, so this module never imports vendor code.

Extracted from ScreenerDataAccess (data_access.py) during the Phase 4 split.
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.ui.screener_console import console, print_probe_table

__all__ = [
    "ProbeResult",
    "check_libraries",
    "load_tushare_token",
    "classify_probe_exception",
    "probe_single",
    "probe_multi",
    "build_capability_summary",
    "apply_legacy_aliases",
    "build_vendor_baseline",
    "build_strategy_capabilities",
    "run_live_probes",
    "probe_cache_path",
    "load_probe_cache",
    "save_probe_cache",
]


@dataclass
class ProbeResult:
    name: str
    ok: bool
    elapsed: float = 0.0
    shape: Any = None
    detail: str = ""
    classification: str = "unknown"
    vendor: str = ""


def check_libraries() -> Dict[str, bool]:
    libs = {}
    for lib, module_name in [
        ("akshare", "akshare"),
        ("baostock", "baostock"),
        ("tushare", "tushare"),
        ("py_mini_racer", "py_mini_racer"),
    ]:
        try:
            __import__(module_name)
            libs[lib] = True
        except Exception:
            libs[lib] = False
    return libs


def load_tushare_token() -> str:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass
    return os.environ.get("TUSHARE_TOKEN", "")


def classify_probe_exception(text: str) -> str:
    lowered = text.lower()
    if "winerror 10013" in lowered or "winerror 10054" in lowered:
        return "network_blocked"
    if "remote end closed" in lowered or "remote end closed connection" in lowered:
        return "remote_closed"
    if "failed to establish a new connection" in lowered:
        return "connection_failed"
    if "maxretryerror" in lowered or "httpsconnectionpool" in lowered:
        return "network_unreachable"
    if "yfratelimit" in lowered or "too many requests" in lowered:
        return "rate_limited"
    if "unable to open database file" in lowered:
        return "local_runtime_error"
    if "syntaxerror" in lowered or "json" in lowered:
        return "parse_error"
    if "timeout" in lowered or "timed out" in lowered:
        return "timeout"
    return "unknown_error"


def probe_single(name: str, fn: Callable, timeout: float = 30.0) -> ProbeResult:
    """探测单个接口."""
    start = time.time()
    result_queue: queue.Queue = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            result_queue.put((True, fn()), block=False)
        except Exception as exc:
            result_queue.put((False, exc), block=False)

    thread = threading.Thread(
        target=worker,
        name=f"screener-probe-{name}",
        daemon=True,
    )
    thread.start()
    thread.join(max(0.01, float(timeout)))
    if thread.is_alive():
        elapsed = time.time() - start
        return ProbeResult(
            name=name,
            ok=False,
            elapsed=elapsed,
            detail=f"TimeoutError('probe exceeded {timeout:.2f}s')",
            classification="timeout",
            vendor=name.split("_")[0] if "_" in name else name,
        )
    try:
        ok, value = result_queue.get_nowait()
        if not ok:
            raise value
        result = value
        elapsed = time.time() - start
        shape = getattr(result, "shape", None) if result is not None else None
        empty = bool(getattr(result, "empty", False)) if result is not None else True
        ok = shape is not None and not empty
        return ProbeResult(
            name=name,
            ok=ok,
            elapsed=elapsed,
            shape=shape,
            detail=f"shape={shape}, empty={empty}" if shape is not None else f"type={type(result).__name__ if result else 'None'}",
            classification="ok" if ok else "empty",
            vendor=name.split("_")[0] if "_" in name else name,
        )
    except (Exception, queue.Empty) as exc:
        elapsed = time.time() - start
        return ProbeResult(
            name=name,
            ok=False,
            elapsed=elapsed,
            detail=repr(exc),
            classification=classify_probe_exception(repr(exc)),
            vendor=name.split("_")[0] if "_" in name else name,
        )


def probe_multi(module: str, probes: List[tuple]) -> Dict[str, ProbeResult]:
    """探测多个同功能接口, 返回各接口结果."""
    return {name: probe_single(name, fn) for name, fn in probes}


# ---------------------------------------------------------------------------
# Capability summary construction
# ---------------------------------------------------------------------------

def build_capability_summary(
    vendors: Dict[str, Any],
    libs: Dict[str, bool],
    tushare_configured: bool,
) -> Dict[str, Any]:
    """构建不执行 live probe 的能力摘要基底."""
    summary = {
        "akshare_importable": libs["akshare"],
        "baostock_importable": libs["baostock"],
        "tushare_importable": libs["tushare"],
        "py_mini_racer_importable": libs["py_mini_racer"],
        "spot_snapshot_verified": False,
        "hist_fetch_verified": False,
        "concept_list_verified": False,
        "industry_list_verified": False,
        "fund_flow_verified": False,
        "index_spot_verified": False,
        "tick_data_verified": False,
        "spot_primary_vendor": vendors.get("spot_primary", "tencent_direct"),
        "hist_primary_vendor": vendors.get("hist_primary", "tencent_direct"),
        "concept_primary_vendor": vendors.get("concept_primary", "ths"),
        "industry_primary_vendor": vendors.get("industry_primary", "ths"),
        "fund_flow_primary_vendor": vendors.get("fund_flow_primary", "ths"),
        "index_primary_vendor": vendors.get("index_primary", "tencent_direct"),
        "spot_secondary_vendor": vendors.get("spot_secondary", "tencent"),
        "hist_secondary_vendor": vendors.get("hist_secondary", "tencent"),
        "hist_tertiary_vendor": vendors.get("hist_tertiary", "sina"),
        "hist_quaternary_vendor": vendors.get("hist_quaternary", "baostock"),
        "fund_flow_secondary_vendor": vendors.get("fund_flow_secondary", "em"),
        "index_secondary_vendor": vendors.get("index_secondary", "sina"),
        "index_tertiary_vendor": vendors.get("index_tertiary", "tencent"),
        "tushare_configured": bool(tushare_configured),
        "warnings": [],
        "freshness": [],
        "validated": False,
    }
    summary["vendor_baseline"] = build_vendor_baseline(summary, vendors)
    summary["strategy_capabilities"] = build_strategy_capabilities(summary, vendors)
    return summary


def apply_legacy_aliases(summary: Dict[str, Any], vendors: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(summary)
    payload["fund_flow_bulk_verified"] = bool(payload.get("fund_flow_verified", False))
    payload["tencent_hist_verified"] = bool(
        payload.get("probe_results", {}).get("hist_tencent_direct", {}).get("ok", False)
    )
    payload["yfinance_hist_verified"] = bool(
        payload.get("probe_results", {}).get("hist_yfinance", {}).get("ok", False)
    )
    payload["fund_flow_fallback_vendor"] = payload.get("fund_flow_fallback_vendor") or "yfinance"
    payload["concept_list_fallback_vendor"] = payload.get("concept_list_fallback_vendor") or payload.get("concept_secondary_vendor", "")
    payload["hist_fetch_secondary_vendor"] = payload.get("hist_fetch_secondary_vendor") or payload.get("hist_secondary_vendor", "sina")
    payload["hist_fetch_fallback_vendor"] = payload.get("hist_fetch_fallback_vendor") or (
        "yfinance" if vendors.get("enable_yfinance_backup", True) else ""
    )
    payload["vendor_baseline"] = build_vendor_baseline(payload, vendors)
    payload["strategy_capabilities"] = build_strategy_capabilities(payload, vendors)
    return payload


def build_vendor_baseline(summary: Dict[str, Any], vendors: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "history": {
            "primary": summary.get("hist_primary_vendor", "tencent_direct"),
            "secondary": summary.get("hist_secondary_vendor", "tencent"),
            "tertiary": summary.get("hist_tertiary_vendor", "sina"),
            "quaternary": summary.get("hist_quaternary_vendor", "baostock"),
            "last_resort": "yfinance" if vendors.get("enable_yfinance_backup", True) else "",
            "eastmoney_role": "compatibility_only",
        },
        "spot": {
            "primary": summary.get("spot_primary_vendor", "tencent_direct"),
            "secondary": summary.get("spot_secondary_vendor", "tencent"),
            "tertiary": summary.get("spot_tertiary_vendor", "sina"),
        },
        "concept": {
            "primary": summary.get("concept_primary_vendor", "ths"),
            "secondary": summary.get("concept_secondary_vendor", "sina"),
        },
        "industry": {
            "primary": summary.get("industry_primary_vendor", "ths"),
        },
        "fund_flow": {
            "primary": summary.get("fund_flow_primary_vendor", "ths"),
            "secondary": summary.get("fund_flow_secondary_vendor", "em"),
        },
        "index": {
            "primary": summary.get("index_primary_vendor", "tencent_direct"),
            "secondary": summary.get("index_secondary_vendor", "sina"),
            "tertiary": summary.get("index_tertiary_vendor", "tencent"),
        },
        "tick": {
            "primary": "tencent",
            "secondary": "sina",
        },
        "auxiliary": {
            "valuation": "baidu",
            "sentiment": "baidu",
            "news": "baidu",
            "dragon_tiger": "sina",
        },
    }


def build_strategy_capabilities(summary: Dict[str, Any], vendors: Dict[str, Any]) -> Dict[str, Any]:
    hist_probe = summary.get("probe_results", {}).get("hist_tencent_direct", {})
    yfinance_probe = summary.get("probe_results", {}).get("hist_yfinance", {})
    concept_probe = summary.get("probe_results", {}).get("concept_ths", {})
    fund_flow_probe = summary.get("probe_results", {}).get("fund_flow_ths", {})

    technical_ready = bool(
        summary.get("fund_flow_verified", False) and summary.get("hist_fetch_verified", False)
    )
    policy_ready = bool(summary.get("concept_list_verified", False))
    smart_money_ready = bool(summary.get("hist_fetch_verified", False))

    return {
        "technical": {
            "status_hint": "ready" if technical_ready else "degraded",
            "required_capabilities": ["fund_flow", "hist_fetch"],
            "primary_dependencies": {
                "fund_flow": summary.get("fund_flow_primary_vendor", "ths"),
                "hist_fetch": summary.get("hist_primary_vendor", "tencent"),
            },
            "supports_tencent_primary_hist": summary.get("hist_primary_vendor", "tencent_direct") == "tencent_direct",
            "supports_yfinance_last_resort": bool(vendors.get("enable_yfinance_backup", True)),
            "notes": [
                "Technical strategy should treat Tencent history as the canonical CN historical path.",
                "THS fund flow remains required for full technical+flow readiness.",
            ],
        },
        "policy": {
            "status_hint": "ready" if policy_ready else "degraded",
            "required_capabilities": ["concept_list"],
            "primary_dependencies": {
                "concept_list": summary.get("concept_primary_vendor", "ths"),
                "concept_fallback": summary.get("concept_secondary_vendor", "sina"),
                "news_auxiliary": "baidu",
            },
            "supports_tencent_primary_hist": False,
            "supports_yfinance_last_resort": False,
            "concept_source_verified": bool(concept_probe.get("ok", False)),
            "news_source_planned": "baidu",
            "notes": [
                "Policy strategy does not require Tencent history to be ready.",
                "Concept boards remain THS-first, with Sina as compatibility fallback.",
            ],
        },
        "smart_money": {
            "status_hint": "ready" if smart_money_ready else "degraded",
            "required_capabilities": ["hist_fetch"],
            "optional_capabilities": ["fund_flow", "tick_data", "valuation_auxiliary"],
            "primary_dependencies": {
                "hist_fetch": summary.get("hist_primary_vendor", "tencent"),
                "fund_flow": summary.get("fund_flow_primary_vendor", "ths"),
                "tick_data": "tencent",
                "valuation_auxiliary": "baidu",
                "dragon_tiger_auxiliary": "sina",
            },
            "supports_tencent_primary_hist": bool(hist_probe.get("ok", False))
            or summary.get("hist_primary_vendor", "tencent") == "tencent",
            "supports_yfinance_last_resort": bool(vendors.get("enable_yfinance_backup", True)),
            "tencent_hist_verified": bool(hist_probe.get("ok", False)),
            "yfinance_hist_verified": bool(yfinance_probe.get("ok", False)),
            "fund_flow_verified": bool(fund_flow_probe.get("ok", False) or summary.get("fund_flow_verified", False)),
            "notes": [
                "Smart-money minimum viable path is Tencent history plus optional Tencent tick detail.",
                "THS/Sina/Baidu remain enhancement sources rather than hard blockers for MVP.",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Live probe execution
# ---------------------------------------------------------------------------

def run_live_probes(
    base_summary: Dict[str, Any],
    probe_groups: Dict[str, List[tuple]],
    yfinance_probe: Optional[tuple],
    requester,
) -> Dict[str, Any]:
    """执行全量 live probe.

    Args:
        base_summary: capability summary baseline (from build_capability_summary).
        probe_groups: {module_key: [(probe_name, callable), ...]} in display order.
            module_key also names the ``{key}_verified`` summary flag.
        yfinance_probe: optional (name, callable) for the yfinance last-resort probe.
        requester: ThrottledRequester, for final request stats.
    """
    console.print()
    from rich.panel import Panel

    console.print(Panel.fit(
        "[bold cyan]>> DATA PROBE[/bold cyan]  [dim]testing API availability (~10-20s)...[/dim]",
        border_style="cyan",
        padding=(0, 1),
    ))

    summary = dict(base_summary)
    probe_results: Dict[str, ProbeResult] = {}
    warnings: List[str] = []

    for module_key, probes in probe_groups.items():
        console.print(f"[dim]Probing {module_key}...[/dim]", end="\r")
        module_result = probe_multi(module_key, probes)
        probe_results.update(module_result)
        summary[f"{module_key}_verified"] = any(r.ok for r in module_result.values())
        console.print()
        rows = [(name, module_result[name].ok, module_result[name].detail or "") for name, _ in probes]
        print_probe_table(module_key, rows)

    if yfinance_probe is not None:
        name, fn = yfinance_probe
        console.print("[dim]Probing yfinance hist...[/dim]", end="\r")
        yf_result = probe_single(name, fn)
        probe_results[name] = yf_result
        if yf_result.ok:
            warnings.append("[INFO] yfinance historical fallback probe succeeded")
            console.print("[green][OK] yfinance[/green]")
        else:
            console.print("[red][X] yfinance[/red]")
    else:
        console.print("[yellow][-] yfinance skipped[/yellow]")

    failed_count = sum(1 for r in probe_results.values() if not r.ok)
    console.print()
    passed = len(probe_results) - failed_count
    total = len(probe_results)
    console.print(f"[green][OK] DataProbe done[/green]  [cyan]{passed}/{total}[/cyan] passed  [red]{failed_count}[/red] failed")
    summary["probe_results"] = {
        k: {
            "name": v.name,
            "ok": v.ok,
            "elapsed": v.elapsed,
            "shape": v.shape,
            "detail": v.detail,
            "classification": v.classification,
            "vendor": v.vendor,
        }
        for k, v in probe_results.items()
    }
    summary["probed_at"] = datetime.now().isoformat()
    summary["request_stats"] = requester.get_stats()

    for result in probe_results.values():
        if not result.ok:
            warnings.append(
                f"[WARN] {result.name} ({result.vendor}) probe failed: {result.detail[:120]}"
            )

    summary["warnings"] = warnings
    return summary


# ---------------------------------------------------------------------------
# Probe cache
# ---------------------------------------------------------------------------

def probe_cache_path(config: Dict[str, Any]) -> Path:
    cache_root = Path(config.get("data_cache_dir", DEFAULT_CONFIG["data_cache_dir"]))
    candidates = [
        cache_root / "screener",
        Path.cwd() / ".tradingagents" / "cache" / "screener",
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate / "a0_probe_summary_v2.json"
        except OSError:
            continue
    return Path.cwd() / "a0_probe_summary_v2.json"


def load_probe_cache(config: Dict[str, Any], tushare_configured: bool) -> Optional[Dict[str, Any]]:
    cache_file = probe_cache_path(config)
    if not cache_file.exists():
        return None

    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        created_at = payload.get("probed_at")
        ttl_minutes = int(config.get("a0_probe", {}).get("cache_ttl_minutes", 60))
        if created_at:
            probed_at = datetime.fromisoformat(created_at)
            if datetime.now() - probed_at > timedelta(minutes=ttl_minutes):
                return None
        defaults = {
            "spot_snapshot_verified": False,
            "hist_fetch_verified": False,
            "concept_list_verified": False,
            "industry_list_verified": False,
            "fund_flow_verified": False,
            "index_spot_verified": False,
            "tick_data_verified": False,
            "spot_primary_vendor": "tencent_direct",
            "hist_primary_vendor": "tencent_direct",
            "concept_primary_vendor": "ths",
            "industry_primary_vendor": "ths",
            "fund_flow_primary_vendor": "ths",
            "index_primary_vendor": "tencent_direct",
            "baostock_importable": False,
            "tushare_importable": False,
            "py_mini_racer_importable": False,
            "tushare_configured": bool(tushare_configured),
        }
        for k, v in defaults.items():
            payload.setdefault(k, v)
        payload.setdefault("validated", False)
        return payload
    except Exception:
        return None


def save_probe_cache(summary: Dict[str, Any], config: Dict[str, Any]) -> None:
    cache_file = probe_cache_path(config)
    try:
        cache_file.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
