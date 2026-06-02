"""Interactive screener CLI wizard.

P6: Enhanced interactive experience aligned with TradingAgents CLI style.
P7: Integrated with Komo brand mascot.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import typer
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

from tradingagents.screener.cli.commands.run_impl import run as run_command

# P7: Import Komo mascot with graceful fallback
try:
    from tradingagents.ui.terminal_mascot import print_komo
except ImportError:
    def print_komo() -> None:
        from rich.console import Console
        c = Console()
        c.print("[dim][Komo mascot: not available][/dim]")

# Use Bloomberg-style themed console
from tradingagents.ui.theme import TRADING_THEME
console = Console(theme=TRADING_THEME)


def _print_welcome() -> None:
    """P6-2/P7: Enhanced welcome banner with Komo mascot."""
    # P7: Show Komo mascot first
    print_komo()

    banner_lines = [
        "[bold cyan]╔══════════════════════════════════════════════════════════╗[/bold cyan]",
        "[bold cyan]║   TRADINGAGENTS SCREENER  [dim]│[/dim]  Stage 1: A-share Candidate Discovery   ║[/bold cyan]",
        "[bold cyan]╚══════════════════════════════════════════════════════════╝[/bold cyan]",
        "",
        "[dim]Bloomberg-style terminal dashboard[/dim]",
        "",
        "[cyan]Workflow:[/cyan]",
        "  [1] [dim]Choose screening mode (FULL / FOCUSED / CUSTOM)[/dim]",
        "  [2] [dim]Set trade date and scope[/dim]",
        "  [3] [dim]Configure output options[/dim]",
        "  [4] [dim]Review summary and confirm[/dim]",
        "  [5] [dim]Execute screening[/dim]",
        "",
        "[dim]Tip: Press Ctrl+C to exit at any time[/dim]",
    ]
    console.print(Align.center(Panel(
        "\n".join(banner_lines),
        border_style="cyan",
        padding=(1, 2),
    )))
    console.print()


def _print_step_header(step_num: int, total_steps: int, title: str) -> None:
    """P6-2: Print a consistent step header."""
    console.print(f"[bold cyan]─── Step {step_num}/{total_steps}: {title} ───[/bold cyan]")


def _print_current_config(config: dict) -> None:
    """P6-2: Print current configuration summary."""
    console.print()
    console.print("[dim]Current selection:[/dim]")
    items = []
    if config.get("mode"):
        items.append(f"mode={config['mode']}")
    if config.get("trade_date"):
        items.append(f"date={config['trade_date']}")
    if config.get("focus"):
        items.append(f"focus={config['focus']}")
    if config.get("max_stocks"):
        items.append(f"max_stocks={config['max_stocks']}")
    if config.get("deep_analysis") is not None:
        items.append(f"deep_analysis={'on' if config['deep_analysis'] else 'off'}")
    if items:
        console.print(f"  [green]{'  |  '.join(items)}[/green]")
    console.print()


def _prompt_mode() -> str:
    """P6-3: Prompt for screening mode with better UX."""
    console.print()
    _print_step_header(1, 6, "Select Screening Mode")
    console.print()

    # Create a visual mode selector
    mode_table = Table(box=None, show_header=False, padding=(0, 2))
    mode_table.add_column(style="cyan", width=12)
    mode_table.add_column(style="white")
    mode_table.add_row("[bold]FULL[/bold]", "Scan near-full market (CSI indexes)")
    mode_table.add_row("[bold]FOCUSED[/bold]", "Target specific sector/theme/index")
    mode_table.add_row("[bold]CUSTOM[/bold]", "Provide explicit ticker list")
    mode_table.add_row("[dim]MVP/EXTENDED/EXPERIMENTAL[/dim]", "[dim]Legacy modes (for compatibility)[/dim]")

    console.print(mode_table)
    console.print()

    mode = Prompt.ask(
        "[cyan]Select mode[/cyan]",
        choices=["FULL", "FOCUSED", "CUSTOM", "MVP", "EXTENDED", "EXPERIMENTAL"],
        default="FULL",
    ).strip().upper()

    console.print(f"[green]✓ Mode: {mode}[/green]")
    return mode


def _prompt_date() -> str:
    """P6-3: Prompt for trade date with validation."""
    console.print()
    _print_step_header(2, 6, "Set Trade Date")
    console.print()

    default_date = datetime.now().strftime("%Y-%m-%d")
    while True:
        date_str = Prompt.ask(
            f"[cyan]Trade date (YYYY-MM-DD)[/cyan]",
            default=default_date,
        ).strip()
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            console.print(f"[green]✓ Date: {date_str}[/green]")
            return date_str
        except ValueError:
            console.print("[red]✗ Invalid date format. Please use YYYY-MM-DD.[/red]")


def _prompt_focus() -> tuple[Optional[str], Optional[str]]:
    """P6-3: Prompt for focus type and value in FOCUSED mode."""
    console.print()
    _print_step_header(3, 6, "Set Focus Scope")
    console.print()

    # Focus type selector
    focus_table = Table(box=None, show_header=False, padding=(0, 2))
    focus_table.add_column(style="cyan", width=10)
    focus_table.add_column(style="white")
    focus_table.add_row("[bold]index[/bold]", "By index constituents (e.g., 000300)")
    focus_table.add_row("[bold]sector[/bold]", "By industry sector (e.g., semiconductor)")
    focus_table.add_row("[bold]theme[/bold]", "By concept theme (e.g., AI)")
    focus_table.add_row("[bold]file[/bold]", "From a file with ticker list")

    console.print(focus_table)
    console.print()

    focus_type = Prompt.ask(
        "[cyan]Focus type[/cyan]",
        choices=["index", "sector", "theme", "file"],
        default="index",
    ).strip().lower()

    # Focus value depends on type
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
    console.print(f"[green]✓ Focus: {focus}[/green]")
    return focus_type, focus_value


def _prompt_tickers_or_universe() -> tuple[Optional[str], Optional[str]]:
    """P6-3: Prompt for ticker list or universe file in CUSTOM mode."""
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
        console.print(f"[green]✓ Tickers: {tickers[:50]}{'...' if len(tickers) > 50 else ''}[/green]")
        return tickers, None

    universe = Prompt.ask(
        "[cyan]Universe file path[/cyan]",
        default="stocks.txt",
    ).strip()
    console.print(f"[green]✓ Universe file: {universe}[/green]")
    return None, universe


def _prompt_options() -> tuple[int, bool, bool, Optional[str]]:
    """P6-3: Prompt for output options."""
    console.print()
    _print_step_header(4, 6, "Set Output Options")
    console.print()

    max_stocks = Prompt.ask(
        "[cyan]Max final candidates[/cyan]",
        default="5",
    ).strip()
    try:
        max_stocks = int(max_stocks)
        if max_stocks < 1:
            max_stocks = 5
    except ValueError:
        max_stocks = 5

    console.print()
    no_deep = not Confirm.ask(
        "[cyan]Enable Deep Analyzer?[/cyan]",
        default=True,
    )
    deep_label = "[red]off[/red]" if no_deep else "[green]on[/green]"
    console.print(f"  Deep Analysis: {deep_label}")

    console.print()
    allow_weekend = Confirm.ask(
        "[cyan]Allow weekend run?[/cyan]",
        default=False,
    )
    weekend_label = "[yellow]allowed[/yellow]" if allow_weekend else "[dim]blocked[/dim]"
    console.print(f"  Weekend: {weekend_label}")

    console.print()
    output_dir = Prompt.ask(
        "[cyan]Output directory[/cyan] (blank=default)",
        default="",
    ).strip() or None

    return max_stocks, no_deep, allow_weekend, output_dir


def _print_run_summary(config: dict) -> None:
    """P6-4: Print run summary before execution."""
    console.print()
    _print_step_header(5, 6, "Review Summary")
    console.print()

    # Create summary panel
    summary_items = [
        f"[cyan]Mode:[/cyan] {config.get('mode', 'N/A')}",
        f"[cyan]Date:[/cyan] {config.get('trade_date', 'N/A')}",
    ]

    if config.get("focus"):
        summary_items.append(f"[cyan]Focus:[/cyan] {config['focus']}")
    if config.get("tickers"):
        summary_items.append(f"[cyan]Tickers:[/cyan] {config.get('tickers', '')[:40]}...")
    if config.get("universe"):
        summary_items.append(f"[cyan]Universe:[/cyan] {config.get('universe', '')}")

    summary_items.extend([
        f"[cyan]Max Stocks:[/cyan] {config.get('max_stocks', 5)}",
        f"[cyan]Deep Analysis:[/cyan] {'Enabled' if config.get('deep_analysis', True) else 'Disabled'}",
        f"[cyan]Weekend:[/cyan] {'Allowed' if config.get('allow_weekend', False) else 'Blocked'}",
    ])

    if config.get("output_dir"):
        summary_items.append(f"[cyan]Output:[/cyan] {config.get('output_dir', '')}")

    # Add risk warnings
    risks = []
    if config.get("mode") == "FULL":
        risks.append("[yellow]⚠ FULL mode may take longer to run[/yellow]")
    if config.get("mode") == "CUSTOM" and not config.get("tickers"):
        risks.append("[yellow]⚠ CUSTOM mode depends on input file quality[/yellow]")

    if risks:
        summary_items.append("")
        summary_items.extend(risks)

    console.print(Panel(
        "\n".join(summary_items),
        title="[bold]Run Configuration[/bold]",
        border_style="cyan",
        padding=(1, 2),
    ))


def interactive() -> None:
    """P6: Launch enhanced interactive Screener wizard."""
    config: dict = {}

    try:
        # Step 1: Welcome and mode selection
        _print_welcome()
        config["mode"] = _prompt_mode()

        # Step 2: Date
        config["trade_date"] = _prompt_date()

        # Step 3: Mode-specific scope
        if config["mode"] == "FOCUSED":
            focus_type, focus_value = _prompt_focus()
            config["focus_type"] = focus_type
            config["focus_value"] = focus_value
            config["focus"] = f"{focus_type}={focus_value}"
        elif config["mode"] == "CUSTOM":
            tickers, universe = _prompt_tickers_or_universe()
            config["tickers"] = tickers
            config["universe"] = universe
        # FULL mode uses default universe

        # Step 4: Options
        max_stocks, no_deep, allow_weekend, output_dir = _prompt_options()
        config["max_stocks"] = max_stocks
        config["deep_analysis"] = not no_deep
        config["allow_weekend"] = allow_weekend
        config["output_dir"] = output_dir

        # Step 5: Summary and confirmation
        _print_run_summary(config)

        console.print()
        if not Confirm.ask("[cyan]Proceed with screening?[/cyan]", default=True):
            console.print("[yellow]Cancelled by user.[/yellow]")
            raise typer.Exit(code=0)

        # Step 6: Execute
        console.print()
        console.print("[cyan]Starting Screener...[/cyan]")
        console.print()

        # Run the screener
        # Note: run_command handles completion output internally (P6-6)
        run_command(
            mode=config["mode"],
            date=config["trade_date"],
            tickers=config.get("tickers"),
            universe=config.get("universe"),
            output_dir=config.get("output_dir"),
            output_format="auto",
            no_deep=no_deep,
            max_stocks=config["max_stocks"],
            allow_weekend=allow_weekend,
            verbose=True,
            focus_type=config.get("focus_type"),
            focus_value=config.get("focus_value"),
        )
        # run_command ends with typer.Exit(code=0), so code below won't execute

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Interrupted by user. Exiting.[/yellow]")
        raise typer.Exit(code=130)
    except Exception as e:
        console.print()
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
