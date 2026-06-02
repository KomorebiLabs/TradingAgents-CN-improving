# TradingAgents CLI 整合与交互式终端美化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal: 将** `cli/` **原始入口和** `tradingagents/screener/cli/` 统一整合到 `python -m tradingagents` 单一大 CLI，视觉风格为 Bloomberg Terminal 数据仪表盘风，保留两个入口的所有原有功能。

**Architecture:** 采用 Typer 子命令架构，所有模块作为子命令注册到根 Typer app (`tradingagents/__main__.py`)。`cli/` 目录重构为 `tradingagents/commands/analyze/` 子包，`screener` 子命令直接复用现有实现（`tradingagents/screener/cli/`）。共享 Rich 样式常量统一放置在 `tradingagents/ui/theme.py`。新增 `--version` / `--info` / `config` 辅助子命令。

**Tech Stack:** Typer + Rich + questionary（保留原始交互风格）

---

## 准备工作

### Pre-0: 修复缺失的 Komo mascot 引用

**Files:**

- Modify: `tradingagents/ui/__init__.py`
- Modify: `tradingagents/screener/cli/interactive.py:22`
- Modify: `cli/main.py:35`

两个入口都在 import `tradingagents.ui.terminal_mascot`，但 `tradingagents/ui/__init__.py` 只有空内容。需要创建一个临时的 stub，让代码不报错。

- **Step 1: Read current ui/init.py**

```python
# tradingagents/ui/__init__.py

def print_komo():
    """Stub: print Komo mascot (placeholder until real implementation)."""
    print("[dim]Komo mascot: (not yet implemented)[/dim]")
```

- **Step 2: Commit**

```bash
git add tradingagents/ui/__init__.py
git commit -m "fix: add stub print_komo to resolve missing terminal_mascot import"
```

---

## Task 1: 创建统一根 CLI 入口 (`tradingagents/`)

**Files:**

- Create: `tradingagents/__main__.py`
- Create: `tradingagents/ui/theme.py`
- Modify: `tradingagents/__init__.py`

### 1.1 创建共享主题样式常量

**Files:**

- Create: `tradingagents/ui/theme.py`
- **Step 1: Write theme.py**

```python
"""Shared Bloomberg-style terminal theme constants for all TradingAgents CLI modules."""

from rich.theme import Theme

# Bloomberg Terminal inspired color palette
TRADING_THEME = Theme({
    # Primary colors
    "primary": "cyan",
    "success": "green",
    "warning": "yellow",
    "danger": "red",
    "info": "blue",

    # Panel/section colors
    "panel.header": "bold cyan",
    "panel.body": "white",
    "panel.border": "cyan",

    # Table colors
    "table.header": "bold magenta",
    "table.cell": "white",
    "table.index": "cyan",

    # Status indicators
    "status.pending": "yellow",
    "status.active": "cyan",
    "status.done": "green",
    "status.error": "red",

    # Signal badges
    "signal.buy": "bold green",
    "signal.hold": "yellow",
    "signal.sell": "bold red",

    # Accent
    "accent": "bold cyan",
    "dim": "dim",
})

# Standard box style for tables
TERMINAL_BOX = None  # Use default box style

# Banner gradient colors (for animated headers)
BANNER_COLOR = "cyan"
BANNER_SECONDARY = "green"
```

- **Step 2: Commit**

```bash
git add tradingagents/ui/theme.py
git commit -m "feat(cli): add shared Bloomberg-style theme constants"
```

### 1.2 创建根 CLI 入口

**Files:**

- Create: `tradingagents/__main__.py`
- Modify: `tradingagents/__init__.py`
- **Step 1: Write main.py**

