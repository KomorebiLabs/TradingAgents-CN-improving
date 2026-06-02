"""TradingAgents unified CLI entry point.

Usage:
    python -m tradingagents              -- interactive main menu
    python -m tradingagents analyze     -- Stage 2: deep multi-agent analysis (original cli/main.py)
    python -m tradingagents screener    -- Stage 1: stock candidate screening
    python -m tradingagents --version
    python -m tradingagents --info
    python -m tradingagents config show
"""

from __future__ import annotations

import sys

import typer

from tradingagents.ui.theme import TRADING_THEME
from tradingagents.ui.terminal_mascot import print_komo

__version__ = "2.0.0"

# Create app with custom theme
app = typer.Typer(
    name="TradingAgents",
    help="TradingAgents CLI: Multi-Agents LLM Financial Trading Framework for A-share stocks.",
    add_completion=True,
    no_args_is_help=False,
    rich_markup_mode="rich",
)


# Subcommand: analyze (Stage 2 - original cli/main.py logic)
@app.command("analyze")
def analyze_cmd(
    ticker: str = typer.Option(None, "--ticker", "-t", help="Ticker symbol to analyze"),
    date: str = typer.Option(None, "--date", "-d", help="Analysis date (YYYY-MM-DD)"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Interactive mode"),
):
    """Stage 2: Deep multi-agent analysis of a single stock.

    Launches the full TradingAgents pipeline (Analysts -> Research -> Trading -> Risk -> Portfolio).
    This is the original `python -m cli.main` functionality.
    """
    # Prefer new unified CLI (cli.analyze.app) over old commands layer
    try:
        from cli.analyze.app import run as analyze_run
        analyze_run()
    except (ImportError, AttributeError):
        from tradingagents.commands.analyze import run_analyze
        run_analyze(ticker=ticker, date=date, interactive=interactive)


# Subcommand: screener (Stage 1 - existing tradingagents/screener/cli)
@app.command("screener")
def screener_cmd(
    ctx: typer.Context,
):
    """Stage 1: A-share stock candidate screening.

    Discovers top stock candidates through multi-strategy screening.
    Usage: python -m tradingagents screener [run] [OPTIONS]

    Examples:
        python -m tradingagents screener                           -- interactive wizard
        python -m tradingagents screener run --date 2026-05-18   -- quick run
        python -m tradingagents screener run --tickers 600519,000001
    """
    from tradingagents.screener.cli.app import app as screener_app

    remaining_args = sys.argv[2:]
    sys.argv = ["screener"] + remaining_args
    screener_app()


@app.command("report")
def report_cmd(
    path: str = typer.Argument("reports/", help="Path to HTML report or reports directory."),
):
    """Open HTML report in browser.

    Opens a TradingAgents HTML report for viewing.
    Usage: python -m tradingagents report [PATH]
    """
    try:
        from tradingagents.commands.report import view_report
        view_report(path)
    except ImportError:
        from rich.console import Console
        console = Console()
        console.print("[yellow]Report viewer not available (module not found).[/yellow]")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version info"),
    info: bool = typer.Option(False, "--info", help="Show system info and module status"),
):
    """TradingAgents CLI - Interactive main menu when run without subcommand."""
    if version:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        console = Console(theme=TRADING_THEME)
        print_komo()

        version_panel = Panel(
            "[bold cyan]TradingAgents[/bold cyan] - Multi-Agents LLM Financial Trading Framework\n\n"
            f"[green]Version:[/green] {__version__}\n"
            "[green]Modules:[/green] Screener (Stage 1) | Analyzer (Stage 2)",
            title="Version Info",
            border_style="cyan",
        )
        console.print(version_panel)
        raise typer.Exit()

    if info:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        import platform
        import sys as _sys

        console = Console(theme=TRADING_THEME)

        table = Table(title="System Info", box=None, show_header=False)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Python", f"{platform.python_version()}")
        table.add_row("Platform", platform.platform())
        table.add_row("CLI Version", __version__)
        table.add_row("Screener", "Available")
        table.add_row("Analyzer", "Available")
        table.add_row("Report (HTML)", "Available")

        console.print(Panel(table, title="System Info", border_style="cyan"))
        raise typer.Exit()

    if ctx.invoked_subcommand is None or ctx.resilient_parsing:
        from cli.main_menu import run_main_menu
        run_main_menu()


if __name__ == "__main__":
    app()
