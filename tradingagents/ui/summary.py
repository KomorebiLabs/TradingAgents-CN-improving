"""TradingAgents post-execution summary page.

Displays results after Screener or Analyzer completion, with optional report saving and display.
"""

from __future__ import annotations
import time
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.markdown import Markdown
from tradingagents.ui.theme import TRADING_THEME

console = Console(theme=TRADING_THEME)


def print_analyzer_summary(result: Dict[str, Any]) -> None:
    """Print the Analyzer execution summary.
    
    Args:
        result: Dictionary containing:
            - ticker: str
            - decision: str (BUY/SELL/HOLD/etc)
            - confidence: int (0-100)
            - elapsed_time: float (seconds)
            - llm_calls: int
            - tool_calls: int
            - tokens_in: int
            - tokens_out: int
            - report_path: Path (optional)
            - final_state: dict (optional)
    """
    console.print()
    console.print(Rule("[bold green]Analysis Complete[/bold green]", style="green"))
    console.print()

    # Summary Panel
    summary_table = Table(box=box.MINIMAL, show_header=False, padding=(0, 1))
    summary_table.add_column("Key", style="cyan", width=20)
    summary_table.add_column("Value", style="white", width=50)

    summary_table.add_row("Ticker", result.get("ticker", "N/A"))
    
    decision = result.get("decision", "N/A")
    decision_style = {
        "BUY": "bold green",
        "SELL": "bold red",
        "HOLD": "bold yellow",
    }.get(decision.upper() if isinstance(decision, str) else "", "white")
    summary_table.add_row("Decision", f"[{decision_style}]{decision}[/{decision_style}]")
    
    confidence = result.get("confidence", 0)
    conf_bar = "█" * (confidence // 10) + "░" * (10 - confidence // 10)
    conf_color = "green" if confidence >= 70 else "yellow" if confidence >= 40 else "red"
    summary_table.add_row("Confidence", f"[{conf_color}]{conf_bar}[/{conf_color}] {confidence}%")

    elapsed = result.get("elapsed_time", 0)
    mins, secs = divmod(int(elapsed), 60)
    summary_table.add_row("Execution Time", f"{mins:02d}:{secs:02d}")
    summary_table.add_row("LLM Calls", str(result.get("llm_calls", 0)))
    summary_table.add_row("Tool Calls", str(result.get("tool_calls", 0)))
    
    tokens_in = result.get("tokens_in", 0)
    tokens_out = result.get("tokens_out", 0)
    summary_table.add_row("Tokens In", _fmt_tokens(tokens_in))
    summary_table.add_row("Tokens Out", _fmt_tokens(tokens_out))

    console.print(Panel(
        summary_table,
        title="[bold cyan]TradingAgents Analysis Summary[/bold cyan]",
        border_style="green",
        padding=(1, 2),
    ))

    # Report path
    report_path = result.get("report_path")
    if report_path and Path(report_path).exists():
        console.print(f"\n[green]✓ Report saved to:[/green] {report_path}")

    console.print()

    # Display full report
    if Confirm.ask("[cyan]Display full report on screen?[/cyan]", default=True):
        _display_full_report(result)


def _display_full_report(result: Dict[str, Any]) -> None:
    """Display the full analysis report section by section."""
    final_state = result.get("final_state", {})
    
    console.print()
    console.print(Rule("[bold green]Complete Analysis Report[/bold green]", style="bold green"))

    def show_section(title: str, content: Any, border: str = "blue") -> None:
        if not content:
            return
        text = content if isinstance(content, str) else str(content)
        if len(text.strip()) < 5:
            return
        console.print(Panel(
            Markdown(text),
            title=f"[bold]{title}[/bold]",
            border_style=border,
            padding=(1, 2),
        ))

    # I. Analyst Team Reports
    analyst_reports = [
        ("Market Analyst", final_state.get("market_report")),
        ("Social Analyst", final_state.get("sentiment_report")),
        ("News Analyst", final_state.get("news_report")),
        ("Fundamentals Analyst", final_state.get("fundamentals_report")),
    ]
    has_any = False
    for name, content in analyst_reports:
        if content:
            has_any = True
            break
    if has_any:
        console.print(Panel("[bold]I. Analyst Team Reports[/bold]", border_style="cyan"))
        for name, content in analyst_reports:
            if content:
                show_section(name, content, "blue")

    # II. Research Team
    debate = final_state.get("investment_debate_state", {})
    if any(debate.get(k) for k in ["bull_history", "bear_history", "judge_decision"]):
        console.print(Panel("[bold]II. Research Team Decision[/bold]", border_style="magenta"))
        if debate.get("bull_history"):
            show_section("Bull Researcher", debate["bull_history"], "blue")
        if debate.get("bear_history"):
            show_section("Bear Researcher", debate["bear_history"], "blue")
        if debate.get("judge_decision"):
            show_section("Research Manager", debate["judge_decision"], "blue")

    # III. Trading Team
    if final_state.get("trader_investment_plan"):
        console.print(Panel("[bold]III. Trading Team Plan[/bold]", border_style="yellow"))
        show_section("Trader", final_state["trader_investment_plan"], "blue")

    # IV. Risk Management Team
    risk = final_state.get("risk_debate_state", {})
    if any(risk.get(k) for k in ["aggressive_history", "conservative_history", "neutral_history"]):
        console.print(Panel("[bold]IV. Risk Management Team Decision[/bold]", border_style="red"))
        if risk.get("aggressive_history"):
            show_section("Aggressive Analyst", risk["aggressive_history"], "blue")
        if risk.get("conservative_history"):
            show_section("Conservative Analyst", risk["conservative_history"], "blue")
        if risk.get("neutral_history"):
            show_section("Neutral Analyst", risk["neutral_history"], "blue")
        if risk.get("judge_decision"):
            console.print(Panel("[bold]V. Portfolio Manager Decision[/bold]", border_style="green"))
            show_section("Portfolio Manager", risk["judge_decision"], "blue")


def print_screener_summary(result: Dict[str, Any]) -> None:
    """Print the Screener execution summary.
    
    Args:
        result: Dictionary containing:
            - candidates: List[Dict] with name, score, reason
            - date: str
            - output_dir: Path
            - elapsed_time: float
    """
    console.print()
    console.print(Rule("[bold green]Screener Complete[/bold green]", style="green"))
    console.print()

    candidates = result.get("candidates", [])
    
    if candidates:
        table = Table(title="[bold cyan]Top Candidates[/bold cyan]", box=box.MINIMAL, show_header=True)
        table.add_column("#", style="cyan", width=4, justify="center")
        table.add_column("Ticker", style="bold white", width=15)
        table.add_column("Name", style="white", width=22)
        table.add_column("Score", style="green", width=8, justify="center")
        table.add_column("Reason", style="dim", width=35)

        for i, c in enumerate(candidates, 1):
            score = c.get("score", 0)
            score_str = f"{score:.1f}"
            table.add_row(
                str(i),
                c.get("ticker", "N/A"),
                c.get("name", "N/A"),
                score_str,
                c.get("reason", "")[:60],
            )

        console.print(Panel(table, border_style="green", padding=(1, 1)))
    else:
        console.print(Panel(
            "[yellow]No candidates found with current criteria.[/yellow]",
            border_style="yellow",
        ))

    # Metadata
    meta = Table(box=box.MINIMAL, show_header=False)
    meta.add_column("Key", style="cyan", width=20)
    meta.add_column("Value", style="white")
    meta.add_row("Date", result.get("date", "N/A"))
    meta.add_row("Candidates Found", str(len(candidates)))
    elapsed = result.get("elapsed_time", 0)
    mins, secs = divmod(int(elapsed), 60)
    meta.add_row("Execution Time", f"{mins:02d}:{secs:02d}")
    if result.get("output_dir"):
        meta.add_row("Output", str(result["output_dir"]))

    console.print(Panel(meta, title="[bold]Execution Info[/bold]", border_style="cyan", padding=(1, 1)))
    console.print()


def print_summary(result: Dict[str, Any], module_type: str) -> None:
    """Main entry point: dispatch to appropriate summary printer.
    
    Args:
        result: Module-specific result dictionary
        module_type: "analyzer" or "screener"
    """
    if module_type == "analyzer":
        print_analyzer_summary(result)
    elif module_type == "screener":
        print_screener_summary(result)
    else:
        console.print(f"[yellow]Unknown module type: {module_type}[/yellow]")


# === HTML Export Interface (next phase placeholder) ===

def html_export(result: Dict[str, Any], output_path: Path, module_type: str) -> str:
    """Generate an HTML report from execution results.
    
    This is a PLACEHOLDER for the next phase.
    Currently returns the path, no HTML is generated.
    
    Args:
        result: Execution result dictionary
        output_path: Where to save the HTML file
        module_type: "analyzer" or "screener"
    
    Returns:
        Path to the generated HTML file (or input path if not implemented)
    """
    # TODO (Phase 6): Implement HTML report generation
    # For now, just return the output_path as-is
    console.print(f"[dim]HTML export not yet implemented. Output path: {output_path}[/dim]")
    return str(output_path)


def _fmt_tokens(n: int) -> str:
    """Format token count for display."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1000:
        return f"{n//1000}K"
    return str(n)