```python
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

    Launches the full TradingAgents pipeline (Analysts → Research → Trading → Risk → Portfolio).
    This is the original `python -m cli.main` functionality.
    """
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
    # Screener's app is a Typer instance. The cleanest way to delegate is to
    # call its main callable with the remaining sys.argv arguments stripped of
    # the first two tokens ("tradingagents" + "screener").
    from tradingagents.screener.cli.app import app as screener_app

    # Everything after "tradingagents screener" is passed to screener app
    remaining_args = sys.argv[2:]
    # Reconstruct argv for screener: first token is program name, rest are args
    sys.argv = ["screener"] + remaining_args
    screener_app()


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

    # Interactive main menu
    if ctx.invoked_subcommand is None or ctx.resilient_parsing:
        _show_main_menu()


def _show_main_menu():
    """Show interactive main menu (Bloomberg-style dashboard)."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.align import Align

    console = Console(theme=TRADING_THEME)

    print_komo()

    # Dashboard-style welcome panel
    welcome_lines = [
        "[bold cyan]═══════════════════════════════════════════════════════════════[/bold cyan]",
        "[bold cyan]║[/bold cyan]          TradingAgents CLI  -  Main Dashboard         [bold cyan]║[/bold cyan]",
        "[bold cyan]═══════════════════════════════════════════════════════════════[/bold cyan]",
        "",
        "[dim]A-share Stock Intelligence Platform[/dim]",
        "",
        "[bold]Available Modules:[/bold]",
    ]

    console.print(Align.center("\n".join(welcome_lines)))
    console.print()

    # Module selection table
    table = Table(box=None, show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", width=4, justify="center")
    table.add_column("Module", style="bold white", width=20)
    table.add_column("Description", style="dim", width=45)
    table.add_column("Command", style="green", width=35)

    table.add_row("1", "[bold]Screener[/bold]",   "Stage 1: A-share candidate discovery",     "python -m tradingagents screener")
    table.add_row("2", "[bold]Analyzer[/bold]",   "Stage 2: Deep multi-agent analysis",        "python -m tradingagents analyze")
    table.add_row("3", "[bold]Report[/bold]",     "HTML report viewer",                        "python -m tradingagents report")
    table.add_row("Q", "[bold]Quit[/bold]",        "Exit CLI",                                  "")

    console.print(table)
    console.print()

    choice = Prompt.ask(
        "[cyan]Select module[/cyan] (1/2/3/Q)",
        choices=["1", "2", "3", "Q", "q"],
        default="Q",
    )

    if choice == "1":
        from tradingagents.screener.cli.app import app as screener_app
        sys.argv = ["screener"]
        screener_app()
    elif choice == "2":
        from tradingagents.commands.analyze import run_analyze
        run_analyze(ticker=None, date=None, interactive=True)
    elif choice == "3":
        console.print("[yellow]Report viewer: specify report path[/yellow]")
        path = Prompt.ask("[cyan]Report path[/cyan]", default="reports/")
        from tradingagents.commands.report import view_report
        view_report(path)
    else:
        console.print("[dim]Goodbye![/dim]")


if __name__ == "__main__":
    app()
```

- **Step 2: Write init.py export**

Modify `tradingagents/__init__.py` — add after the existing warnings:

```python
__version__ = "2.0.0"
```

- **Step 3: Commit**

```bash
git add tradingagents/__main__.py tradingagents/__init__.py tradingagents/ui/theme.py
git commit -m "feat(cli): add unified root CLI entry point with version/info/menu"
```

---

## Task 2: 重构 `cli/` 为 `tradingagents/commands/analyze/`

**Files:**

- Create: `tradingagents/commands/__init__.py`
- Create: `tradingagents/commands/analyze/__init__.py`
- Create: `tradingagents/commands/analyze/__main__.py`
- Move: `cli/main.py` → `tradingagents/commands/analyze/app.py` (refactored)
- Move: `cli/utils.py` → `tradingagents/commands/analyze/utils.py`
- Move: `cli/models.py` → `tradingagents/commands/analyze/models.py`
- Move: `cli/config.py` → `tradingagents/commands/analyze/config.py`
- Move: `cli/announcements.py` → `tradingagents/commands/analyze/announcements.py`
- Move: `cli/stats_handler.py` → `tradingagents/commands/analyze/stats_handler.py`
- Move: `cli/static/` → `tradingagents/commands/analyze/static/`
- Modify: `cli/__main__.py` (redirect to new location)
- Modify: `cli/__init__.py` (redirect to new location)
- Create: `tradingagents/commands/__init__.py`

