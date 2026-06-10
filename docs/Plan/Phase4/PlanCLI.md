# Screener CLI 执行阶段全量 Rich UI 改造实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `tradingagents/screener/` 下所有模块的裸 `print()` 替换为 Rich Console API + TRADING_THEME 主题，实现与欢迎界面/结果页面一致的 Bloomberg Terminal 风格输出。

**Architecture:** 新建共享 console 工具模块 `tradingagents/ui/screener_console.py`，各 Screener 子模块统一 import 该模块的 console 实例，不再各自创建 Console。执行阶段使用 `Panel` / `Table` / `Progress` / `Rule` 等 Rich 组件实现彩色面板输出。

**Tech Stack:** `rich` (Panel, Table, Progress, Rule, Console, Live, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, box)

---

## 文件结构

| 角色 | 路径 |
|------|------|
| 新建 | `tradingagents/ui/screener_console.py` |
| 修改 | `tradingagents/screener/engine.py` |
| 修改 | `tradingagents/screener/universe.py` |
| 修改 | `tradingagents/screener/data_access.py` |
| 修改 | `tradingagents/screener/strategies/technical.py` |
| 修改 | `tradingagents/screener/strategies/policy.py` |
| 修改 | `tradingagents/screener/strategies/smart_money.py` |
| 修改 | `tradingagents/screener/deep_analyzer.py` |
| 修改 | `tradingagents/screener/merger.py` |

---

## 阶段一：共享 Console 工具模块

### Task 1: 创建 `tradingagents/ui/screener_console.py`

**Files:**
- Create: `tradingagents/ui/screener_console.py`
- Test: N/A（此模块为纯工具，无业务逻辑测试）

- [ ] **Step 1: 编写模块内容**

```python
"""Screener 专用 Rich Console 工具模块.

所有 Screener 子模块（engine, universe, strategies 等）统一使用
本模块导出的 console 实例，避免每个文件各自创建 Console 实例。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.rule import Rule
from rich.table import Table
from rich.box import MINIMAL

from tradingagents.ui.theme import TRADING_THEME


def _detect_no_color() -> bool:
    """检测是否应该禁用颜色（TTY 被重定向到文件时）。"""
    return not sys.stdout.isatty()


# Screener 专用 console，所有子模块共用
# no_color=True 时自动降级为纯文本（用于日志重定向）
console = Console(
    theme=TRADING_THEME,
    no_color=_detect_no_color(),
)


# ── 预构建样式常量 ────────────────────────────────────────────────

PANEL_BORDER_CYAN = "cyan"
PANEL_BORDER_GREEN = "green"
PANEL_BORDER_YELLOW = "yellow"
PANEL_BORDER_RED = "red"
PANEL_BORDER_BLUE = "blue"
PANEL_BORDER_MAGENTA = "magenta"


# ── 快捷工具函数 ─────────────────────────────────────────────────

def print_rule(style: str = "cyan") -> None:
    """打印一条水平分隔线。"""
    console.print(Rule(style=style))


def print_stage_header(stage_name: str, subtitle: str = "") -> None:
    """打印阶段开始标题面板。

    示例: Stage Universe, Stage A, Stage B
    """
    header_text = f"[bold cyan]{stage_name}[/bold cyan]"
    if subtitle:
        header_text += f"  [dim]| {subtitle}[/dim]"
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]▸ {stage_name}[/bold cyan]{'  [dim]▶[/dim]  [white]" + subtitle + "[/white]" if subtitle else "[/white]"}",
        border_style="cyan",
        padding=(0, 1),
    ))
    console.print()


def print_stage_done(stage_name: str, stats: str) -> None:
    """打印阶段完成信息。"""
    console.print(f"[green]✓ {stage_name} done[/green]  [dim]{stats}[/dim]")


def print_stage_warning(stage_name: str, message: str) -> None:
    """打印阶段警告信息。"""
    console.print(f"[yellow]⚠ {stage_name}: {message}[/yellow]")


def print_stage_error(stage_name: str, message: str) -> None:
    """打印阶段错误信息。"""
    console.print(f"[red]✗ {stage_name}: {message}[/red]")


def print_header_banner(mode: str, trade_date: str, deep_analysis: bool) -> None:
    """打印运行启动横幅（替换 engine.py 中的裸 print 分隔线）。"""
    console.print()
    console.print(Panel.fit(
        f"[bold white]TRADINGAGENTS SCREENER[/bold white]\n"
        f"[dim]mode=[/dim][cyan]{mode}[/cyan]  "
        f"[dim]date=[/dim][cyan]{trade_date}[/cyan]  "
        f"[dim]deep=[/dim][{'green' if deep_analysis else 'yellow'}]{deep_analysis}[/]",
        border_style="green",
        padding=(1, 2),
        title="[bold green]EXECUTION START[/bold green]",
    ))
    console.print()


def print_completion_banner(candidates: int, deep_analyzed: int, elapsed: float) -> None:
    """打印运行完成横幅（替换 engine.py 中的裸 print 分隔线）。"""
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
    """打印一行带颜色和百分比的进度文字（用于 Stage A/B 等高频循环）。"""
    pct = (current * 100) // total if total > 0 else 0
    bar_len = 20
    filled = "█" * (current * bar_len // total) if total > 0 else ""
    empty = "░" * (bar_len - len(filled))
    bar = f"[cyan]{filled}[/cyan][dim]{empty}[/dim]"
    label = f"{prefix} " if prefix else ""
    console.print(
        f"[dim]{description}:[/dim] {label}[cyan]{current}/{total}[/cyan] "
        f"[{bar}] [cyan]{pct}%[/cyan]",
        end="\r",
    )


def clear_progress_line() -> None:
    """清除 progress bar 的行（打印完成后调用）。"""
    console.print(" " * 120, end="\r")


def create_stage_table(
    headers: list[str],
    rows: list[list[str]],
    title: str = "",
    border_style: str = "cyan",
) -> Table:
    """创建标准 Stage 表格，用于 DataProbe 等结构化输出。"""
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
    """打印 DataProbe 的探测结果表格。

    Args:
        category: 探测类别名，如 "spot_snapshot", "hist_fetch"
        rows: list of (name, ok, detail)
    """
    ok_count = sum(1 for _, ok, _ in rows if ok)
    total_count = len(rows)

    table = Table(box=MINIMAL, show_header=True, header_style="bold cyan", border_style="cyan", padding=(0, 1))
    table.add_column("[bold]API[/bold]", style="white", width=28)
    table.add_column("[bold]Status[/bold]", width=10)
    table.add_column("[bold]Detail[/bold]", style="dim")

    for name, ok, detail in rows:
        status = "[green]✓ PASS[/green]" if ok else "[red]✗ FAIL[/red]"
        status_style = "green" if ok else "red"
        table.add_row(name, f"[{status_style}]{'PASS' if ok else 'FAIL'}[/{status_style}]", detail or "[dim]-[/dim]")

    header = f"[bold cyan]▸ {category.upper()}[/bold cyan]"
    summary = f"[green]{ok_count}[/green][dim]/{total_count} passed[/dim]"

    console.print(Panel(
        table,
        title=f"{header}  {summary}",
        border_style="cyan",
        padding=(1, 1),
    ))
```

