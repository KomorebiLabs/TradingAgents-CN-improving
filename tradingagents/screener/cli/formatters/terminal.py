"""Terminal formatters for screener CLI output."""

from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box


console = Console()


def format_signal_badge(score: float, degraded: bool = False) -> str:
    """Generate a BUY/HOLD/SELL signal badge based on score."""
    if score >= 75:
        badge = "[bold green]BUY[/bold green]"
    elif score >= 60:
        badge = "[yellow]HOLD[/yellow]"
    else:
        badge = "[red]SELL[/red]"

    if degraded:
        badge += " [dim](degraded)[/dim]"

    return badge


def _is_degraded(card) -> bool:
    """Check if any SignalEvidence in the card is degraded."""
    if not hasattr(card, "signal_breakdown") or not card.signal_breakdown:
        return False
    return any(getattr(e, "degraded", False) for e in card.signal_breakdown)


def print_ranking_table(
    candidates: List[Any],
    title: str = "Top Candidates",
    max_rows: int = 10,
) -> None:
    """Print a ranked table of candidates to terminal."""
    if not candidates:
        console.print("[dim]No candidates to display.[/dim]")
        return

    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.ROUNDED,
        title=title,
        title_style="bold green",
    )
    table.add_column("Rank", justify="center", width=5)
    table.add_column("Ticker", style="cyan", width=10)
    table.add_column("Name", style="white", width=15)
    table.add_column("Signal", justify="center", width=8)
    table.add_column("Score", justify="right", width=7)
    table.add_column("Key Reasons", style="dim", overflow="fold")

    for i, card in enumerate(candidates[:max_rows], 1):
        ticker = card.ticker
        name = getattr(card, "name", ticker)
        score = getattr(card, "screening_score", None)
        score_str = f"{score:.1f}" if score is not None else "N/A"
        degraded = _is_degraded(card)

        # Extract key reasons from evidence
        reasons: List[str] = []
        if hasattr(card, "concept_tags") and card.concept_tags:
            reasons.extend(str(t) for t in card.concept_tags[:2])
        if hasattr(card, "evidence_snapshot"):
            summary = card.evidence_snapshot.get("semantic_decision_summary", "")
            if summary and len(summary) > 60:
                summary = summary[:57] + "..."
            if summary:
                reasons.append(summary)

        reasons_str = " | ".join(reasons[:2]) if reasons else "—"

        signal = format_signal_badge(score or 0, degraded)

        table.add_row(
            str(i),
            ticker,
            name,
            signal,
            score_str,
            reasons_str,
        )

    console.print()
    console.print(table)


def print_executive_summary(
    result: Any,
    trade_date: str,
    output_dir: Optional[str] = None,
) -> None:
    """Print a compact executive summary to terminal."""
    candidates = result.candidates
    dropped = result.dropped_candidates
    metrics = result.metrics

    # Header
    console.print()
    console.print(
        Panel.fit(
            f"[bold green]Screener Run Complete[/bold green]  |  [cyan]{trade_date}[/cyan]  |  "
            f"[dim]Mode: {result.mode}[/dim]",
            border_style="green",
        )
    )

    # Quick stats row
    stagea_audit = metrics.get("effective_config_used", {}).get("stagea_audit", {})
    if stagea_audit:
        stagea_info = (
            f"[cyan]StageA:[/cyan] {stagea_audit.get('stagea_pass_count', '?')}/{stagea_audit.get('stagea_input_count', '?')}  "
        )
    else:
        stagea_info = ""

    stats_text = (
        f"[cyan]Universe:[/cyan] {metrics.get('universe_size', '?')} stocks  |  "
        f"{stagea_info}"
        f"[cyan]Strategy A:[/cyan] {metrics.get('strategy_a_candidates', '?')}  |  "
        f"[cyan]Strategy B:[/cyan] {metrics.get('strategy_b_candidates', '?')}  |  "
        f"[cyan]Strategy C:[/cyan] {metrics.get('strategy_c_candidates', '?')}  |  "
        f"[cyan]Final:[/cyan] {len(candidates)}  |  "
        f"[cyan]Dropped:[/cyan] {len(dropped)}  |  "
        f"[cyan]Time:[/cyan] {metrics.get('elapsed_seconds_total', 0):.1f}s"
    )
    console.print(stats_text)
    console.print()

    # Top picks
    if candidates:
        print_ranking_table(candidates, title=f"Top {len(candidates)} Picks", max_rows=len(candidates))
    else:
        console.print("[yellow]No candidates passed the merger filters.[/yellow]")
        console.print("[dim]Tip: Check dropped_candidates in the output JSON for details.[/dim]")

    # Data quality warnings
    degraded = metrics.get("degraded_strategies", [])
    if degraded:
        console.print()
        console.print(
            f"[yellow]![/yellow] [dim]Degraded strategies: {', '.join(degraded)}[/dim]"
        )

    # Output location
    if output_dir:
        console.print()
        console.print(f"[dim]Report saved to:[/dim] {output_dir}")