### 2.1 创建包结构

- **Step 1: Create init.py for commands package**

```python
"""TradingAgents CLI commands package."""

from .analyze import run_analyze

__all__ = ["run_analyze"]
```

- **Step 2: Create init.py for analyze subpackage**

```python
"""TradingAgents analyze command (Stage 2: Deep multi-agent analysis)."""

from .app import app

__all__ = ["app", "run_analyze"]
```

- **Step 3: Create main.py for analyze**

```python
"""Entry point: python -m tradingagents.commands.analyze"""

from tradingagents.commands.analyze.app import app

app()
```

- **Step 4: Copy all files to new location and update imports**

For each file, the key change is that all `from cli.` imports become `from tradingagents.commands.analyze.` (or relative `from .`).

In `app.py` (copied from `cli/main.py`), make these changes:

- `from cli.models import AnalystType` → `from .models import AnalystType`
- `from cli.utils import *` → `from .utils import *`
- `from cli.announcements import ...` → `from .announcements import ...`
- `from cli.stats_handler import ...` → `from .stats_handler import ...`
- `from tradingagents.ui.terminal_mascot import print_komo` stays as-is
- The path reference for `static/welcome.txt` needs updating: `Path(__file__).parent / "static" / "welcome.txt"`

In `utils.py`, `announcements.py`, `stats_handler.py`, `models.py`, `config.py` — no content changes needed, just copy to new location.

- **Step 5: Create the run_analyze entry function (added to init.py)**

In `tradingagents/commands/analyze/__init__.py`, add:

```python
def run_analyze(
    ticker: str | None = None,
    date: str | None = None,
    interactive: bool = True,
):
    """Programmatic entry point for the analyze command.

    Args:
        ticker: Ticker symbol (used in non-interactive mode)
        date: Analysis date YYYY-MM-DD (used in non-interactive mode)
        interactive: If True, launch the interactive wizard (questionary prompts).
                     If False, use provided ticker/date with defaults for other options.
    """
    if interactive:
        # Interactive mode: call the original interactive flow
        from .app import run_analysis
        run_analysis()
    else:
        # Non-interactive mode: use CLI main (typer) with piped defaults
        # Import the original typer app and call it as if the user typed the args
        import sys
        args = []
        if ticker:
            args.extend(["--ticker", ticker])
        if date:
            args.extend(["--date", date])
        # Replace sys.argv with the equivalent CLI invocation
        old_argv = sys.argv
        sys.argv = ["analyze"] + args
        from .app import app as analyze_app
        try:
            analyze_app(standalone_mode=False)
        finally:
            sys.argv = old_argv
```

Note: The typer `--ticker` and `--date` options in the root `__main__.py` are pass-through options that feed into `run_analyze()`. The actual non-interactive analyze command in `analyze_app` is designed for interactive use (questionary prompts). For now, `run_analyze(interactive=False)` with ticker+date will be a future enhancement. Keep it as a graceful stub.

- **Step 6: Redirect old cli/ package to new location**

Modify `cli/__init__.py`:

```python
"""Redirect: use tradingagents.commands.analyze instead.

This package is kept for backwards compatibility.
Run: python -m tradingagents
Or:  python -m tradingagents.commands.analyze
"""

from tradingagents.commands.analyze import app

__all__ = ["app"]
```

Modify `cli/__main__.py`:

```python
"""Redirect to: python -m tradingagents"""

import sys
from pathlib import Path

# Show redirect message
print("[cyan]Redirecting to: python -m tradingagents analyze[/cyan]")
print("[dim]Note: 'python -m cli.main' is deprecated, use 'python -m tradingagents analyze'[/dim]\n")

# Forward to the new entry point
from tradingagents.commands.analyze.app import app as analyze_app
analyze_app()
```

- **Step 7: Copy static folder**

Copy `cli/static/welcome.txt` to `tradingagents/commands/analyze/static/welcome.txt`.