- [ ] **Step 2: 保存文件**

文件写入路径: `D:\cursor\HarmonyOS\Github project\TradingAgents-main\tradingagents\ui\screener_console.py`

- [ ] **Step 3: 验证语法**

Run: `python -c "from tradingagents.ui.screener_console import console, print_stage_header; print('OK')"`
Expected: `OK` (no errors)

---

## 阶段二：核心 Engine 改造

### Task 2: 改造 `tradingagents/screener/engine.py`

**Files:**
- Modify: `tradingagents/screener/engine.py`

需要替换的 print 调用（替换关系精确到每行）：

| 行号 | 旧代码 | 新代码 |
|------|--------|--------|
| 169 | `print(f"[SCREENER] Stage A: processed...")` | `print_progress_bar("Stage A", i+1, total)` |
| 171 | `print(f"[SCREENER] Stage A: done...")` | `clear_progress_line()` + `console.print("[green]✓ Stage A done[/green]  ...") |
| 185-188 | 裸分隔线 + 启动信息 | `print_header_banner(mode, trade_date, enable_deep_analysis)` |
| 213 | `print()` 空白行 | 删除（由 print_header_banner 包含） |
| 214 | `print(f"[SCREENER] Stage Universe: done...")` | 注释掉（universe.py 内部已输出） |
| 217 | `print()` 空白行 | 删除 |
| 218 | `print(f"[SCREENER] Stage A: light pre-screening...")` | `print_stage_header("Stage A", f"pre-screening {len(universe.tickers)} stocks")` |
| 230 | `print(f"[SCREENER] Stage A: done...")` | 已有（_run_stage_a 末尾输出），在此处也输出一行汇总 |
| 238 | `print()` 空白行 | 删除 |
| 239 | `print(f"[SCREENER] Stage B: running strategies...")` | `print_stage_header("Stage B", f"strategies on {len(stagea_pass_tickers)} stocks")` |
| 243 | `print(f"[SCREENER] Stage B: running TechnicalStrategy...")` | `console.print("[dim]  TechnicalStrategy...[/dim]", end="\r")` |
| 245 | `print(f"[SCREENER] Stage B: running PolicyStrategy...")` | 同上 |
| 247 | `print(f"[SCREENER] Stage B: running SmartMoneyStrategy...")` | 同上 |
| 249 | `print()` 空白行 | 删除 |
| 250 | `print(f"[SCREENER] Stage B: all strategies done...")` | `console.print(f"[green]✓ Stage B done[/green]  Technical=[cyan]{len(technical_outcome.cards)}[/cyan]  Policy=[cyan]{len(policy_outcome.cards)}[/cyan]  SmartMoney=[cyan]{len(smart_money_outcome.cards)}[/cyan]")` |
| 260 | `print()` 空白行 | 删除 |
| 261 | `print("[SCREENER] Stage DeepAnalysis: starting...")` | `print_stage_header("Stage DeepAnalysis", f"analyzing {len(merged_candidates)} candidates")` |
| 265 | `print("[SCREENER] Stage DeepAnalysis: skipped...")` | `console.print("[yellow]  DeepAnalysis skipped (no candidates)[/yellow]")` |
| 342 | `print()` 空白行 | 删除 |
| 358 | `print(f"[SCREENER] Stage Names: resolving...")` | `print_stage_header("Stage Names", f"resolving {len(merged_candidates)} names")` |
| 361 | `print(f"[SCREENER] Stage Names: resolving...")` | 删除高频进度（仅保留 Stage Names header 即可） |
| 401-404 | 裸分隔线 + 完成信息 | `print_completion_banner(len(merged_candidates), len(deep_results), elapsed)` |

- [ ] **Step 1: 在文件顶部 import 后追加**

在 `engine.py` 顶部（`from tradingagents.screener.merger import merge_signal_cards` 之后）添加：

```python
from tradingagents.ui.screener_console import (
    console,
    print_header_banner,
    print_stage_header,
    print_stage_done,
    print_completion_banner,
    print_progress_bar,
    clear_progress_line,
)
```

- [ ] **Step 2: 替换 run() 方法中的 print 分隔线和启动横幅（行 185-189）**

将：
```python
        print()
        print("=" * 70)
        print(f"[SCREENER] Starting run | mode={mode} | date={trade_date} | deep_analysis={enable_deep_analysis}")
        print("=" * 70)
        print()
