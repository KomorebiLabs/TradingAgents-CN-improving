"""TradingAgents CLI - Main Menu (Bloomberg-style dashboard).

This module provides the interactive main menu for the TradingAgents CLI.
It is the central hub from which all modules (Screener, Analyzer, Report)
are launched, and returns to the menu after each module completes.
"""
from __future__ import annotations

from pathlib import Path

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from tradingagents.ui.terminal_mascot import print_komo
from tradingagents.ui.theme import TRADING_THEME


def run_main_menu() -> None:
    """Show Bloomberg-style main menu, execute selected module, return to menu on completion."""
    console = Console(theme=TRADING_THEME)

    while True:
        # Print Komo mascot
        print_komo()

        # Print welcome banner (read from cli/static/welcome.txt)
        welcome_path = Path(__file__).parent / "static" / "welcome.txt"
        if welcome_path.exists():
            console.print(welcome_path.read_text(encoding="utf-8"))

        # Main dashboard header
        console.print(
            Panel(
                "[bold cyan]TradingAgents CLI  -  Main Dashboard[/bold cyan]\n[dim]A-share Stock Intelligence Platform[/dim]",
                border_style="cyan",
            )
        )
        console.print()

        # Menu table
        from rich.table import Table

        table = Table(box=None, show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=4, justify="center")
        table.add_column("Module", style="bold white", width=20)
        table.add_column("Description", style="dim", width=45)
        table.add_column("Command", style="green", width=35)

        table.add_row(
            "1",
            "[bold]Screener[/bold]",
            "Stage 1: A-share candidate discovery",
            "python -m tradingagents screener",
        )
        table.add_row(
            "2",
            "[bold]Analyzer[/bold]",
            "Stage 2: Deep multi-agent analysis",
            "python -m tradingagents analyze",
        )
        table.add_row(
            "3",
            "[bold]Report[/bold]",
            "HTML report viewer",
            "python -m tradingagents report",
        )
        table.add_row("Q", "[bold]Quit[/bold]", "Exit CLI", "")

        console.print(table)
        console.print()

        choice = Prompt.ask(
            "[cyan]Select module[/cyan] (1/2/3/Q)",
            choices=["1", "2", "3", "Q", "q"],
            default="Q",
        )

        if choice == "1":
            _run_screener()
        elif choice == "2":
            _run_analyzer()
        elif choice == "3":
            _run_report_viewer()
        else:
            console.print("[dim]Goodbye![/dim]")
            return

        # After module completes, ask to return to menu
        if not Confirm.ask("[cyan]返回主菜单？[/cyan]", default=True):
            console.print("[dim]Goodbye![/dim]")
            return


def _run_screener() -> None:
    """Run the Screener CLI module (Stage 1)."""
    # Try new location first (cli.screener.app.run), fall back to old
    try:
        from cli.screener.app import run as screener_run

        screener_run()
    except (ImportError, AttributeError):
        from tradingagents.screener.cli.app import app as screener_app
        import sys as _sys

        _sys.argv = ["screener"]
        screener_app()


def _run_analyzer() -> None:
    """Run the Analyzer CLI module (Stage 2)."""
    # Try new location first (cli.analyze.app.run), fall back to old
    try:
        from cli.analyze.app import run as analyzer_run

        analyzer_run()
    except (ImportError, AttributeError):
        from tradingagents.commands.analyze import run_analyze

        run_analyze(ticker=None, date=None, interactive=True)


def _run_report_viewer() -> None:
    """Run the HTML report viewer."""
    console = Console(theme=TRADING_THEME)
    path = Prompt.ask("[cyan]Report path[/cyan]", default="reports/")
    try:
        from tradingagents.commands.report import view_report

        view_report(path)
    except ImportError:
        console.print("[yellow]Report viewer not available[/yellow]")
