"""TradingAgents Screener execution engine.

Replaces the run_impl from tradingagents.screener.cli.commands.
Handles:
1. ScreenerEngine initialization
2. Configuration building
3. engine.run() with error handling
4. Returns result dict for summary.py
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel

from tradingagents.screener import ScreenerEngine
from tradingagents.ui.theme import TRADING_THEME

console = Console(theme=TRADING_THEME)


def _get_last_trading_day() -> str:
    """Return the most recent session from the cached A-share calendar."""
    from tradingagents.screener.trading_calendar import latest_a_share_trading_day

    return latest_a_share_trading_day(datetime.now().date()).isoformat()


def _load_tickers_from_file(path: str) -> List[str]:
    """Load ticker codes from a text file (one code per line)."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Universe file not found: {p}")
    with open(p, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    if not lines:
        raise ValueError(f"Universe file is empty: {p}")
    return lines


def _resolve_tickers(tickers: Optional[str], universe_file: Optional[str]) -> Optional[List[str]]:
    """Resolve tickers string or universe file into a list of ticker codes."""
    if tickers:
        result = [t.strip() for t in tickers.split(",") if t.strip()]
        if not result:
            raise ValueError("--tickers is empty")
        return result
    if universe_file:
        return _load_tickers_from_file(universe_file)
    return None


def _build_cli_config(
    mode: str,
    custom_tickers: Optional[List[str]],
    enable_deep: bool,
    max_stocks: int,
    allow_weekend: bool,
    focus_type: Optional[str] = None,
    focus_value: Optional[str] = None,
    stagea_max_input: Optional[int] = None,
    stageb_max_input: Optional[int] = None,
) -> Dict[str, Any]:
    """Build the ScreenerEngine config dict from CLI arguments."""
    from tradingagents.screener.config import SCREENER_UNIVERSE

    universe_config = SCREENER_UNIVERSE.get(mode, {})
    default_stagea_max = universe_config.get("stagea_max_input", 1000)
    default_stageb_max = universe_config.get("stageb_max_input", 200)

    if custom_tickers is not None:
        universe_profile = "CUSTOM"
    elif mode in ("FOCUSED",):
        universe_profile = "FOCUSED"
    else:
        universe_profile = mode

    return {
        "mode": mode,
        "run_time": {
            "earliest": "16:30",
            "latest_next_day": "09:00",
            "allow_weekend": allow_weekend,
            "allow_non_trading_day_override": False,
            "allow_experimental_intraday": False,
            "max_data_age_days": 2,
        },
        "universe": {
            "profile": universe_profile,
            "custom_tickers": custom_tickers or [],
            "focus_type": focus_type,
            "focus_value": focus_value,
        },
        "candidates": {
            "max_output": max_stocks,
            "max_output_extended": max_stocks + 2,
            "same_sector_limit": 2,
        },
        "stagea_max_input": stagea_max_input if stagea_max_input is not None else default_stagea_max,
        "stageb_max_input": stageb_max_input if stageb_max_input is not None else default_stageb_max,
        "deep_analyzer": {
            "enable_real_deep_analysis": enable_deep,
            "max_stocks": max_stocks,
            "delay_between_stocks": 2.0,
            "retry_on_failure": True,
            "max_retries": 1,
        },
    }


def _serialize_for_output(result: Any) -> Dict[str, Any]:
    """Serialize ScreenerEngine output to JSON-compatible dict."""
    return {
        "run_id": result.run_id,
        "mode": result.mode,
        "trade_date": result.trade_date,
        "started_at": result.started_at,
        "completed_at": result.completed_at,
        "universe_size": result.universe_size,
        "universe_metadata": result.universe_metadata,
        "candidates": [
            {
                "ticker": c.ticker,
                "name": getattr(c, "company_name", c.ticker),
                "screening_score": c.screening_score,
                "initial_confidence": c.initial_confidence,
                "data_source_verified": c.data_source_verified,
                "signal": _signal_from_score(c.screening_score),
                "degraded": _is_degraded(c),
                "concept_tags": [str(t) for t in (c.concept_tags or [])],
                "risk_flags": [str(r) for r in (c.risk_flags or [])],
                "key_reasons": _extract_key_reasons(c),
            }
            for c in result.candidates
        ],
        "dropped_candidates": [
            {
                "ticker": d.get("ticker", f"dropped_{i}"),
                "company_name": d.get("company_name", d.get("ticker", f"dropped_{i}")),
                "reason": d.get("semantic_decision_summary", ""),
            }
            for i, d in enumerate(result.dropped_candidates or [], 1)
        ],
        "strategy_status": result.strategy_status,
        "data_issues": result.data_issues,
        "metrics": _clean_metrics(result.metrics),
    }


def _signal_from_score(score: Optional[float]) -> str:
    if score is None:
        return "HOLD"
    if score >= 75:
        return "BUY"
    if score >= 60:
        return "HOLD"
    return "SELL"


def _is_degraded(card) -> bool:
    """Check if any SignalEvidence in the card is degraded."""
    if not card.signal_breakdown:
        return False
    return any(e.degraded for e in card.signal_breakdown)


def _extract_key_reasons(card: Any) -> List[str]:
    """Extract human-readable key reasons from a SignalCard."""
    reasons: List[str] = []
    if hasattr(card, "concept_tags") and card.concept_tags:
        reasons.extend(str(t) for t in card.concept_tags[:3])
    snapshot = getattr(card, "evidence_snapshot", {}) or {}
    summary = snapshot.get("semantic_decision_summary", "")
    if summary and len(summary) < 200:
        reasons.append(summary)
    return reasons


def _clean_metrics(metrics: Any) -> Dict[str, Any]:
    """Remove non-serializable objects from metrics."""
    if isinstance(metrics, dict):
        result = {}
        for k, v in metrics.items():
            try:
                json.dumps(v)
                result[k] = v
            except (TypeError, ValueError):
                result[k] = str(v)
        return result
    return {}


def _resolve_output_dir(output_dir: Optional[str]) -> Path:
    """Resolve the output directory path."""
    if output_dir:
        p = Path(output_dir).expanduser().resolve()
    else:
        # Default: project_root/reports/Screener (D盘项目目录)
        project_root = Path(__file__).resolve().parents[2]
        p = project_root / "reports" / "Screener"
    p.mkdir(parents=True, exist_ok=True)
    return p


def run_screener(config: dict) -> dict:
    """Run the Screener and return a result dict for summary.py.

    Args:
        config: Dictionary from cli/screener/app.py containing:
            - mode: str (MVP, EXTENDED, EXPERIMENTAL, FULL, FOCUSED, CUSTOM)
            - trade_date: str (YYYY-MM-DD)
            - tickers: str | None
            - universe: str | None
            - output_dir: str | None
            - no_deep: bool
            - max_stocks: int
            - allow_weekend: bool
            - focus_type: str | None
            - focus_value: str | None

    Returns:
        dict with: candidates, date, output_dir, elapsed_time
    """
    mode = config["mode"]
    trade_date = config["trade_date"]
    tickers = config.get("tickers")
    universe = config.get("universe")
    output_dir = config.get("output_dir")
    no_deep = config.get("no_deep", False)
    max_stocks = config.get("max_stocks", 5)
    allow_weekend = config.get("allow_weekend", False)
    focus_type = config.get("focus_type")
    focus_value = config.get("focus_value")

    # Validate date
    try:
        datetime.strptime(trade_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format: {trade_date} (expected YYYY-MM-DD)")

    # CUSTOM mode requires tickers or universe
    if mode == "CUSTOM" and not tickers and not universe:
        raise ValueError("CUSTOM mode requires tickers or universe file")

    custom_tickers = _resolve_tickers(tickers, universe)

    engine_config = _build_cli_config(
        mode=mode,
        custom_tickers=custom_tickers,
        enable_deep=not no_deep,
        max_stocks=max_stocks,
        allow_weekend=allow_weekend,
        focus_type=focus_type,
        focus_value=focus_value,
        stagea_max_input=config.get("stagea_max_input"),
        stageb_max_input=config.get("stageb_max_input"),
    )

    out_dir = _resolve_output_dir(output_dir)

    stagea_limit = engine_config.get("stagea_max_input", "auto")
    stageb_limit = engine_config.get("stageb_max_input", "auto")
    start_time = time.time()

    console.print()
    console.print(Panel.fit(
        f"[bold cyan]Screener Execution[/bold cyan] | mode={mode} | date={trade_date}",
        border_style="cyan",
        padding=(0, 1),
    ))
    console.print()
    console.print(f"[dim]Stage A limit: {stagea_limit} | Stage B limit: {stageb_limit}[/dim]")
    console.print()

    try:
        engine = ScreenerEngine(config=engine_config)
        console.print("[cyan]▶ Universe -> Stage A -> Stage B -> Merger -> Report[/cyan]")
        console.print()
        console.print("[dim]Executing engine.run() - please wait (10-20 minutes for full run)...[/dim]")
        result = engine.run(
            mode=mode,
            trade_date=trade_date,
            enable_deep_analysis=not no_deep,
            persist_outputs=True,
        )
    except RuntimeError as e:
        raise RuntimeError(f"Runtime error: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error: {e}") from e

    elapsed = time.time() - start_time

    # Save JSON output
    data = _serialize_for_output(result)
    json_path = out_dir / f"screener_{trade_date}_{result.run_id[:8]}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    console.print(f"[green]JSON output written to:[/green] {json_path}")

    # Build return dict for summary
    candidates_out = [
        {
            "ticker": c.get("ticker", ""),
            "name": c.get("name", ""),
            "score": c.get("screening_score", 0.0),
            "signal": c.get("signal", "HOLD"),
            "reason": " | ".join(c.get("key_reasons", [])[:2]),
        }
        for c in data.get("candidates", [])
    ]

    return {
        "candidates": candidates_out,
        "date": trade_date,
        "output_dir": json_path,
        "elapsed_time": elapsed,
    }