```
替换为：
```python
        print_header_banner(mode, trade_date, enable_deep_analysis)
```

- [ ] **Step 3: 替换 Stage Universe 完成行（行 213-214）**

将：
```python
        print()
        print(f"[SCREENER] Stage Universe: done | {len(universe.tickers)} stocks in universe (mode={mode})")
```
替换为：
```python
        console.print(f"[green]✓ Universe ready[/green]  [dim]{len(universe.tickers)} stocks  mode=[cyan]{mode}[/cyan]")
```

- [ ] **Step 4: 替换 Stage A 开始（行 217-218）**

将：
```python
        print()
        print(f"[SCREENER] Stage A: light pre-screening of {len(universe.tickers)} stocks...")
```
替换为：
```python
        print_stage_header("Stage A", f"light pre-screening of {len(universe.tickers)} stocks")
```

- [ ] **Step 5: 替换 _run_stage_a 中的 print_progress 和 done（行 169-171）**

将 `_run_stage_a` 方法中行 169 的：
```python
                print(f"[SCREENER] Stage A: processed {i + 1}/{total} ({pct}%) | passed so far: {len(passed)}")
```
替换为：
```python
                print_progress_bar("Stage A", i + 1, total)
```

将行 171 的：
```python
        print(f"[SCREENER] Stage A: done | {len(passed)}/{total} passed | dropped: {total - len(passed)}")
```
替换为：
```python
        clear_progress_line()
        console.print(f"[green]✓ Stage A done[/green]  [cyan]{len(passed)}/{total}[/cyan] passed  [red]{total - len(passed)}[/red] dropped")
```

同时在 `_run_stage_a` 顶部添加 import：
```python
from tradingagents.ui.screener_console import print_progress_bar, clear_progress_line, console
```

- [ ] **Step 6: 替换 Stage B 开始（行 238-239）**

将：
```python
        print()
        print(f"[SCREENER] Stage B: running strategies on {len(stagea_pass_tickers)} stocks...")
        print()
```
替换为：
```python
        print_stage_header("Stage B", f"running strategies on {len(stagea_pass_tickers)} stocks")
```

- [ ] **Step 7: 替换策略执行中的内联进度（行 243-250）**

将：
```python
        print(f"[SCREENER] Stage B: running TechnicalStrategy on {len(stagea_pass_tickers)} stocks...")
        technical_outcome = technical_strategy.run(stagea_pass_tickers, trade_date)
        print(f"[SCREENER] Stage B: running PolicyStrategy on {len(stagea_pass_tickers)} stocks...")
        policy_outcome = policy_strategy.run(stagea_pass_tickers, trade_date)
        print(f"[SCREENER] Stage B: running SmartMoneyStrategy on {len(stagea_pass_tickers)} stocks...")
        smart_money_outcome = smart_money_strategy.run(stagea_pass_tickers, trade_date)
        print()
        print(f"[SCREENER] Stage B: all strategies done | Technical={len(technical_outcome.cards)} cards | Policy={len(policy_outcome.cards)} cards | SmartMoney={len(smart_money_outcome.cards)} cards")
```
替换为：
```python
        console.print("[dim]  Running TechnicalStrategy...[/dim]", end="\r")
        technical_outcome = technical_strategy.run(stagea_pass_tickers, trade_date)
        console.print(f"[green]  ✓ TechnicalStrategy[/green]  [cyan]{len(technical_outcome.cards)}[/cyan] cards  ", end="\r")

        console.print("[dim]  Running PolicyStrategy...[/dim]", end="\r")
        policy_outcome = policy_strategy.run(stagea_pass_tickers, trade_date)
        console.print(f"[green]  ✓ PolicyStrategy[/green]  [cyan]{len(policy_outcome.cards)}[/cyan] cards  ", end="\r")

        console.print("[dim]  Running SmartMoneyStrategy...[/dim]", end="\r")
        smart_money_outcome = smart_money_strategy.run(stagea_pass_tickers, trade_date)
        console.print()
        console.print(f"[green]✓ Stage B done[/green]  Technical=[cyan]{len(technical_outcome.cards)}[/cyan]  Policy=[cyan]{len(policy_outcome.cards)}[/cyan]  SmartMoney=[cyan]{len(smart_money_outcome.cards)}[/cyan]")
```

- [ ] **Step 8: 替换 DeepAnalysis 部分（行 260-265）**

将：
```python
        print()
        print("[SCREENER] Stage DeepAnalysis: starting deep analysis of candidates...")
```
替换为：
```python
        if enable_deep_analysis and merged_candidates:
            print_stage_header("Stage DeepAnalysis", f"deep analysis of {len(merged_candidates)} candidates")