def print_dropped_candidates(
    dropped: List[Any],
    max_rows: int = 5,
) -> None:
    """Print a compact table of dropped candidates."""
    if not dropped:
        return

    console.print()
    console.print("[yellow]Dropped Candidates[/yellow]:")

    table = Table(
        show_header=True,
        header_style="bold red",
        box=box.SIMPLE,
    )
    table.add_column("Ticker", style="red", width=10)
    table.add_column("Name", style="white", width=12)
    table.add_column("Reason", style="dim", overflow="fold")

    for item in dropped[:max_rows]:
        ticker = item.get("ticker", "?")
        name = item.get("company_name", "?")
        reason = item.get("reason", item.get("semantic_decision_summary", "unknown"))
        if len(reason) > 60:
            reason = reason[:57] + "..."
        table.add_row(ticker, name, reason)

    console.print(table)
    if len(dropped) > max_rows:
        console.print(f"[dim]... and {len(dropped) - max_rows} more[/dim]")


def print_run_config(
    mode: str,
    trade_date: str,
    tickers: Optional[List[str]] = None,
    universe_file: Optional[str] = None,
    enable_deep: bool = True,
    max_stocks: int = 3,
    # P5-1: New parameters
    focus_type: Optional[str] = None,
    focus_value: Optional[str] = None,
    stagea_max_input: Optional[int] = None,
    stageb_max_input: Optional[int] = None,
) -> None:
    """Print the run configuration before starting."""
    items = [
        f"[cyan]mode:[/cyan] {mode}",
        f"[cyan]date:[/cyan] {trade_date}",
    ]
    if tickers:
        items.append(f"[cyan]tickers:[/cyan] {', '.join(tickers[:5])}" + (" ..." if len(tickers) > 5 else ""))
    elif universe_file:
        items.append(f"[cyan]universe:[/cyan] {universe_file}")
    else:
        items.append(f"[cyan]universe:[/cyan] CSI index constituents")

    # P5-1: Show focus parameters for FOCUSED mode
    if mode == "FOCUSED" and focus_type and focus_value:
        items.append(f"[cyan]focus:[/cyan] {focus_type}={focus_value}")

    items.append(f"[cyan]deep_analysis:[/cyan] {'enabled' if enable_deep else 'disabled'}")
    if enable_deep:
        items.append(f"[cyan]max_deep_stocks:[/cyan] {max_stocks}")

    # P5-1: Show stage limits
    if stagea_max_input:
        items.append(f"[cyan]stagea_max:[/cyan] {stagea_max_input}")
    if stageb_max_input:
        items.append(f"[cyan]stageb_max:[/cyan] {stageb_max_input}")

    config_text = "  |  ".join(items)
    console.print()
    console.print(f"[dim]{config_text}[/dim]")
    console.print()