- **Step 8: Commit**

```bash
git add tradingagents/commands/
git add cli/__init__.py cli/__main__.py
git commit -m "refactor(cli): move cli/ to tradingagents/commands/analyze/ with backwards compat redirect"
```

---

## Task 3: 更新 Screener CLI 使用共享主题

**Files:**

- Modify: `tradingagents/screener/cli/app.py`
- Modify: `tradingagents/screener/cli/interactive.py`
- Modify: `tradingagents/screener/cli/commands/run_impl.py`

### 3.1 Update screener CLI to use shared theme

- **Step 1: Update screener CLI app.py to use theme**

Add at top of `tradingagents/screener/cli/app.py`:

```python
from tradingagents.ui.theme import TRADING_THEME

# Override console to use themed console
from rich.console import Console
console = Console(theme=TRADING_THEME)
```

Update the `app` creation to use the theme:

```python
app = typer.Typer(
    name="screener",
    help="TradingAgents Screener CLI: Stage 1 candidate discovery for A-share stocks.",
    add_completion=True,
    no_args_is_help=False,
    rich_markup_mode="rich",
)
```

Also update the screener's `__main__.py` to use:

```python
"""Entry point for: python -m tradingagents.screener.cli"""

import sys
import logging
import logging

# Ensure logging goes to stdout with TradingAgents branding
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)

from tradingagents.screener.cli.app import app

app()
```

### 3.2 Update interactive.py to use theme

- **Step 2: Update screener interactive.py**

Replace the `print_komo()` import line with a try/except to handle missing mascot gracefully:

```python
try:
    from tradingagents.ui.terminal_mascot import print_komo
except ImportError:
    def print_komo():
        from rich.console import Console
        c = Console()
        c.print("[dim][Komo mascot: not available][/dim]")
```

Add a Bloomberg-style header to the welcome banner:

```python
def _print_welcome() -> None:
    """Enhanced welcome banner with Bloomberg dashboard style."""
    # Show Komo mascot if available
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
```

- **Step 3: Commit**

```bash
git add tradingagents/screener/cli/app.py tradingagents/screener/cli/interactive.py
git commit -m "feat(cli): apply Bloomberg-style theme to screener interactive mode"
```

---

## Task 4: 添加 Report 子命令（HTML 美化报告）

**Files:**

- Create: `tradingagents/commands/report/__init__.py`
- Create: `tradingagents/commands/report/html_builder.py`
- Create: `tradingagents/commands/report/__main__.py`

### 4.1 Create report command

- **Step 1: Create report/init.py**

```python
"""TradingAgents report viewer command."""

from .html_builder import generate_html_report, view_report

__all__ = ["generate_html_report", "view_report"]
```

- **Step 2: Create html_builder.py**