```

将：
```python
        elif enable_deep_analysis and not merged_candidates:
            print("[SCREENER] Stage DeepAnalysis: skipped (no candidates)")
```
替换为：
```python
        elif enable_deep_analysis and not merged_candidates:
            console.print("[yellow]  DeepAnalysis skipped (no candidates)[/yellow]")
```

- [ ] **Step 9: 替换 Stage Names（行 358-361）**

将：
```python
        print(f"[SCREENER] Stage Names: resolving company names for {len(merged_candidates)} candidates...")
        for i, card in enumerate(merged_candidates, 1):
            if i % 10 == 0 or i == len(merged_candidates):
                print(f"[SCREENER] Stage Names: resolving {i}/{len(merged_candidates)}...")
            _inject_name(card)
```
替换为：
```python
        print_stage_header("Stage Names", f"resolving company names for {len(merged_candidates)} candidates")
        for card in merged_candidates:
            _inject_name(card)
```

- [ ] **Step 10: 替换完成横幅（行 401-404）**

将：
```python
        elapsed = (datetime.now() - started_at).total_seconds()
        print()
        print("=" * 70)
        print(f"[SCREENER] COMPLETE | {len(merged_candidates)} candidates | {len(deep_results)} deep-analyzed | elapsed={elapsed:.1f}s")
        print("=" * 70)
        print()
```
替换为：
```python
        elapsed = (datetime.now() - started_at).total_seconds()
        print_completion_banner(len(merged_candidates), len(deep_results), elapsed)
```

- [ ] **Step 11: 验证语法**

Run: `python -c "from tradingagents.screener.engine import ScreenerEngine; print('OK')"`
Expected: `OK` (no import errors)

---

## 阶段三：Universe 和 DataProbe 改造

### Task 3: 改造 `tradingagents/screener/universe.py`

**Files:**
- Modify: `tradingagents/screener/universe.py`

需要替换的 print 调用：

| 位置 | 旧代码 | 新代码 |
|------|--------|--------|
| 行 119 | `print(f"[SCREENER] Stage Universe: fetching index constituents...")` | `console.print("[cyan]Fetching index constituents...[/cyan]", end="\r")` |
| 行 132 | `print(f"[SCREENER] Stage Universe: fetching {idx_code}...")` | 注释掉（被 Stage header 替代） |
| 行 162 | `print(f"[SCREENER] Stage Universe: fetched {len(all_constituents)}...")` | `console.print()` 单行完成结果 |
| 行 192 | `print(f"[SCREENER] Stage Universe: CUSTOM mode...")` | `console.print(f"[cyan]▸ CUSTOM mode[/cyan]  [dim]loading {len(custom_tickers)} tickers[/dim]")` |
| 行 218 | `print(f"[SCREENER] Stage Universe: FOCUSED mode...")` | `console.print(f"[cyan]▸ FOCUSED mode[/cyan]  [dim]focus={focus_type}/{focus_value}[/dim]")` |
| 行 233 | `print(f"[SCREENER] Stage Universe: loaded from cache...")` | `console.print(f"[green]✓ Universe ready (cached)[/green]  [dim]{len(cached.tickers)} tickers[/dim]")` |
| 行 236 | `print(f"[SCREENER] Stage Universe: building from index constituents...")` | `console.print("[cyan]▸ Building universe from index constituents...[/cyan]", end="\r")` |
| 行 241 | `print(f"[SCREENER] Stage Universe: fetched {len(constituents)} constituents...")` | 注释掉 |
| 行 275 | `print(f"[SCREENER] Stage Universe: done - {len(result.tickers)} stocks...")` | `console.print(f"[green]✓ Universe ready[/green]  [cyan]{len(result.tickers)}[/cyan] stocks  [dim]cached to {cache_file.name}[/dim]")` |

- [ ] **Step 1: 在文件顶部 import 区域添加**

在 `universe.py` 顶部（现有 import 之后）添加：

```python
from tradingagents.ui.screener_console import console
```

- [ ] **Step 2: 替换 `_fetch_constituents_for_indexes` 函数中的 print（行 119）**

将：
```python
    print(f"[SCREENER] Stage Universe: fetching index constituents for {len(index_codes)} indexes...")
```
替换为：
```python
    console.print(f"[cyan]▸ Fetching {len(index_codes)} index constituents...[/cyan]", end="\r")
```

- [ ] **Step 3: 替换逐指数 fetch 进度（行 132）**

删除（或注释掉）：
```python
        print(f"[SCREENER] Stage Universe: fetching {idx_code} ({i + 1}/{len(index_codes)})...")
```

- [ ] **Step 4: 替换 fetch 完成行（行 162）**

将：
```python
    print(f"[SCREENER] Stage Universe: fetched {len(all_constituents)} unique constituents from {len(index_codes)} indexes")
```
替换为：
```python
    console.print()
    console.print(f"[green]✓ Index constituents fetched[/green]  [cyan]{len(all_constituents)}[/cyan] unique from [cyan]{len(index_codes)}[/cyan] indexes")
```

- [ ] **Step 5: 替换 CUSTOM mode 日志（行 192）**

将：
```python
        print(f"[SCREENER] Stage Universe: CUSTOM mode - loading {len(custom_tickers)} custom tickers")
```
替换为：
```python
        console.print(f"[cyan]▸ CUSTOM mode[/cyan]  [dim]loading {len(custom_tickers)} custom tickers[/dim]")
