"""`screener run` subcommand.

Usage:
    python -m tradingagents.screener.cli run --date 2026-05-08 --mode MVP
    python -m tradingagents.screener.cli run --tickers 600519,000001 --no-deep
    python -m tradingagents.screener.cli run --universe stocks.txt --output-dir ./output
    python -m tradingagents.screener.cli run --help
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console

from tradingagents.screener import ScreenerEngine

console = Console()

ENV_PREFIX = "TRADINGAGENTS_SCREENER_"


def _get_last_trading_day() -> str:
    """Return the most recent trading day (Mon-Fri)."""
    today = datetime.now()
    weekday = today.weekday()
    days_back = 0 if weekday < 5 else (1 if weekday == 5 else 2)
    last = today - timedelta(days=days_back)
    return last.strftime("%Y-%m-%d")


def _load_tickers_from_file(path: str) -> List[str]:
    """Load ticker codes from a text file (one code per line)."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        console.print(f"[red]Error: Universe file not found: {p}[/red]")
        raise typer.Exit(code=2)
    with open(p, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    if not lines:
        console.print(f"[red]Error: Universe file is empty: {p}[/red]")
        raise typer.Exit(code=2)
    return lines


def _resolve_tickers(
    tickers: Optional[str],
    universe_file: Optional[str],
) -> Optional[List[str]]:
    """Resolve --tickers / --universe into a list of ticker codes."""
    if tickers:
        result = [t.strip() for t in tickers.split(",") if t.strip()]
        if not result:
            console.print("[red]Error: --tickers is empty[/red]")
            raise typer.Exit(code=2)
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

    # P5-1: Get default limits from universe config
    universe_config = SCREENER_UNIVERSE.get(mode, {})
    default_stagea_max = universe_config.get("stagea_max_input", 1000)
    default_stageb_max = universe_config.get("stageb_max_input", 200)

    # Determine universe profile
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
            # P5-1: Focus parameters for FOCUSED mode
            "focus_type": focus_type,
            "focus_value": focus_value,
        },
        "candidates": {
            "max_output": max_stocks,
            "max_output_extended": max_stocks + 2,
            "same_sector_limit": 2,
        },
        # P5-1: Stage limits (can be overridden by CLI)
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
        p = Path.home() / ".tradingagents" / "logs" / "screener"
    p.mkdir(parents=True, exist_ok=True)
    return p


