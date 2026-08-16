"""TradingAgents unified CLI entry point.

Usage:
    python -m tradingagents              -- interactive main menu
    python -m tradingagents analyze     -- Stage 2: deep multi-agent analysis
    python -m tradingagents screener    -- Stage 1: stock candidate screening
    python -m tradingagents --version
    python -m tradingagents --info
"""

from __future__ import annotations

import typer

from tradingagents import __version__
from tradingagents.ui.theme import TRADING_THEME
from tradingagents.ui.terminal_mascot import print_komo

# Create app with custom theme
app = typer.Typer(
    name="TradingAgents",
    help="TradingAgents CLI: Multi-Agents LLM Financial Trading Framework for A-share stocks.",
    add_completion=True,
    no_args_is_help=False,
    rich_markup_mode="rich",
)


# Subcommand: analyze (Stage 2)
@app.command("analyze")
def analyze_cmd(
    ticker: str = typer.Option(None, "--ticker", "-t", help="Ticker symbol to analyze"),
    date: str = typer.Option(None, "--date", "-d", help="Analysis date (YYYY-MM-DD)"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Interactive mode"),
):
    """Stage 2: Deep multi-agent analysis of a single stock.

    Launches the full TradingAgents pipeline (Analysts -> Research -> Trading -> Risk -> Portfolio).

    With --no-interactive, --ticker (and optionally --date) run directly with default settings.
    """
    from cli.analyze.app import run as analyze_run

    if interactive or not ticker:
        analyze_run()
        return

    # Non-interactive mode: assemble defaults and execute directly.
    from datetime import datetime

    from cli.analyze.run_impl import run_analysis
    from cli.models import AnalystType
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.ui.summary import print_summary

    config = {
        "ticker": ticker,
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "output_language": "English",
        "analysts": list(AnalystType),
        "research_depth": 1,
        "llm_provider": DEFAULT_CONFIG["llm_provider"],
        "backend_url": DEFAULT_CONFIG.get("backend_url"),
        "shallow_thinking_model": DEFAULT_CONFIG["quick_think_llm"],
        "deep_thinking_model": DEFAULT_CONFIG["deep_think_llm"],
        "thinking_level": None,
        "reasoning_effort": None,
        "anthropic_effort": None,
    }
    result = run_analysis(config)
    print_summary(result, module_type="analyzer")


# Subcommand: screener (Stage 1) — registered as a sub-app so that
# `python -m tradingagents screener run --date ...` works natively
# without any sys.argv rewriting.
from cli.screener.app import screener_app  # noqa: E402

app.add_typer(screener_app, name="screener")


@app.command("report")
def report_cmd(
    path: str = typer.Argument("reports/", help="Path to HTML report or reports directory."),
):
    """Open HTML report in browser.

    Usage: python -m tradingagents report [PATH]
    """
    from cli.report_viewer import view_report

    view_report(path)


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
