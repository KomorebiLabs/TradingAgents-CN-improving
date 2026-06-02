"""TradingAgents Screener CLI — Stage 1: Candidate Discovery.

Entry point: python -m cli.screener (called by cli.main_menu)
Refactored to use the unified prompt layer (cli/prompts.py).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.rule import Rule
from rich.table import Table
from rich.box import SIMPLE
from rich.live import Live

from tradingagents.ui.theme import TRADING_THEME

# Import unified prompt helpers
from cli.prompts import create_question_box

console = Console(theme=TRADING_THEME)


def _print_welcome() -> None:
    """Print enhanced ASCII logo + welcome panel with professional trading terminal feel."""
    welcome_path = Path(__file__).parent.parent / "static" / "welcome.txt"
    if welcome_path.exists():
        console.print(welcome_path.read_text(encoding="utf-8"))

    # Enhanced welcome panel with version and professional styling
    banner_lines = [
        "[bold cyan]╔══════════════════════════════════════════════════════════╗[/bold cyan]",
        "[bold cyan]║  [bold white]TRADINGAGENTS SCREENER[/bold white]  │  [bold green]Stage 1: A-share Candidate Discovery[/bold green]  ║[/bold cyan]",
        "[bold cyan]╚══════════════════════════════════════════════════════════╝[/bold cyan]",
        "",
        "[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]",
        "[bold yellow]▸ Workflow:[/bold yellow]",
        "   [1] [cyan]Choose screening mode[/cyan]   (FULL / FOCUSED / CUSTOM)",
        "   [2] [cyan]Set trade date[/cyan]         (YYYY-MM-DD)",
        "   [3] [cyan]Configure scope[/cyan]         (focus or universe)",
        "   [4] [cyan]Set output options[/cyan]      (max candidates, deep analysis)",
        "   [5] [cyan]Review and confirm[/cyan]      (verify settings)",
        "   [6] [cyan]Execute screening[/cyan]       (run the analysis)",
        "[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]",
        "",
        "[dim]💡 Tip: Press Ctrl+C to exit at any time[/dim]",
    ]
    console.print(Align.center(Panel(
        "\n".join(banner_lines),
        border_style="cyan",
        padding=(1, 2),
        title="[bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green] [bold white]WELCOME[/bold white] [bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold green]",
    )))
    console.print()


def _print_step_progress(step_num: int, total_steps: int | None) -> None:
    """Print a visual progress bar showing current step."""
    if total_steps is None:
        console.print(f"\n[bold white]Step {step_num}:[/bold white]")
        return
    progress_pct = int((step_num / total_steps) * 100)
    filled = "█" * (step_num * 10 // total_steps)
    empty = "░" * (10 - (step_num * 10 // total_steps))
    bar = f"[bold cyan]{filled}[/bold cyan][dim]{empty}[/dim]"
    console.print(f"\n[bold white]Step {step_num}/{total_steps}:[/bold white] {bar} [bold cyan]{progress_pct}%[/bold cyan]")


def _print_step_header(step_num: int, total_steps: int | None, title: str) -> None:
    """Print a consistent step header with visual separator."""
    console.print()
    console.print(Rule(style="cyan", characters="─"))
    _print_step_progress(step_num, total_steps)
    console.print(f"[bold cyan]▶ {title}[/bold cyan]")
    console.print(Rule(style="dim cyan", characters="─"))
    console.print()


def _prompt_mode() -> str:
    """Step 1: Prompt for screening mode."""
    _print_step_header(1, None, "Select Screening Mode")
    console.print()

    mode_table = Table(
        box=SIMPLE,
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        padding=(0, 2),
        title="[bold]Available Modes[/bold]",
    )
    mode_table.add_column("[bold]Mode[/bold]", style="cyan", width=15)
    mode_table.add_column("[bold]Description[/bold]", style="white")
    mode_table.add_row(
        "[bold green]FULL[/bold green]",
        "Scan near-full A-share market via CSI broad/300/500 indexes (~1700 stocks)",
    )
    mode_table.add_row(
        "[bold yellow]FOCUSED[/bold yellow]",
        "Target a specific sector, theme, or index (e.g., semiconductor, AI, CSI 300)",
    )
    mode_table.add_row(
        "[bold magenta]CUSTOM[/bold magenta]",
        "Provide your own ticker list or universe file for screening",
    )
    mode_table.add_row(
        "[dim]MVP[/dim]",
        "[dim]Legacy: mini-scan of CSI broad + CSI 300 index (~300 stocks)[/dim]",
    )
    mode_table.add_row(
        "[dim]EXTENDED[/dim]",
        "[dim]Legacy: CSI 300 + CSI 500 + CSI 1000 index constituents[/dim]",
    )
    mode_table.add_row(
        "[dim]EXPERIMENTAL[/dim]",
        "[dim]Legacy: extra-wide scan (CSI + CSI 800 + CSI 1000)[/dim]",
    )
    console.print(mode_table)
    console.print()

    mode = Prompt.ask(
        "[cyan]Select mode[/cyan]",
        choices=["FULL", "FOCUSED", "CUSTOM", "MVP", "EXTENDED", "EXPERIMENTAL"],
        default="FULL",
    ).strip().upper()

    console.print(f"[bold green]✓[/bold green] Mode: [bold]{mode}[/bold]")
    return mode


def _prompt_date() -> str:
    """Step 2: Prompt for trade date."""
    console.print()
    _print_step_header(2, 6, "Set Trade Date")
    console.print()

    default_date = datetime.now().strftime("%Y-%m-%d")
    while True:
        date_str = Prompt.ask(
            "[cyan]Trade date (YYYY-MM-DD)[/cyan]",
            default=default_date,
        ).strip()
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            console.print(f"[bold green]✓[/bold green] Date: [bold white]{date_str}[/bold white]")
            return date_str
        except ValueError:
            console.print("[bold red]✗[/bold red] [red]Invalid date format. Please use YYYY-MM-DD.[/red]")


def _prompt_focus() -> tuple[str, str]:
    """Step 3 (FOCUSED): Prompt for focus type and value."""
    console.print()
    _print_step_header(3, 6, "Set Focus Scope")
    console.print()

    focus_table = Table(
        box=SIMPLE,
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        padding=(0, 2),
        title="[bold]Focus Types[/bold]",
    )
    focus_table.add_column("[bold]Type[/bold]", style="cyan", width=12)
    focus_table.add_column("[bold]Description[/bold]", style="white")
    focus_table.add_row("[bold yellow]index[/bold yellow]", "By index constituents (e.g., 000300)")
    focus_table.add_row("[bold yellow]sector[/bold yellow]", "By industry sector (e.g., semiconductor)")
    focus_table.add_row("[bold yellow]theme[/bold yellow]", "By concept theme (e.g., AI)")
    focus_table.add_row("[bold yellow]file[/bold yellow]", "From a file with ticker list")
    console.print(focus_table)
    console.print()

    focus_type = Prompt.ask(
        "[cyan]Focus type[/cyan]",
        choices=["index", "sector", "theme", "file"],
        default="index",
    ).strip().lower()

    console.print()
    if focus_type == "index":
        default_value = "000300"
        hint = "e.g., 000300 (CSI 300)"
    elif focus_type == "sector":
        default_value = "semiconductor"
        hint = "e.g., semiconductor, healthcare"
    elif focus_type == "theme":
        default_value = "AI"
        hint = "e.g., AI, new_energy"
    else:
        default_value = "stocks.txt"
        hint = "e.g., stocks.txt or /path/to/file.txt"

    focus_value = Prompt.ask(
        f"[cyan]Focus value[/cyan] ({hint})",
        default=default_value,
    ).strip()

    focus = f"{focus_type}={focus_value}"
    console.print(f"[bold green]✓[/bold green] Focus: [bold white]{focus}[/bold white]")
    return focus_type, focus_value


def _prompt_universe() -> tuple[Optional[str], Optional[str]]:
    """Step 3 (CUSTOM): Prompt for ticker list or universe file."""
    console.print()
    _print_step_header(3, 6, "Set Custom Universe")
    console.print()

    source = Prompt.ask(
        "[cyan]Input source[/cyan]",
        choices=["tickers", "universe", "file"],
        default="tickers",
    ).strip().lower()

    console.print()
    if source in ("tickers", "file"):
        tickers = Prompt.ask(
            "[cyan]Tickers (comma-separated)[/cyan]",
            default="600519,000001,300750",
        ).strip()
        display_tickers = tickers[:50] + "..." if len(tickers) > 50 else tickers
        console.print(f"[bold green]✓[/bold green] Tickers: [bold white]{display_tickers}[/bold white]")
        return tickers, None

    universe = Prompt.ask(
        "[cyan]Universe file path[/cyan]",
        default="stocks.txt",
    ).strip()
    console.print(f"[bold green]✓[/bold green] Universe file: [bold white]{universe}[/bold white]")
    return None, universe


def _prompt_options() -> tuple[int, bool, bool, Optional[str]]:
    """Step 4: Prompt for output options."""
    console.print()
    _print_step_header(4, 6, "Set Output Options")
    console.print()

    console.print(Panel(
        "[bold]Max final candidates[/bold]: How many top-ranked stocks to return after scoring.\n"
        "[dim]Recommended: 3-5 for focused follow-up analysis[/dim]",
        border_style="dim",
        padding=(1, 1),
    ))
    max_stocks_raw = Prompt.ask(
        "[cyan]Max final candidates[/cyan]",
        default="5",
    ).strip()
    try:
        max_stocks = int(max_stocks_raw)
        if max_stocks < 1:
            max_stocks = 5
    except ValueError:
        max_stocks = 5

    console.print()
    console.print(Panel(
        "[bold]Deep Analyzer[/bold]: LLM-powered deep dive into each candidate's fundamentals,\n"
        "news, and competitive moat after initial scoring.\n"
        "[dim]Warning: Adds ~3-5 min per candidate | Disable for faster MVP scans[/dim]",
        border_style="dim",
        padding=(1, 1),
    ))
    no_deep = not Confirm.ask(
        "[cyan]Enable Deep Analyzer?[/cyan]",
        default=True,
    )
    deep_label = "[red]off[/red]" if no_deep else "[green]on[/green]"
    console.print(f"  Deep Analysis: {deep_label}")

    console.print()
    console.print(Panel(
        "[bold]Allow Weekend[/bold]: Some data feeds (Tencent Finance, THS) update less\n"
        "frequently on weekends, which may cause data staleness warnings.\n"
        "[dim]Set No on weekdays for freshest data | Set Yes if running on Saturday/Sunday[/dim]",
        border_style="dim",
        padding=(1, 1),
    ))
    allow_weekend = Confirm.ask(
        "[cyan]Allow weekend run?[/cyan]",
        default=False,
    )
    weekend_label = "[yellow]allowed[/yellow]" if allow_weekend else "[dim]blocked[/dim]"
    console.print(f"  Weekend: {weekend_label}")

    console.print()
    console.print(Panel(
        "[bold]Output Directory[/bold]: Where to save the screening results.\n"
        "[dim]Leave blank for default (~/.tradingagents/logs/screener/) | Press Enter for default[/dim]",
        border_style="dim",
        padding=(1, 1),
    ))
    output_dir = Prompt.ask(
        "[cyan]Output directory[/cyan] (press Enter for default)",
        default="",
    ).strip() or None

    return max_stocks, no_deep, allow_weekend, output_dir


def _print_run_summary(config: dict) -> None:
    """Step 5: Print run summary before confirmation using a rich styled table."""
    console.print()
    _print_step_header(5, 6, "Review Summary")
    console.print()

    # Create a rich summary table with borders
    summary_table = Table(
        box=SIMPLE,
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        title="[bold]Run Configuration Summary[/bold]",
        title_style="bold white",
        padding=(0, 2),
        row_styles=["", "on black"],  # Alternating row colors
    )
    summary_table.add_column("[bold]Parameter[/bold]", style="cyan", width=20)
    summary_table.add_column("[bold]Value[/bold]", style="white")

    # Add configuration rows
    summary_table.add_row("[bold]Mode[/bold]", f"[bold green]{config.get('mode', 'N/A')}[/bold green]")
    summary_table.add_row("[bold]Trade Date[/bold]", f"[bold white]{config.get('trade_date', 'N/A')}[/bold white]")

    if config.get("focus"):
        summary_table.add_row("[bold]Focus[/bold]", f"[bold yellow]{config['focus']}[/bold yellow]")
    if config.get("tickers"):
        tickers = config.get('tickers', '')[:40]
        summary_table.add_row("[bold]Tickers[/bold]", f"[bold white]{tickers}{'...' if len(config.get('tickers', '')) > 40 else ''}[/bold white]")
    if config.get("universe"):
        summary_table.add_row("[bold]Universe[/bold]", f"[bold white]{config.get('universe', '')}[/bold white]")

    summary_table.add_row("[bold]Max Candidates[/bold]", f"[bold white]{config.get('max_stocks', 5)}[/bold white]")
    deep_status = "[bold green]Enabled[/bold green]" if config.get('deep_analysis', True) else "[bold red]Disabled[/bold red]"
    summary_table.add_row("[bold]Deep Analysis[/bold]", deep_status)
    weekend_status = "[bold yellow]Allowed[/bold yellow]" if config.get('allow_weekend', False) else "[bold dim]Blocked[/bold dim]"
    summary_table.add_row("[bold]Weekend Run[/bold]", weekend_status)

    if config.get("output_dir"):
        summary_table.add_row("[bold]Output Dir[/bold]", f"[bold white]{config.get('output_dir', '')}[/bold white]")

    console.print(summary_table)

    # Add risk warnings panel
    risks = []
    if config.get("mode") == "FULL":
        risks.append("[yellow]⚠ FULL mode may take longer to run[/yellow]")
    if config.get("mode") == "CUSTOM" and not config.get("tickers"):
        risks.append("[yellow]⚠ CUSTOM mode depends on input file quality[/yellow]")

    if risks:
        console.print()
        console.print(Panel(
            "\n".join(risks),
            title="[bold yellow]⚠ Risk Notices[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        ))


def run() -> None:
    """Main entry point for the Screener CLI.

    1. Print welcome
    2. Run 6-step questionnaire
    3. Execute screening via run_impl
    4. Show summary
    5. Return to caller (caller handles "返回主菜单？" prompt)
    """
    config: dict = {}
    step = 0

    try:
        # Step 1: Welcome + Mode selection
        _print_welcome()
        step = 1
        config["mode"] = _prompt_mode()

        # Step 2: Date
        step = 2
        config["trade_date"] = _prompt_date()

        # Step 3: Mode-specific scope
        if config["mode"] == "FOCUSED":
            step = 3
            focus_type, focus_value = _prompt_focus()
            config["focus_type"] = focus_type
            config["focus_value"] = focus_value
            config["focus"] = f"{focus_type}={focus_value}"
        elif config["mode"] == "CUSTOM":
            step = 3
            tickers, universe = _prompt_universe()
            config["tickers"] = tickers
            config["universe"] = universe
        # FULL/MVP/EXTENDED/EXPERIMENTAL skip step 3

        # Step 4: Options
        step = 4
        max_stocks, no_deep, allow_weekend, output_dir = _prompt_options()
        config["max_stocks"] = max_stocks
        config["deep_analysis"] = not no_deep
        config["allow_weekend"] = allow_weekend
        config["output_dir"] = output_dir
        config["no_deep"] = no_deep

        # Step 5: Summary + Confirmation
        step = 5
        _print_run_summary(config)

        console.print()
        if not Confirm.ask("[bold cyan]Proceed with screening?[/bold cyan]", default=True):
            console.print("[bold yellow]⚠ Cancelled by user.[/bold yellow]")
            return

        # Step 6: Execute with animated progress
        step = 6
        console.print()
        _print_step_header(6, 6, "Execute Screening")

        # Create animated execution panel
        execution_panel = Panel(
            "[bold cyan]Initializing screener engine...[/bold cyan]",
            title="[bold]Execution Status[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )
        console.print(execution_panel)
        console.print()

        # Use Rich progress for animated execution
        with Progress(
            SpinnerColumn(spinner_name="dots12", style="cyan"),
            TextColumn("[bold cyan]{task.description}[/bold cyan]"),
            BarColumn(bar_width=30, style="cyan"),
            TextColumn("[bold]{task.completed}/{task.total}[/bold]"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            main_task = progress.add_task("[bold cyan]Screening stocks...", total=100)

            # Import and run the execution engine
            from cli.screener.run_impl import run_screener
            result = run_screener(config)

            # Simulate progress completion
            for i in range(50, 101):
                progress.update(main_task, completed=i)
            progress.update(main_task, description="[bold green]✓ Screening complete![/bold green]")

        console.print()

        # Show summary
        from tradingagents.ui.summary import print_summary
        print_summary(result, module_type="screener")

    except KeyboardInterrupt:
        console.print()
        console.print("[bold yellow]⚠ Interrupted by user. Exiting.[/bold yellow]")
    except Exception as e:
        console.print()
        console.print(f"[bold red]✗ Error:[/bold red] [red]{e}[/red]")