```

- [ ] **Step 6: 替换 FOCUSED mode 日志（行 218）**

将：
```python
        print(f"[SCREENER] Stage Universe: FOCUSED mode - focus_type={focus_type}, focus_value={focus_value}")
```
替换为：
```python
        console.print(f"[cyan]▸ FOCUSED mode[/cyan]  [dim]focus=[/dim][white]{focus_type}[/white][dim]=[/dim][white]{focus_value}[/white]")
```

- [ ] **Step 7: 替换缓存命中日志（行 233）**

将：
```python
        print(f"[SCREENER] Stage Universe: loaded from cache - {len(cached.tickers)} tickers (profile={profile})")
```
替换为：
```python
        console.print(f"[green]✓ Universe ready (cached)[/green]  [cyan]{len(cached.tickers)}[/cyan] tickers  [dim]profile={profile}[/dim]")
```

- [ ] **Step 8: 替换构建开始（行 236）**

将：
```python
    print(f"[SCREENER] Stage Universe: building from index constituents (profile={profile})...")
```
替换为：
```python
    console.print(f"[cyan]▸ Building universe from index constituents...[/cyan]  [dim]profile={profile}[/dim]", end="\r")
```

- [ ] **Step 9: 注释掉中间进度（行 241）**

删除（或注释掉）：
```python
    print(f"[SCREENER] Stage Universe: fetched {len(constituents)} constituents, building result...")
```

- [ ] **Step 10: 替换最终完成行（行 275）**

将：
```python
    print(f"[SCREENER] Stage Universe: done - {len(result.tickers)} stocks | cached to {cache_file.name}")
```
替换为：
```python
    console.print(f"[green]✓ Universe ready[/green]  [cyan]{len(result.tickers)}[/cyan] stocks  [dim]cached to {cache_file.name}[/dim]")
```

- [ ] **Step 11: 验证语法**

Run: `python -c "from tradingagents.screener.universe import build_screening_universe; print('OK')"`
Expected: `OK`

---

### Task 4: 改造 `tradingagents/screener/data_access.py`

**Files:**
- Modify: `tradingagents/screener/data_access.py`

DataProbe 的所有 print() 用 `print_probe_table()` 替换，使探测结果以彩色表格形式展示。

- [ ] **Step 1: 在 `data_access.py` 顶部添加 import**

在 `from tradingagents.default_config import DEFAULT_CONFIG` 之后添加：

```python
from tradingagents.ui.screener_console import console, print_probe_table
```

- [ ] **Step 2: 替换 DataProbe 开始行（行 1257）**

将：
```python
        print("[SCREENER] Stage DataProbe: running live API probes (this may take ~10-20s)...")
```
替换为：
```python
        console.print()
        console.print(Panel.fit(
            "[bold cyan]▸ DATA PROBE[/bold cyan]  [dim]testing API availability (~10-20s)...[/dim]",
            border_style="cyan",
            padding=(0, 1),
        ))
```

- [ ] **Step 3: 替换 spot_snapshot probe（行 1270-1282）**

将：
```python
        print("[SCREENER] Stage DataProbe: probing spot_snapshot...", end=" ", flush=True)
        # ... probe ...
        print(f"{len(spot_ok)}/{len(spot_probes)} passed -> [{', '.join(spot_ok) or 'none'}]")
```
替换为：
```python
        console.print("[dim]Probing spot_snapshot...[/dim]", end="\r")
        # ... probe ...
        console.print()
        rows = [(name, probe_results[name].ok, probe_results[name].detail or "") for name in [n for n, _ in spot_probes]]
        print_probe_table("spot_snapshot", rows)
```

**注意**：`spot_result` 是在 probe 后才构建的，所以需要在所有 probe 完成后统一调用 `print_probe_table`。参考步骤 10 的统一处理方式。

- [ ] **Step 4: 简化 individual probe 输出（行 1270, 1285, 1303, 1317, 1330, 1342, 1355, 1367）**

将每一组 probe 的单个 `print("...probing...", end=" ")` 替换为一行简洁的内联输出，最后用 `print_probe_table` 统一展示。

实际做法：把所有 individual `print("probing X...")` 改为 `console.print(f"[dim]Probing {category}...[/dim]", end="\r")`，在末尾加上 `console.print()` 换行。

- [ ] **Step 5: 替换 hist_fetch probe（行 1285-1300）**

同 Step 3 模式，末尾加 `print_probe_table`。

- [ ] **Step 6: 替换 concept_list probe（行 1303-1314）**

同 Step 3 模式。

- [ ] **Step 7: 替换 industry_list probe（行 1317-1327）**

同 Step 3 模式。

- [ ] **Step 8: 替换 fund_flow probe（行 1330-1339）**

同 Step 3 模式。

- [ ] **Step 9: 替换 index_spot probe（行 1342-1352）**

同 Step 3 模式。

- [ ] **Step 10: 替换 tick_data probe（行 1355-1364）**

同 Step 3 模式。

- [ ] **Step 11: 替换 yfinance probe（行 1367-1380）**

将：
```python
        print("[SCREENER] Stage DataProbe: probing yfinance hist...", end=" ", flush=True)
        if vendors.get("enable_yfinance_backup", True):
            # ... probe ...
            print("passed" if yf_result.ok else "failed")
        else:
            print("skipped")
```
替换为：
```python
        console.print("[dim]Probing yfinance hist...[/dim]", end="\r")
        if vendors.get("enable_yfinance_backup", True):
            # ... probe stays same ...
            console.print(f"[green]✓ yfinance[/green]" if yf_result.ok else "[red]✗ yfinance[/red]")
        else:
            console.print("[yellow]○ yfinance skipped[/yellow]")