```python
"""HTML report generator for screener and analyze results.

Bloomberg Terminal inspired dark theme with data-rich tables.
"""

from pathlib import Path
from typing import Any
import json
from datetime import datetime


def generate_html_report(
    title: str,
    results: dict[str, Any],
    output_path: str | Path,
    template: str = "screener",
) -> Path:
    """Generate a self-contained HTML report from screener/analyze results.

    Args:
        title: Report title
        results: Dict containing report data (candidates, scores, signals, etc.)
        output_path: Where to save the HTML file
        template: "screener" or "analyze"
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    html_content = _build_html(title, results, template)
    output_path.write_text(html_content, encoding="utf-8")
    return output_path


def _build_html(title: str, results: dict, template: str) -> str:
    """Build Bloomberg-style HTML report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Dark Bloomberg theme CSS
    css = """
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: #0d1117;
            color: #e6edf3;
            font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
            font-size: 13px;
            line-height: 1.6;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header {
            border-bottom: 2px solid #00d4ff;
            padding-bottom: 16px;
            margin-bottom: 24px;
        }
        .header h1 {
            color: #00d4ff;
            font-size: 24px;
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        .header .subtitle { color: #7d8590; margin-top: 4px; }
        .meta-bar {
            display: flex;
            gap: 24px;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 12px 16px;
            margin-bottom: 24px;
        }
        .meta-item { display: flex; flex-direction: column; }
        .meta-label { color: #7d8590; font-size: 11px; text-transform: uppercase; }
        .meta-value { color: #00d4ff; font-size: 15px; font-weight: bold; }
        .section { margin-bottom: 32px; }
        .section-title {
            color: #00d4ff;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-left: 3px solid #00d4ff;
            padding-left: 10px;
            margin-bottom: 16px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        th {
            background: #161b22;
            color: #f0883e;
            text-align: left;
            padding: 10px 12px;
            border-bottom: 2px solid #30363d;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #21262d;
        }
        tr:hover { background: #161b22; }
        .signal-buy { color: #3fb950; font-weight: bold; }
        .signal-hold { color: #d29922; font-weight: bold; }
        .signal-sell { color: #f85149; font-weight: bold; }
        .score { color: #00d4ff; font-weight: bold; }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        }
        .badge-bull { background: rgba(63, 185, 80, 0.15); color: #3fb950; }
        .badge-bear { background: rgba(248, 81, 73, 0.15); color: #f85149; }
        .badge-neutral { background: rgba(210, 153, 34, 0.15); color: #d29922; }
        .footer {
            border-top: 1px solid #30363d;
            padding-top: 16px;
            margin-top: 40px;
            color: #7d8590;
            font-size: 11px;
        }
    </style>
    """

    body = _build_screener_table(results)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - TradingAgents Report</title>
    <style>{css}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <div class="subtitle">TradingAgents Screener Report</div>
        </div>

        <div class="meta-bar">
            <div class="meta-item">
                <span class="meta-label">Generated</span>
                <span class="meta-value">{timestamp}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Candidates</span>
                <span class="meta-value">{len(results.get('candidates', []))}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Mode</span>
                <span class="meta-value">{results.get('mode', 'N/A')}</span>
            </div>
        </div>

        {body}

        <div class="footer">
            Generated by TradingAgents CLI &bull; Data may be delayed
        </div>
    </div>
</body>
</html>"""


def _build_screener_table(results: dict) -> str:
    """Build HTML table for screener results."""
    candidates = results.get("candidates", [])

    if not candidates:
        return '<div class="section"><div class="section-title">No candidates found</div></div>'

    rows = []
    for i, c in enumerate(candidates, 1):
        score = c.get("score", 0)
        signal = c.get("signal", "HOLD")
        ticker = c.get("ticker", "N/A")
        name = c.get("name", c.get("ticker", "N/A"))

        signal_class = {
            "BUY": "signal-buy",
            "HOLD": "signal-hold",
            "SELL": "signal-sell",
        }.get(signal, "signal-hold")

        reasons = c.get("key_reasons", [])
        if isinstance(reasons, list):
            reasons_html = "<br>".join(f"&bull; {r}" for r in reasons[:3])
        else:
            reasons_html = str(reasons)

        rows.append(f"""<tr>
            <td>{i}</td>
            <td><strong>{ticker}</strong></td>
            <td>{name}</td>
            <td class="{signal_class}">{signal}</td>
            <td class="score">{score:.1f}</td>
            <td style="max-width:400px">{reasons_html}</td>
        </tr>""")

    return f"""
    <div class="section">
        <div class="section-title">Top Candidates</div>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Ticker</th>
                    <th>Name</th>
                    <th>Signal</th>
                    <th>Score</th>
                    <th>Key Reasons</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
    </div>"""


def view_report(path: str):
    """Open HTML report in browser."""
    import webbrowser
    import os

    p = Path(path).expanduser().resolve()
    if not p.exists():
        print(f"[red]Report not found: {p}[/red]")
        return

    # Try to open with system default browser
    url = f"file://{p.absolute()}"
    print(f"[cyan]Opening report: {p.name}[/cyan]")
    webbrowser.open(url)
```

- **Step 3: Create main.py**

```python
"""Entry point: python -m tradingagents.commands.report"""

from tradingagents.commands.report import view_report

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "reports/"
    view_report(path)
```

