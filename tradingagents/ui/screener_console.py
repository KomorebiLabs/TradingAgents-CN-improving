"""Screener 专用 Rich Console 工具模块."""

from __future__ import annotations

import sys
from typing import Optional

from rich.box import MINIMAL
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from tradingagents.ui.theme import TRADING_THEME


def _detect_no_color() -> bool:
    return not sys.stdout.isatty()


console = Console(
    theme=TRADING_THEME,
    no_color=_detect_no_color(),
)


def print_rule(style: str = "cyan") -> None:
    console.print(Rule(style=style))


def print_stage_header(stage_name: str, subtitle: str = "") -> None:
    console.print()
    if subtitle:
        console.print(Panel.fit(
            f"[bold cyan]>> {stage_name}[/bold cyan]  [dim]-[/dim]  [white]{subtitle}[/white]",
            border_style="cyan",
            padding=(0, 1),
        ))
    else:
        console.print(Panel.fit(
            f"[bold cyan]>> {stage_name}[/bold cyan]",
            border_style="cyan",
            padding=(0, 1),
        ))
    console.print()


def print_stage_done(stage_name: str, stats: str) -> None:
    console.print(f"[green][OK] {stage_name} done[/green]  [dim]{stats}[/dim]")


def print_stage_warning(stage_name: str, message: str) -> None:
    console.print(f"[yellow][!] {stage_name}: {message}[/yellow]")


def print_stage_error(stage_name: str, message: str) -> None:
    console.print(f"[red][X] {stage_name}: {message}[/red]")


def print_header_banner(mode: str, trade_date: str, deep_analysis: bool) -> None:
    deep_label = "[green]True[/green]" if deep_analysis else "[yellow]False[/yellow]"
    console.print()
    console.print(Panel.fit(
        f"[bold white]TRADINGAGENTS SCREENER[/bold white]\n"
        f"[dim]mode=[/dim][cyan]{mode}[/cyan]  "
        f"[dim]date=[/dim][cyan]{trade_date}[/cyan]  "
        f"[dim]deep=[/dim]{deep_label}",
        border_style="green",
        padding=(1, 2),
        title="[bold green]EXECUTION START[/bold green]",
    ))
    console.print()


def print_completion_banner(candidates: int, deep_analyzed: int, elapsed: float) -> None:
    elapsed_str = f"{elapsed:.1f}s"
    console.print()
    console.print(Panel.fit(
        f"[bold green]SCREENER COMPLETE[/bold green]\n\n"
        f"[dim]Candidates:[/dim] [bold white]{candidates}[/bold white]  "
        f"[dim]Deep Analyzed:[/dim] [bold white]{deep_analyzed}[/bold white]  "
        f"[dim]Elapsed:[/dim] [cyan]{elapsed_str}[/cyan]",
        border_style="green",
        padding=(1, 2),
        title="[bold green]COMPLETE[/bold green]",
    ))
    console.print()


def print_progress_bar(
    description: str,
    current: int,
    total: int,
    prefix: str = "",
) -> None:
    pct = (current * 100) // total if total > 0 else 0
    bar_len = 20
    filled = "#" * (current * bar_len // total) if total > 0 else ""
    empty = "-" * (bar_len - len(filled))
    bar = f"[cyan]{filled}[/cyan][dim]{empty}[/dim]"
    label = f"{prefix} " if prefix else ""
    console.print(
        f"[dim]{description}:[/dim] {label}[cyan]{current}/{total}[/cyan] "
        f"[{bar}] [cyan]{pct}%[/cyan]",
        end="\r",
    )


def clear_progress_line() -> None:
    console.print(" " * 120, end="\r")


def create_stage_table(
    headers: list[str],
    rows: list[list[str]],
    title: str = "",
    border_style: str = "cyan",
) -> Table:
    table = Table(
        box=MINIMAL,
        show_header=True,
        header_style="bold cyan",
        border_style=border_style,
        padding=(0, 1),
        title=title,
    )
    for h in headers:
        table.add_column(f"[bold]{h}[/bold]", style="white")
    for row in rows:
        table.add_row(*[str(c) for c in row])
    return table


def print_probe_table(
    category: str,
    rows: list[tuple[str, bool, str]],
) -> None:
    ok_count = sum(1 for _, ok, _ in rows if ok)
    total_count = len(rows)

    table = Table(
        box=MINIMAL,
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        padding=(0, 1),
    )
    table.add_column("[bold]API[/bold]", style="white", width=28)
    table.add_column("[bold]Status[/bold]", width=10)
    table.add_column("[bold]Detail[/bold]", style="dim")

    for name, ok, detail in rows:
        if ok:
            table.add_row(name, "[green]PASS[/green]", detail or "[dim]-[/dim]")
        else:
            table.add_row(name, "[red]FAIL[/red]", detail or "[dim]-[/dim]")

    header = f"[bold cyan]>> {category.upper()}[/bold cyan]"
    summary = f"[green]{ok_count}[/green][dim]/{total_count} passed[/dim]"
    console.print(Panel(
        table,
        title=f"{header}  {summary}",
        border_style="cyan",
        padding=(1, 1),
    ))