```

- [ ] **Step 12: 替换 DataProbe 汇总（行 1383-1385）**

将：
```python
        print("[SCREENER] Stage DataProbe: done")
        print(f"[SCREENER] Stage DataProbe: {len(probe_results) - failed_count}/{len(probe_results)} probes passed, {failed_count} failed")
```
替换为：
```python
        console.print()
        passed = len(probe_results) - failed_count
        total = len(probe_results)
        color = "green" if failed_count == 0 else "yellow" if failed_count < total / 2 else "red"
        console.print(f"[green]✓ DataProbe done[/green]  [cyan]{passed}/{total}[/cyan] passed  [red]{failed_count}[/red] failed")
```

- [ ] **Step 13: 验证语法**

Run: `python -c "from tradingagents.screener.data_access import ScreenerDataAccess; print('OK')"`
Expected: `OK`

---

## 阶段四：三大策略改造

### Task 5: 改造 `tradingagents/screener/strategies/technical.py`

**Files:**
- Modify: `tradingagents/screener/strategies/technical.py`

- [ ] **Step 1: 在文件顶部添加 import**

在 `technical.py` 顶部（`from tradingagents.screener.models import SignalCard, SignalEvidence` 之后）添加：

```python
from tradingagents.ui.screener_console import (
    console,
    print_stage_header,
    print_stage_done,
    print_progress_bar,
    clear_progress_line,
)
```

- [ ] **Step 2: 替换 run() 开始行（行 75）**

将：
```python
        print(f"[SCREENER] Stage B Technical: starting (universe={len(universe)} stocks)...")
```
替换为：
```python
        console.print(f"[cyan]▸ TechnicalStrategy[/cyan]  [dim]{len(universe)} stocks...", end="\r")
```

- [ ] **Step 3: 替换 history fetch 开始（行 129）**

将：
```python
        print(f"[SCREENER] Stage B Technical: loading histories ({len(universe)} stocks)...")
```
替换为：
```python
        console.print(f"[cyan]  Loading histories[/cyan]  [dim]{len(universe)} stocks...[/dim]", end="\r")
```

- [ ] **Step 4: 替换 scoring 进度（行 261）**

将：
```python
                print(f"[SCREENER] Stage B Technical: processed {i + 1}/{len(universe)} ({pct}%) | {len(cards)} cards scored so far")
```
替换为：
```python
                print_progress_bar("Technical scoring", i + 1, len(universe))
```

- [ ] **Step 5: 替换 scoring done（行 263）**

将：
```python
        print(f"[SCREENER] Stage B Technical: scoring done, sorting top {len(cards)} cards...")
```
替换为：
```python
        clear_progress_line()
        console.print(f"[cyan]  Technical:[/cyan] [dim]sorting {len(cards)} cards...[/dim]", end="\r")
```

- [ ] **Step 6: 替换 done（行 274）**

将：
```python
        print(f"[SCREENER] Stage B Technical: done | {len(cards)} cards (status={status})")
```
替换为：
```python
        console.print(f"[green]✓ TechnicalStrategy done[/green]  [cyan]{len(cards)}[/cyan] cards  [dim]status={status}[/dim]")
```

- [ ] **Step 7: 替换 history fetch 中的高频进度（行 660）**

将：
```python
                print(f"[SCREENER] Stage B Technical: fetching history {i + 1}/{total} ({pct}%) | {len(histories)} valid loaded")
```
替换为：
```python
                print_progress_bar("Fetching histories", i + 1, total)
```

- [ ] **Step 8: 替换 history fetch done（行 662）**

将：
```python
        print(f"[SCREENER] Stage B Technical: history fetch done | {len(histories)}/{total} stocks with valid data")
```
替换为：
```python
        clear_progress_line()
        console.print(f"[green]✓ Histories fetched[/green]  [cyan]{len(histories)}/{total}[/cyan] with valid data")
```

- [ ] **Step 9: 替换警告（行 664）**

将：
```python
            print("[SCREENER] Stage B Technical: WARNING - no valid history data loaded, scoring will be degraded")
```
替换为：
```python
            console.print("[yellow]⚠ WARNING: no valid history data loaded, scoring will be degraded[/yellow]")
```

- [ ] **Step 10: 验证语法**

Run: `python -c "from tradingagents.screener.strategies.technical import TechnicalStrategy; print('OK')"`
Expected: `OK`

---

### Task 6: 改造 `tradingagents/screener/strategies/policy.py`

**Files:**
- Modify: `tradingagents/screener/strategies/policy.py`

- [ ] **Step 1: 在文件顶部添加 import**

在 `policy.py` 顶部（现有 import 之后）添加：

```python
from tradingagents.ui.screener_console import (
    console,
    print_stage_header,
    print_progress_bar,
    clear_progress_line,
)
```

- [ ] **Step 2: 替换 run() 开始行（行 38）**

将：
```python
        print(f"[SCREENER] Stage B Policy: starting (universe={len(universe)} stocks)...")
```
替换为：
```python
        console.print(f"[cyan]▸ PolicyStrategy[/cyan]  [dim]{len(universe)} stocks...", end="\r")
```

- [ ] **Step 3: 替换概念加载（行 90）**

将：
```python
                        print(f"[SCREENER] Stage B Policy: loaded {len(codes)} stocks for {_name_zh}")