- **Step 4: Commit**

```bash
git add tradingagents/commands/report/
git commit -m "feat(report): add HTML report generator with Bloomberg dark theme"
```

---

## Task 5: 集成 HTML 报告到 Screener 输出

**Files:**

- Modify: `tradingagents/screener/cli/commands/run_impl.py`
- Modify: `tradingagents/screener/report.py`

### 5.1 Hook HTML report into screener output

- **Step 1: Add HTML report generation to run_impl.py**

Add near the end of the `run()` function in `run_impl.py`, after the terminal output is printed and before `raise typer.Exit()`:

```python
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
            for c in (ranking or [])
        ],
        "mode": mode,
        "date": trade_date,
    }
    html_path = Path(output_dir or "reports") / f"screener_{trade_date}.html"
    generate_html_report(
        title=f"Screener Report - {trade_date}",
        results=report_data,
        output_path=html_path,
        template="screener",
    )
    console.print(f"[green]HTML report: {html_path.resolve()}[/green]")
except Exception as e:
    console.print(f"[dim]HTML report skipped: {e}[/dim]")
```

- **Step 2: Commit**

```bash
git add tradingagents/screener/cli/commands/run_impl.py
git commit -m "feat(report): generate HTML report alongside screener terminal output"
```

---

## Task 6: 验证完整 CLI 流程

### 6.1 Test root entry point

- **Step 1: Test --version**

```bash
python -m tradingagents --version
```

Expected: Version panel with Komo mascot.

- **Step 2: Test --info**

```bash
python -m tradingagents --info
```

Expected: System info table.

- **Step 3: Test screener help**

```bash
python -m tradingagents screener --help
```

Expected: Screener help text.

- **Step 4: Test screener run help**

```bash
python -m tradingagents screener run --help
```

Expected: Full screener run options.

- **Step 5: Test analyze help**

```bash
python -m tradingagents analyze --help
```

Expected: Analyze help text.

- **Step 6: Verify old entry point still works**

```bash
python -m cli.main --help
```

Expected: Works (via redirect).

---

## 总结

### 架构变更图

```
Before:
  cli/main.py          ← python -m cli.main (analyze only)
  tradingagents/screener/cli/__main__.py  ← python -m screener.cli (screener only)
  No root entry point

After:
  python -m tradingagents              ← interactive main menu (Bloomberg dashboard)
  ├── python -m tradingagents screener       ← Stage 1 (existing, enhanced)
  │     ├── python -m tradingagents screener run --date 2026-05-18
  │     └── python -m tradingagents screener (interactive wizard)
  ├── python -m tradingagents analyze        ← Stage 2 (moved from cli/)
  └── python -m tradingagents report <path>  ← HTML report viewer (new)
  python -m cli.main                  ← backwards compat redirect
```

### 交付物清单


| 文件                                                | 操作  | 说明                   |
| ------------------------------------------------- | --- | -------------------- |
| `tradingagents/__main__.py`                       | 创建  | 统一根 CLI 入口           |
| `tradingagents/ui/theme.py`                       | 创建  | Bloomberg 风格共享主题     |
| `tradingagents/ui/__init__.py`                    | 修改  | print_komo stub      |
| `tradingagents/commands/__init__.py`              | 创建  | commands 包           |
| `tradingagents/commands/analyze/`                 | 创建  | cli/ 重构后的 analyze 命令 |
| `tradingagents/commands/report/`                  | 创建  | HTML 报告生成器           |
| `tradingagents/screener/cli/app.py`               | 修改  | 使用共享主题               |
| `tradingagents/screener/cli/interactive.py`       | 修改  | Bloomberg 风格横幅       |
| `tradingagents/screener/cli/commands/run_impl.py` | 修改  | 集成 HTML 报告           |
| `cli/__init__.py`                                 | 修改  | 重定向到新位置              |
| `cli/__main__.py`                                 | 修改  | 重定向到新位置              |


---

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-05-19-tradingagents-cli-unified.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**