def run(
    mode: str = typer.Option(
        "MVP",
        "--mode",
        "-m",
        help="Screener mode: MVP, EXTENDED, EXPERIMENTAL, FULL, FOCUSED, CUSTOM",
        envvar=f"{ENV_PREFIX}MODE",
    ),
    date: Optional[str] = typer.Option(
        None,
        "--date",
        "-d",
        help="Trade date (YYYY-MM-DD). Defaults to last trading day.",
        envvar=f"{ENV_PREFIX}DATE",
    ),
    tickers: Optional[str] = typer.Option(
        None,
        "--tickers",
        "-t",
        help="Comma-separated stock codes, e.g. 600519,000001,300750",
        envvar=f"{ENV_PREFIX}TICKERS",
    ),
    universe: Optional[str] = typer.Option(
        None,
        "--universe",
        "-u",
        help="Path to a text file containing one stock code per line",
        envvar=f"{ENV_PREFIX}UNIVERSE",
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Directory to write output files (default: ~/.tradingagents/logs/screener/)",
        envvar=f"{ENV_PREFIX}OUTPUT_DIR",
    ),
    output_format: str = typer.Option(
        "auto",
        "--output",
        help="Output format: auto (terminal + JSON), json",
        envvar=f"{ENV_PREFIX}OUTPUT_FORMAT",
    ),
    no_deep: bool = typer.Option(
        False,
        "--no-deep",
        help="Skip Deep Analyzer stage (faster, no LLM calls)",
        envvar=f"{ENV_PREFIX}NO_DEEP",
    ),
    max_stocks: int = typer.Option(
        5,
        "--max-stocks",
        help="Maximum number of final candidate stocks",
        envvar=f"{ENV_PREFIX}MAX_STOCKS",
    ),
    allow_weekend: bool = typer.Option(
        False,
        "--allow-weekend",
        help="Allow running on weekends (normally blocked by runtime guard)",
        envvar=f"{ENV_PREFIX}ALLOW_WEEKEND",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Print verbose progress messages",
        envvar=f"{ENV_PREFIX}VERBOSE",
    ),
    json_output: Optional[str] = typer.Option(
        None,
        "--json-output",
        hidden=True,
        help="(Deprecated, use --output json instead)",
    ),
    # P5-1: New parameters for three-tier mode
    focus_type: Optional[str] = typer.Option(
        None,
        "--focus-type",
        help="FOCUSED mode focus type: sector, theme, index, or file",
        envvar=f"{ENV_PREFIX}FOCUS_TYPE",
    ),
    focus_value: Optional[str] = typer.Option(
        None,
        "--focus-value",
        help="FOCUSED mode focus value: e.g. semiconductor, ai, 000300, or file path",
        envvar=f"{ENV_PREFIX}FOCUS_VALUE",
    ),
    stagea_max_input: Optional[int] = typer.Option(
        None,
        "--stagea-max-input",
        help="Stage A maximum input size (default: auto based on mode)",
        envvar=f"{ENV_PREFIX}STAGEA_MAX_INPUT",
    ),
    stageb_max_input: Optional[int] = typer.Option(
        None,
        "--stageb-max-input",
        help="Stage B maximum input size (default: auto based on mode)",
        envvar=f"{ENV_PREFIX}STAGEB_MAX_INPUT",
    ),
) -> None:
    """Run the Stage 1 Screener to discover top stock candidates.

    Examples:

        # Run with last trading day, CSI index universe, MVP mode
        python -m tradingagents.screener.cli run

        # Run on a specific date with 3 output stocks
        python -m tradingagents.screener.cli run --date 2026-05-08 --max-stocks 3

        # Run on a custom ticker list (no API needed for universe)
        python -m tradingagents.screener.cli run --tickers 600519,000001,300750 --no-deep

        # Run with extended mode, allow weekend
        python -m tradingagents.screener.cli run --mode EXTENDED --allow-weekend

        # Plan 5: Run in FULL mode (near full market)
        python -m tradingagents.screener.cli run --mode FULL

        # Plan 5: Run in FOCUSED mode by index
        python -m tradingagents.screener.cli run --mode FOCUSED --focus-type index --focus-value 000300

        # Plan 5: Run in FOCUSED mode by sector
        python -m tradingagents.screener.cli run --mode FOCUSED --focus-type sector --focus-value semiconductor

        # Plan 5: Run in CUSTOM mode with explicit tickers
        python -m tradingagents.screener.cli run --mode CUSTOM --tickers 600519,000001 --no-deep
    """
    from tradingagents.screener.cli.formatters import (
        console,
        print_dropped_candidates,
        print_executive_summary,
        print_run_config,
        print_ranking_table,
    )

    if json_output:
        output_format = "json"
        console.print(
            "[yellow]Warning: --json-output is deprecated, use --output json instead[/yellow]"
        )

    trade_date = date or _get_last_trading_day()

    try:
        datetime.strptime(trade_date, "%Y-%m-%d")
    except ValueError:
        console.print(f"[red]Error: Invalid date format: {trade_date} (expected YYYY-MM-DD)[/red]")
        raise typer.Exit(code=2)

    # P5-1: Updated valid modes to include FULL/FOCUSED/CUSTOM
    valid_modes = ("MVP", "EXTENDED", "EXPERIMENTAL", "FULL", "FOCUSED", "CUSTOM")
    if mode not in valid_modes:
        console.print(f"[red]Error: Invalid mode: {mode} (expected one of {valid_modes})[/red]")
        raise typer.Exit(code=2)

    # P5-1: CUSTOM mode requires tickers or universe
    if mode == "CUSTOM" and not tickers and not universe:
        console.print("[red]Error: CUSTOM mode requires --tickers or --universe[/red]")
        raise typer.Exit(code=2)

    custom_tickers = _resolve_tickers(tickers, universe)

    # P5-1: Print run config with new parameters
    if verbose:
        print_run_config(
            mode=mode,
            trade_date=trade_date,
            tickers=custom_tickers,
            universe_file=universe,
            enable_deep=not no_deep,
            max_stocks=max_stocks,
            focus_type=focus_type,
            focus_value=focus_value,
            stagea_max_input=stagea_max_input,
            stageb_max_input=stageb_max_input,
        )

    config = _build_cli_config(
        mode=mode,
        custom_tickers=custom_tickers,
        enable_deep=not no_deep,
        max_stocks=max_stocks,
        allow_weekend=allow_weekend,
        focus_type=focus_type,
        focus_value=focus_value,
        stagea_max_input=stagea_max_input,
        stageb_max_input=stageb_max_input,
    )

    out_dir = _resolve_output_dir(output_dir)

    # P5-1/P6-5: Enhanced startup message with stage limits
    stagea_limit = config.get("stagea_max_input", "auto")
    stageb_limit = config.get("stageb_max_input", "auto")
    start_time = time.time()

    # P6-5: Print execution header
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
        engine = ScreenerEngine(config=config)
        console.print("[cyan]▶ Universe -> Stage A -> Stage B -> Merger -> Report[/cyan]")
        console.print()
        result = engine.run(
            mode=mode,
            trade_date=trade_date,
            enable_deep_analysis=not no_deep,
            persist_outputs=True,
        )
    except RuntimeError as e:
        console.print(f"[red]Runtime error:[/red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(code=1)

    elapsed = time.time() - start_time

    if output_format == "json":
        data = _serialize_for_output(result)
        json_path = out_dir / f"screener_{trade_date}_{result.run_id[:8]}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        console.print(f"[green]JSON output written to:[/green] {json_path}")
        raise typer.Exit(code=0)

    print_executive_summary(result, trade_date, str(out_dir))
    print_dropped_candidates(result.dropped_candidates or [])

    data = _serialize_for_output(result)
    json_path = out_dir / f"screener_{trade_date}_{result.run_id[:8]}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    console.print(f"[green]JSON output written to:[/green] {json_path}")

    # Generate HTML report
    try:
        from tradingagents.commands.report import generate_html_report
        report_data = {
            "candidates": [
                {
                    "ticker": c.get("ticker", ""),
                    "name": c.get("name", ""),
                    "signal": c.get("signal", "HOLD"),
                    "score": c.get("score", 0.0),
                    "key_reasons": c.get("key_reasons", []),
                }
                for c in data.get("ranking", [])
            ],
            "mode": mode,
            "date": trade_date,
        }
        html_path = out_dir / f"screener_{trade_date}.html"
        generate_html_report(
            title=f"Screener Report - {trade_date}",
            results=report_data,
            output_path=html_path,
            template="screener",
        )
        console.print(f"[green]HTML report:[/green] {html_path.resolve()}")
    except Exception as e:
        console.print(f"[dim]HTML report skipped: {e}[/dim]")

    # P6-6: Enhanced completion page
    console.print()
    console.print(Panel.fit(
        f"[bold green]✓ Screener Completed[/bold green]",
        border_style="green",
        padding=(0, 1),
    ))
    console.print()
    console.print(f"[cyan]Candidates found:[/cyan] {len(result.candidates)}")
    console.print(f"[cyan]Execution time:[/cyan] {elapsed:.1f}s")
    console.print()
    console.print(f"[dim]Report:[/dim] {json_path}")
    console.print()
    console.print("[dim]Next steps:[/dim]")
    console.print("  • Review candidates in the output report")
    console.print("  • Use Deep Analyzer for detailed analysis")
    console.print("  • Continue with TradingAgents main workflow")

    raise typer.Exit(code=0)