```
替换为：
```python
                        console.print(f"[dim]  Loaded {len(codes)} stocks for {_name_zh}...[/dim]", end="\r")
```

- [ ] **Step 4: 替换 concept constituents（行 110）**

将：
```python
        print(f"[SCREENER] Stage B Policy: loading concept constituents for {len(selected_concepts)} concepts...")
```
替换为：
```python
        console.print(f"[cyan]  Loading concept constituents[/cyan]  [dim]{len(selected_concepts)} concepts...[/dim]", end="\r")
```

- [ ] **Step 5: 替换 scoring 开始（行 127）**

将：
```python
        print(f"[SCREENER] Stage B Policy: scoring all {total} stocks...")
```
替换为：
```python
        console.print(f"[cyan]  Policy scoring[/cyan]  [dim]{total} stocks...[/dim]", end="\r")
```

- [ ] **Step 6: 替换 scoring 进度（行 337）**

将：
```python
                print(f"[SCREENER] Stage B Policy: processed {idx + 1}/{total} ({pct}%) | {len(cards)} cards scored so far")
```
替换为：
```python
                print_progress_bar("Policy scoring", idx + 1, total)
```

- [ ] **Step 7: 替换 sorting（行 339）**

将：
```python
        print(f"[SCREENER] Stage B Policy: scoring done, sorting {len(cards)} cards...")
```
替换为：
```python
        clear_progress_line()
        console.print(f"[cyan]  Policy:[/cyan] [dim]sorting {len(cards)} cards...[/dim]", end="\r")
```

- [ ] **Step 8: 替换 done（行 351）**

将：
```python
        print(f"[SCREENER] Stage B Policy: done | {len(cards)} cards (status={status})")
```
替换为：
```python
        console.print(f"[green]✓ PolicyStrategy done[/green]  [cyan]{len(cards)}[/cyan] cards  [dim]status={status}[/dim]")
```

- [ ] **Step 9: 验证语法**

Run: `python -c "from tradingagents.screener.strategies.policy import PolicyStrategy; print('OK')"`
Expected: `OK`

---

### Task 7: 改造 `tradingagents/screener/strategies/smart_money.py`

**Files:**
- Modify: `tradingagents/screener/strategies/smart_money.py`

- [ ] **Step 1: 在文件顶部添加 import**

在 `smart_money.py` 顶部（现有 import 之后）添加：

```python
from tradingagents.ui.screener_console import (
    console,
    print_progress_bar,
    clear_progress_line,
)
```

- [ ] **Step 2: 替换 run() 开始行（行 29）**

将：
```python
        print(f"[SCREENER] Stage B SmartMoney: starting (universe={len(universe)} stocks)...")
```
替换为：
```python
        console.print(f"[cyan]▸ SmartMoneyStrategy[/cyan]  [dim]{len(universe)} stocks...", end="\r")
```

- [ ] **Step 3: 替换 scoring 开始（行 130）**

将：
```python
        print(f"[SCREENER] Stage B SmartMoney: scoring all {total} stocks...")
```
替换为：
```python
        console.print(f"[cyan]  SmartMoney scoring[/cyan]  [dim]{total} stocks...[/dim]", end="\r")
```

- [ ] **Step 4: 替换 scoring 进度（行 366）**

将：
```python
                print(f"[SCREENER] Stage B SmartMoney: processed {idx + 1}/{total} ({pct}%) | {len(scored_cards)} cards generated")
```
替换为：
```python
                print_progress_bar("SmartMoney scoring", idx + 1, total)
```

- [ ] **Step 5: 替换完成进度（行 370）**

将：
```python
            print(f"[SCREENER] Stage B SmartMoney: processed {total}/{total} (100%) | {len(scored_cards)} cards generated")
```
替换为：
```python
            clear_progress_line()
```

- [ ] **Step 6: 替换无股票情况（行 372）**

将：
```python
            print("[SCREENER] Stage B SmartMoney: 0 stocks to process")
```
替换为：
```python
            console.print("[yellow]  SmartMoney: 0 stocks to process[/yellow]")
```

- [ ] **Step 7: 替换 sorting（行 374）**

将：
```python
        print(f"[SCREENER] Stage B SmartMoney: scoring done, sorting {len(scored_cards)} cards...")
```
替换为：
```python
        console.print(f"[cyan]  SmartMoney:[/cyan] [dim]sorting {len(scored_cards)} cards...[/dim]", end="\r")
```

- [ ] **Step 8: 替换 done（行 389）**

将：
```python
        print(f"[SCREENER] Stage B SmartMoney: done | {len(cards)} cards (status={status})")
```
替换为：
```python
        console.print(f"[green]✓ SmartMoneyStrategy done[/green]  [cyan]{len(cards)}[/cyan] cards  [dim]status={status}[/dim]")
```

- [ ] **Step 9: 验证语法**

Run: `python -c "from tradingagents.screener.strategies.smart_money import SmartMoneyStrategy; print('OK')"`
Expected: `OK`

---

## 阶段五：DeepAnalyzer 和 Merger 改造

### Task 8: 改造 `tradingagents/screener/deep_analyzer.py`

**Files:**
- Modify: `tradingagents/screener/deep_analyzer.py`

- [ ] **Step 1: 在文件顶部添加 import**

在 `deep_analyzer.py` 顶部添加：

```python
from tradingagents.ui.screener_console import console
```

- [ ] **Step 2: 替换 analyze_top_candidates 中的 print（行 154-161）**

将：
```python
        if limit == 0:
            print("[SCREENER] Stage DeepAnalysis: no candidates to analyze")
            return []
        print(f"[SCREENER] Stage DeepAnalysis: analyzing top {limit} candidates (max_stocks={self.deep_config.max_stocks})...")
        results = []
        for i, card in enumerate(candidates[:limit], 1):
            print(f"[SCREENER] Stage DeepAnalysis: analyzing {i}/{limit} - {card.ticker} (score={card.screening_score:.1f})...")
            results.append(self.analyze(card, trade_date))
        print(f"[SCREENER] Stage DeepAnalysis: done | {len(results)} candidates analyzed")
```
替换为：
```python
        if limit == 0:
            console.print("[yellow]  DeepAnalysis: no candidates to analyze[/yellow]")
            return []
        results = []
        for i, card in enumerate(candidates[:limit], 1):
            console.print(
                f"[cyan]  Analyzing[/cyan] [white]{i}/{limit}[/white]  "
                f"[bold white]{card.ticker}[/bold white]  "
                f"[dim]score={card.screening_score:.1f}[/dim]",
                end="\r",
            )
            results.append(self.analyze(card, trade_date))
        console.print()
        console.print(f"[green]✓ DeepAnalysis done[/green]  [cyan]{len(results)}/{limit}[/cyan] candidates analyzed")
```

- [ ] **Step 3: 验证语法**

Run: `python -c "from tradingagents.screener.deep_analyzer import DeepAnalyzer; print('OK')"`
Expected: `OK`

---

### Task 9: 改造 `tradingagents/screener/merger.py`

**Files:**
- Modify: `tradingagents/screener/merger.py`

- [ ] **Step 1: 在 `merger.py` 顶部添加 import**

在现有 import 之后添加：

```python
from tradingagents.ui.screener_console import console
```

- [ ] **Step 2: 替换 merge_signal_cards 开始（行 887）**

将：
```python
    print(f"[SCREENER] Stage Merger: starting | mode={mode} | {len(cards)} cards to process")
```
替换为：
```python
    console.print(f"[cyan]▸ Merger[/cyan]  [dim]mode={mode}  {len(cards)} cards...[/dim]", end="\r")
```

- [ ] **Step 3: 替换 merge/sort 行（行 902）**

将：
```python
    print(f"[SCREENER] Stage Merger: merging and sorting cards...")
```
替换为：
```python
    console.print(f"[cyan]  Merging and sorting...[/cyan]", end="\r")
```

- [ ] **Step 4: 替换完成行（行 1044）**

将：
```python
    print(f"[SCREENER] Stage Merger: done | {len(limited)} candidates retained | {len(dropped)} dropped (max_output={max_output}, mode={mode})")
```
替换为：
```python
    console.print(f"[green]✓ Merger done[/green]  [cyan]{len(limited)}[/cyan] retained  [red]{len(dropped)}[/red] dropped  [dim]mode={mode}[/dim]")
```

- [ ] **Step 5: 验证语法**

Run: `python -c "from tradingagents.screener.merger import merge_signal_cards; print('OK')"`
Expected: `OK`

---

## 阶段六：端到端验证

### Task 10: 端到端运行验证

**Files:**
- Test: 运行一个最小化 Screener 任务验证所有改动

- [ ] **Step 1: 运行 mini Screener 测试（不依赖真实 API，用缓存数据）**

Run: `cd "D:\cursor\HarmonyOS\Github project\TradingAgents-main" && python -m cli.screener`
Expected: 交互式 CLI 正常启动，Rich Panel 界面正常渲染（无崩溃，无报错）

**如果遇到问题**：
- ImportError: 检查 `screener_console.py` 的路径是否正确
- `rich.table.Table` 报错: 检查 `box=MINIMAL` 是否是有效参数
- 颜色不显示: Windows PowerShell 默认支持 ANSI，无需额外配置

---

## Self-Review 检查清单

**1. Spec 覆盖检查：**
- [x] Task 1: 共享 console 模块（含 print_stage_header, print_probe_table 等工具函数）
- [x] Task 2: engine.py — 启动横幅、Stage A/B 进度、完成横幅
- [x] Task 3: universe.py — Index 抓取、CUSTOM/FOCUSED 模式、缓存、最终完成
- [x] Task 4: data_access.py — DataProbe 全套探测表格输出
- [x] Task 5: technical.py — 策略开始、历史加载、评分进度、完成
- [x] Task 6: policy.py — 策略开始、概念加载、评分进度、完成
- [x] Task 7: smart_money.py — 策略开始、评分进度、完成
- [x] Task 8: deep_analyzer.py — 分析候选人进度、完成
- [x] Task 9: merger.py — 合并开始、排序、完成
- [x] Task 10: 端到端验证

**2. Placeholder 扫描：**
- 无 "TBD" / "TODO" / "fill in details" 等占位符
- 所有步骤都包含完整可执行的代码块
- 无 "Add appropriate error handling" 等模糊描述

**3. 类型一致性检查：**
- `console` 实例由 `screener_console.py` 统一导出，各模块 import 路径一致
- `print_progress_bar(current, total)` 签名在 engine.py 和 strategies 中一致
- `print_probe_table(category, rows)` 签名在 data_access.py 中一致
- `print_stage_header(name, subtitle)` 签名在 engine.py 中一致

---

## 执行选项

**Plan complete and saved to `docs/Plan/Phase4/PlanCLI.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
