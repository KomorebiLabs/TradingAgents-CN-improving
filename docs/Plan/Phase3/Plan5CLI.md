# Phase5 CLI — Unified Framework & Live Dashboard

> **Goal:** 将 `cli/` 和 `tradingagents/screener/cli/` 两个独立 CLI 整合为统一入口框架，同时升级 Analyze 的 Live Dashboard 为完整的可观测性终端。

## 背景与决策

### 为什么重构

| 问题 | 现状 |
|------|------|
| 入口分散 | `python -m tradingagents` 和 `python -m cli` 各自存在，需要统一 |
| Analyze CLI 耦合高 | `app.py` 1200 行混合了问卷、执行、渲染、汇总四种职责 |
| questionary 依赖 | Analyze 问卷用 questionary，Screener 用 Rich.Prompt，视觉不统一 |
| 无返回主菜单 | 两个 CLI 执行完后直接退出，用户无法从 Screener 结果一键跳转到 Analyzer |
| 500ms 刷新过速 | Graph 每秒最多产生 1-2 个 chunk，500ms 刷新大部分时间得到重复状态，浪费渲染且造成终端闪烁 |
| Live Dashboard 数据少 | 只显示 agent 状态和消息，缺少 Skill 使用、Semantic 参数、Event Trail、Token 分布等可观测性数据 |

### 决策

1. **统一入口：** `cli/__main__.py` 作为唯一入口（`python -m cli`），转发到 `tradingagents/__main__.py`
2. **模块独立但共享 UI 层：** Analyze 和 Screener 是独立模块，共享 `cli/prompts.py` 和 `cli/static/welcome.txt`
3. **解耦问卷与渲染：** Analyze 的问卷逻辑（8 步）和 Live Dashboard（渲染）分开为独立文件
4. **刷新策略：** chunk 到达时即时刷新 + 每 3 秒定时器保底刷新
5. **复用现有资产：** `cli/static/welcome.txt`、`cli/models.py`、`cli/stats_handler.py`、`screener/cli/interactive.py` 的问卷流程全部保留并迁移
6. **返回主菜单：** 任何模块完成后显示 "返回主菜单？ [Y/n]"，保持交互连续性
7. **HTML 接口预留：** `summary.py` 提供 `html_export()` 空方法，为下一阶段 HTML 报告铺垫

---

## 目录结构

```
cli/
├── __init__.py                     ← 改造：统一入口，始终返回主菜单循环
├── __main__.py                     ← 改造：run_main_menu() 替代直接退出
├── static/
│   └── welcome.txt                 ← 保留：ASCII Logo（"Komorebi Yang"）
├── models.py                       ← 保留：AnalystType enum
├── stats_handler.py                ← 保留：StatsCallbackHandler
├── config.py                       ← 保留：CLI_CONFIG
│
├── prompts.py                      ← 新建：统一 prompt 工具（替换 questionary）
│                                    所有问卷函数基于 Rich.Prompt/Rich.Confirm
│                                    复用 TRPING_THEME 配色
│
├── analyze/
│   ├── __init__.py
│   ├── app.py                     ← 改造：问卷(8步) + 启动 + 汇总页 + 返回菜单（~300行）
│   └── run_impl.py                ← 新建：核心执行引擎，管理 Live Dashboard 生命周期
│
└── screener/
    ├── __init__.py
    └── app.py                     ← 改造：问卷(6步) + 执行 + 汇总页 + 返回菜单

tradingagents/
├── __main__.py                     ← 改造：转发到 cli/__main__.py（统一入口）
└── ui/
    ├── live_dashboard.py           ← 新建：Live Dashboard（3s刷新+即时刷新）
    ├── summary.py                  ← 新建：汇总页 + HTML 接口预留
    └── theme.py                    ← 改造：增强 Bloomberg 配色常量
```

**向后兼容（保留，不删除）：**
- `tradingagents/commands/analyze/` — 保留，旧的 `python -m tradingagents analyze` 继续工作
- `tradingagents/screener/cli/` — 保留，旧的 `python -m tradingagents screener` 继续工作

---

## 用户交互流程

```
$ python -m cli
# 或
$ python -m tradingagents

┌──────────────────────────────────────────────────────┐
│                                                      │
│    ______               ___             ___          │
│   /_  __/________ _____/ (_)___  ____ _/   |        │
│    / / / ___/ __ `/ __  / / __ \/ __ `/ /| |        │
│   / / / /  / /_/ / /_/ / / / / / /_/ / ___ |       │
│  /_/ /_/   \__,_/\__,_/_/_/ /_/\__, /_/  |_|       │
│                              /____/                  │
│           Komorebi Yang（Learning）                  │
│                                                      │
│  ╔════════════════════════════════════════════════╗   │
│  ║  TradingAgents CLI — Main Dashboard            ║   │
│  ╚════════════════════════════════════════════════╝   │
│                                                      │
│  [1] Screener   Stage 1: 选股筛选                   │
│  [2] Analyzer   Stage 2: 深度多智能体分析            │
│  [3] Report     查看报告                            │
│  [Q] Quit       退出                               │
│                                                      │
│  > 选择模块 (1/2/3/Q): _                           │
└──────────────────────────────────────────────────────┘

→ 选 1（Screener）
  Step 1: 模式选择  FULL / FOCUSED / CUSTOM
  Step 2: 交易日期  YYYY-MM-DD（默认今天）
  Step 3: 范围配置  （FULL跳过，FOCUSED选板块/主题/指数，CUSTOM输股票列表）
  Step 4: 输出选项  最大标的数 / Deep Analyzer / 周末运行 / 输出目录
  Step 5: 配置总览  Panel 显示所有配置，确认执行
  Step 6: 执行
    ┌─ PROGRESS ─────────┬─ SKILL & SEMANTIC ────────┐
    │ Stage 1  ■■■□      │ Skills: market ✓ social ✓│
    │ Stage A   ● RUNNING│ Semantic: temp=0.7        │
    │ Stage B   ○ WAIT   │ Memory: 2 hits            │
    ├────────────────────┴───────────────────────────┤
    │ [EVENT TRAIL] 12:30 StageA→StageB  12:32 分析中│
    ├─────────────────────────────────────────────────┤
    │ LLM: 5  Tools: 12  ↑3.2K ↓1.1K  ⏱ 00:42      │
    └─────────────────────────────────────────────────┘
  运行结束 → Summary 汇总页 → "返回主菜单？ [Y/n] _"

→ 选 2（Analyzer）
  Step 1: 股票代码  SPY / 600519 / NVDA 等
  Step 2: 分析日期  YYYY-MM-DD（默认今天）
  Step 3: 输出语言  中文 / English / 日文 等12种
  Step 4: 分析团队  Market / Social / News / Fundamentals（多选）
  Step 5: 研究深度  Shallow / Medium / Deep
  Step 6: LLM 提供商  OpenAI / Google / DeepSeek 等10种
  Step 7: Thinking模型  quick模型 + deep模型
  Step 8: 推理配置  （根据提供商显示或不显示）
  执行（实时 Dashboard 同步）
  运行结束 → Summary 汇总页 → "返回主菜单？ [Y/n] _"
```

---

## Task 1: 统一入口层

**目标：** `cli/__main__.py` 作为统一入口，`tradingagents/__main__.py` 转发到它。

### 1.1 改造 `cli/__main__.py`

- [ ] 读取 `cli/static/welcome.txt` 内容并 print
- [ ] 实现 `run_main_menu()` 函数：显示主菜单、读取用户输入、调用对应模块
- [ ] 选 1 → 调用 `cli.screener.app.run()`，完成后继续 `run_main_menu()`
- [ ] 选 2 → 调用 `cli.analyze.app.run()`，完成后继续 `run_main_menu()`
- [ ] 选 3 → 调用报告查看器，之后继续 `run_main_menu()`
- [ ] 选 Q → 退出

### 1.2 改造 `tradingagents/__main__.py`

- [ ] `main()` 回调直接 `from cli.__main__ import run_main_menu; run_main_menu()`
- [ ] 保留 `--version` 和 `--info` 选项（这两个不进入主菜单循环）
- [ ] `analyze` 和 `screener` 子命令保持（向后兼容），但它们执行完后调用 `cli.__main__.run_main_menu()` 而非退出

---

## Task 2: 统一 Prompt 层

**目标：** 新建 `cli/prompts.py`，将 `cli/utils.py` 中所有问卷函数的**交互逻辑完整保留**，只把 `questionary` 库替换为 Rich.Prompt/Rich.Confirm。

### 2.1 创建 `cli/prompts.py` — 完整函数清单

每个函数的**交互逻辑、验证规则、样式颜色**必须与原 `cli/utils.py` 完全一致。

#### 基础工具函数

```python
# cli/prompts.py

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table

console = Console(theme=TRADING_THEME)

def print_step_header(n: int, total: int, title: str) -> None:
    """统一样式：─── Step N/T: Title ───"""
    console.print(f"[bold cyan]─── Step {n}/{total}: {title} ───[/bold cyan]")

def create_question_box(title: str, prompt: str, default: str | None = None) -> Panel:
    """复用 commands/analyze/app.py 中 create_question_box() 的样式"""
    content = f"[bold]{title}[/bold]\n[dim]{prompt}[/dim]"
    if default:
        content += f"\n[dim]Default: {default}[/dim]"
    return Panel(content, border_style="blue", padding=(1, 2))
```

#### `ask_ticker() → str`
- **原函数：** `cli/utils.py` 的 `get_ticker()`
- **交互：** `Prompt.ask("Enter the exact ticker symbol to analyze (Examples: SPY, CNC.TO, 7203.T, 0700.HK):", default="SPY", choices=None)`
- **样式：** 绿色输入提示
- **验证：** 非空字符串，`.strip().upper()` 规范化
- **失败：** `console.print("[red]No ticker symbol provided. Exiting...[/red]"); exit(1)`

#### `ask_date(prompt, default_today) → str`
- **原函数：** `cli/utils.py` 的 `get_analysis_date()`
- **交互：** `while True` 循环，`Prompt.ask()` 输入 YYYY-MM-DD
- **验证：** `datetime.strptime(date_str, "%Y-%m-%d")` 成功 + 非未来日期
- **失败提示：** `[red]Invalid date format[/red]` 或 `[red]Date cannot be in future[/red]`
- **成功后：** `console.print(f"[green]Date: {date}[/green]")`

#### `ask_analysts() → List[AnalystType]`
- **原函数：** `cli/utils.py` 的 `select_analysts()`
- **原样式：** questionary checkbox，绿色选中标记
- **交互：** 使用 `Rich.Prompt` + 手动多选机制
  - 显示 4 个选项：Market Analyst / Social Media Analyst / News Analyst / Fundamentals Analyst
  - 键盘空格选择/取消，Enter 确认
  - 指令提示：`"Press Space to select/unselect, Enter when done"`
- **验证：** 至少选 1 个，否则重新提示
- **成功后：** `console.print(f"[green]Selected analysts: market, news[/green]")`

#### `ask_research_depth() → int`
- **原函数：** `cli/utils.py` 的 `select_research_depth()`
- **选项（黄色高亮）：**
  - `"Shallow - Quick research, few debate and strategy discussion rounds"` → 1
  - `"Medium - Middle ground, moderate debate rounds and strategy discussion"` → 3
  - `"Deep - Comprehensive research, in depth debate and strategy discussion"` → 5
- **交互：** `Prompt.ask(..., choices=[...], default="Medium")`

#### `ask_llm_provider() → Tuple[str, str|None]`
- **原函数：** `cli/utils.py` 的 `select_llm_provider()`
- **选项（10个，洋红色高亮）：**
  - OpenAI → `"openai"`, base_url = `"https://api.openai.com/v1"`
  - Google → `"google"`, base_url = `None`
  - Anthropic → `"anthropic"`, base_url = `"https://api.anthropic.com/"`
  - xAI → `"xai"`, base_url = `"https://api.x.ai/v1"`
  - DeepSeek → `"deepseek"`, base_url = `"https://api.deepseek.com"`
  - Qwen → `"qwen"`, base_url = `"https://dashscope.aliyuncs.com/compatible-mode/v1"`
  - GLM → `"glm"`, base_url = `"https://open.bigmodel.cn/api/paas/v4/"`
  - OpenRouter → `"openrouter"`, base_url = `"https://openrouter.ai/api/v1"`
  - Azure OpenAI → `"azure"`, base_url = `None`
  - Ollama → `"ollama"`, base_url = `"http://localhost:11434/v1"`
- **交互：** `Prompt.ask(..., choices=[...], default="OpenAI")`

#### `ask_model(provider, mode: "quick"|"deep") → str`
- **原函数：** `cli/utils.py` 的 `_select_model()` + `select_shallow_thinking_agent()` + `select_deep_thinking_agent()`
- **逻辑分支：**
  - **OpenRouter：** 调用 `_fetch_openrouter_models()` 从 `https://openrouter.ai/api/v1/models` 抓取前 5 个模型显示，选项包含 `"Custom model ID"` → 若选 custom 则二次输入
  - **Azure：** 直接 `Prompt.ask("Enter Azure deployment name (quick-thinking):")`，非空验证
  - **其他（OpenAI/Google/DeepSeek等）：** 调用 `get_model_options(provider, mode)` 渲染下拉，最后一项为 `"Custom model ID"`
- **洋红色高亮**

#### `ask_provider_thinking_config(provider) → Dict`
- **原函数：** `cli/utils.py` 的 `ask_gemini_thinking_config()` / `ask_openai_reasoning_effort()` / `ask_anthropic_effort()`
- **逻辑分支：**
  - **Google（绿色）：** `"Enable Thinking (recommended)"` → `"high"` / `"Minimal/Disable Thinking"` → `"minimal"`
  - **OpenAI（青色）：** `"Medium (Default)"` → `"medium"` / `"High (More thorough)"` → `"high"` / `"Low (Faster)"` → `"low"`
  - **Anthropic（青色）：** `"High (recommended)"` → `"high"` / `"Medium (balanced)"` → `"medium"` / `"Low (faster, cheaper)"` → `"low"`
  - **其他：** Step 8 跳过，返回 `None`

#### `ask_output_language() → str`
- **原函数：** `cli/utils.py` 的 `ask_output_language()`
- **选项（黄色高亮，12个）：**
  - English / Chinese / Japanese / Korean / Hindi / Spanish / Portuguese / French / German / Arabic / Russian
  - 末尾：`"Custom language"` → 二次输入自定义语言名
- **交互：** `Prompt.ask(..., choices=[...], default="English")`

### 2.2 迁移步骤

- [ ] 创建 `cli/prompts.py`，实现上述所有函数
- [ ] 保留 `cli/utils.py` 的 `TICKER_INPUT_EXAMPLES`、`ANALYST_ORDER` 常量定义
- [ ] 保留 `cli/utils.py` 的 `normalize_ticker_symbol()` 函数
- [ ] `cli/utils.py` 改为 `from cli.prompts import *`，保持向后兼容导入
- [ ] 验证所有 8 个问卷函数与原行为一致（输入验证、默认值、样式颜色）

### 2.3 Task 2 详细检查清单

| # | 函数 | 来源 | 交互类型 | 颜色 | 验证 | 特殊逻辑 |
|---|------|------|---------|------|------|---------|
| 1 | `ask_ticker()` | `get_ticker()` | text | green | 非空 | `.upper()` |
| 2 | `ask_date()` | `get_analysis_date()` | text+loop | green | YYYY-MM-DD + 非未来 | while True |
| 3 | `ask_analysts()` | `select_analysts()` | checkbox | green | 至少1个 | 多选 |
| 4 | `ask_research_depth()` | `select_research_depth()` | select | yellow | 必须选 | 3个选项→1/3/5 |
| 5 | `ask_llm_provider()` | `select_llm_provider()` | select | magenta | 必须选 | 10个选项 |
| 6 | `ask_model()` | `_select_model()` | select/text | magenta | 非空 | OpenRouter API抓取 |
| 7 | `ask_provider_thinking_config()` | 3个函数 | select | cyan/green | 必须选 | provider分支 |
| 8 | `ask_output_language()` | `ask_output_language()` | select | yellow | 必须选 | custom二次输入 |

---

## Task 3: Screener CLI 重构

**目标：** 将 `tradingagents/screener/cli/interactive.py` 的问卷流程迁移到 `cli/screener/app.py`，复用 `cli/prompts.py`。

### 3.1 创建 `cli/screener/app.py`

- [ ] 导入 `cli/prompts.py` 替代原来的 `Rich.Prompt` / `Rich.Confirm`
- [ ] 迁移 `_prompt_mode()` — 使用 `prompts.ask_select()`
- [ ] 迁移 `_prompt_date()` — 使用 `prompts.ask_date()`
- [ ] 迁移 `_prompt_focus()` — 使用 `prompts.ask_select()` + `prompts.ask_text()`
- [ ] 迁移 `_prompt_tickers_or_universe()` — 使用 `prompts.ask_select()` + `prompts.ask_text()`
- [ ] 迁移 `_prompt_options()` — 使用 `prompts.ask_text()` + `prompts.ask_confirm()`
- [ ] `interactive()` 流程保持：6 步 → 汇总确认 → 执行 → 汇总页 → "返回主菜单？"

### 3.2 创建 `cli/screener/run_impl.py`

- [ ] 从 `tradingagents/screener/cli/commands/run_impl.py` 迁移核心执行逻辑
- [ ] 运行结束后调用 `tradingagents.ui.summary.print_summary(result, module_type="screener")`
- [ ] 将 `raise typer.Exit(code=0)` 替换为 `return`（由上层 `app.py` 处理返回菜单）

---

## Task 4: Analyze CLI 重构（解耦 + Live Dashboard）

**目标：** 将 `tradingagents/commands/analyze/app.py` 的问卷流程拆分到 `cli/analyze/app.py`，执行引擎拆分到 `cli/analyze/run_impl.py`，并升级 Live Dashboard。

### 4.0 原 `app.py` 中的关键逻辑（必须保留）

以下是原 `tradingagents/commands/analyze/app.py` 中 `get_user_selections()` 的完整流程，迁移时**一个字都不能少**：

#### Step 0 — 启动欢迎（Line 469-498）

```python
# 读取 cli/static/welcome.txt 并 print
# 创建 welcome Panel：
#   - 标题: "Welcome to TradingAgents"
#   - 副标题: "Multi-Agents LLM Financial Trading Framework"
#   - 内容包含: ASCII logo + 工作流说明 + GitHub 链接
# fetch_announcements() 获取公告并显示（静默失败）

# 定义辅助函数 create_question_box(title, prompt, default=None):
#   - 返回 Panel(border_style="blue", padding=(1,2))
#   - 内容: "[bold]{title}[/bold]\n[dim]{prompt}[/dim]\n[dim]Default: {default}[/dim]"
```

#### Step 1 — Ticker（Line 508-516）

```python
console.print(create_question_box(
    "Step 1: Ticker Symbol",
    "Enter the exact ticker symbol to analyze, including exchange suffix when needed (examples: SPY, CNC.TO, 7203.T, 0700.HK)",
    "SPY"
))
ticker = ask_ticker()  # 来自 cli/prompts.py
```

#### Step 2 — Date（Line 518-527）

```python
default_date = datetime.datetime.now().strftime("%Y-%m-%d")
console.print(create_question_box("Step 2: Analysis Date", "Enter the analysis date (YYYY-MM-DD)", default_date))
date = ask_date("Enter the analysis date (YYYY-MM-DD):", default_date)
```

#### Step 3 — Output Language（Line 529-536）

```python
console.print(create_question_box(
    "Step 3: Output Language",
    "Select the language for analyst reports and final decision"
))
language = ask_output_language()
```

#### Step 4 — Analysts Team（Line 538-547）

```python
console.print(create_question_box("Step 4: Analysts Team", "Select your LLM analyst agents for the analysis"))
selected_analysts = ask_analysts()
console.print(f"[green]Selected analysts:[/green] {', '.join(a.value for a in selected_analysts)}")
```

#### Step 5 — Research Depth（Line 549-555）

```python
console.print(create_question_box("Step 5: Research Depth", "Select your research depth level"))
depth = ask_research_depth()
```

#### Step 6 — LLM Provider（Line 557-563）

```python
console.print(create_question_box("Step 6: LLM Provider", "Select your LLM provider"))
provider, backend_url = ask_llm_provider()
```

#### Step 7 — Thinking Agents（Line 565-572）

```python
console.print(create_question_box("Step 7: Thinking Agents", "Select your thinking agents for analysis"))
shallow = ask_model(provider, "quick")
deep = ask_model(provider, "deep")
```

#### Step 8 — Provider-Specific Config（Line 574-603）

```python
thinking_level = None
reasoning_effort = None
anthropic_effort = None
if provider.lower() == "google":
    console.print(create_question_box("Step 8: Thinking Mode", "Configure Gemini thinking mode"))
    thinking_level = ask_provider_thinking_config(provider)  # 返回 {"thinking_level": "high"}
elif provider.lower() == "openai":
    console.print(create_question_box("Step 8: Reasoning Effort", "Configure OpenAI reasoning effort level"))
    reasoning_effort = ask_provider_thinking_config(provider)  # 返回 "medium"|"high"|"low"
elif provider.lower() == "anthropic":
    console.print(create_question_box("Step 8: Effort Level", "Configure Anthropic effort level"))
    anthropic_effort = ask_provider_thinking_config(provider)  # 返回 "high"|"medium"|"low"
```

#### 配置字典组装（Line 607-614）

```python
config = {
    "ticker": ticker,
    "date": date,
    "output_language": language,
    "analysts": selected_analysts,
    "research_depth": depth,
    "llm_provider": provider,
    "backend_url": backend_url,
    "shallow_thinking_model": shallow,
    "deep_thinking_model": deep,
    "thinking_level": thinking_level,
    "reasoning_effort": reasoning_effort,
    "anthropic_effort": anthropic_effort,
}
return config
```

### 4.1 创建 `cli/analyze/app.py`（~300 行）

```python
"""TradingAgents Analyze CLI — Stage 2: Multi-Agent Deep Analysis.

运行方式：
    python -m cli.analyze       -- 交互问卷
    python -m cli analyze        -- 同上（通过 cli/__main__.py 入口）
"""

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.align import Align
from rich.panel import Panel
from rich.prompt import Confirm

from tradingagents.ui.theme import TRADING_THEME
from cli.prompts import (
    ask_ticker, ask_date, ask_output_language,
    ask_analysts, ask_research_depth,
    ask_llm_provider, ask_model, ask_provider_thinking_config,
    create_question_box,
)

console = Console(theme=TRADING_THEME)

# === 启动欢迎 ===
def _print_welcome() -> None:
    """打印 ASCII logo + 欢迎 Panel + 公告（来自原 app.py Line 469-498）"""
    # 读取 cli/static/welcome.txt
    with open(Path(__file__).parent.parent / "static" / "welcome.txt", encoding="utf-8") as f:
        ascii_art = f.read()

    welcome_content = f"{ascii_art}\n"
    welcome_content += "[bold green]TradingAgents: Multi-Agents LLM Financial Trading Framework - CLI[/bold green]\n\n"
    welcome_content += "[bold]Workflow Steps:[/bold]\n"
    welcome_content += "I. Analyst Team → II. Research Team → III. Trader → IV. Risk Management → V. Portfolio Management\n\n"
    welcome_content += "[dim]Built by [Tauric Research](https://github.com/TauricResearch)[/dim]"

    console.print(Align.center(Panel(
        welcome_content,
        border_style="green",
        padding=(1, 2),
        title="Welcome to TradingAgents",
        subtitle="Multi-Agents LLM Financial Trading Framework",
    )))
    console.print()

    # 获取公告
    try:
        from tradingagents.commands.analyze.utils import fetch_announcements, display_announcements
        announcements = fetch_announcements()
        display_announcements(console, announcements)
    except Exception:
        pass  # 静默失败

# === 问卷流程 ===
def get_user_config() -> dict:
    """执行 8 步问卷，返回配置字典"""
    _print_welcome()

    console.print(create_question_box(
        "Step 1: Ticker Symbol",
        "Enter the exact ticker symbol to analyze, including exchange suffix when needed (examples: SPY, CNC.TO, 7203.T, 0700.HK)",
        "SPY"
    ))
    ticker = ask_ticker()

    default_date = datetime.now().strftime("%Y-%m-%d")
    console.print(create_question_box("Step 2: Analysis Date", "Enter the analysis date (YYYY-MM-DD)", default_date))
    date = ask_date("Enter the analysis date (YYYY-MM-DD):", default_date)

    console.print(create_question_box("Step 3: Output Language", "Select the language for analyst reports and final decision"))
    language = ask_output_language()

    console.print(create_question_box("Step 4: Analysts Team", "Select your LLM analyst agents for the analysis"))
    selected_analysts = ask_analysts()
    console.print(f"[green]Selected analysts:[/green] {', '.join(a.value for a in selected_analysts)}")

    console.print(create_question_box("Step 5: Research Depth", "Select your research depth level"))
    depth = ask_research_depth()

    console.print(create_question_box("Step 6: LLM Provider", "Select your LLM provider"))
    provider, backend_url = ask_llm_provider()

    console.print(create_question_box("Step 7: Thinking Agents", "Select your thinking agents for analysis"))
    shallow = ask_model(provider, "quick")
    deep = ask_model(provider, "deep")

    # Step 8: Provider-specific
    thinking_level = reasoning_effort = anthropic_effort = None
    p = provider.lower()
    if p == "google":
        console.print(create_question_box("Step 8: Thinking Mode", "Configure Gemini thinking mode"))
        thinking_level = ask_provider_thinking_config(provider)
    elif p == "openai":
        console.print(create_question_box("Step 8: Reasoning Effort", "Configure OpenAI reasoning effort level"))
        reasoning_effort = ask_provider_thinking_config(provider)
    elif p == "anthropic":
        console.print(create_question_box("Step 8: Effort Level", "Configure Anthropic effort level"))
        anthropic_effort = ask_provider_thinking_config(provider)

    return {
        "ticker": ticker,
        "date": date,
        "output_language": language,
        "analysts": selected_analysts,
        "research_depth": depth,
        "llm_provider": provider,
        "backend_url": backend_url,
        "shallow_thinking_model": shallow,
        "deep_thinking_model": deep,
        "thinking_level": thinking_level,
        "reasoning_effort": reasoning_effort,
        "anthropic_effort": anthropic_effort,
    }

# === 主入口 ===
def run() -> None:
    """CLI.analyze 主入口：问卷 → 执行 → 汇总 → 返回菜单"""
    config = get_user_config()

    from cli.analyze.run_impl import run_analysis
    result = run_analysis(config)

    from tradingagents.ui.summary import print_summary
    print_summary(result, module_type="analyzer")

    if Confirm.ask("[cyan]返回主菜单？[/cyan]", default=True):
        from cli.__main__ import run_main_menu
        run_main_menu()
```

### 4.2 创建 `cli/analyze/run_impl.py`（完整实现）

```python
"""TradingAgents Analyze 执行引擎。

完整复现原 app.py 第 935-1179 行的所有逻辑。
职责：
1. 接收 config 字典，组装 TradingAgentsGraph
2. 创建并管理 LiveDashboard（chunk 即时刷新 + 3s 定时器保底）
3. 处理 graph.stream() 的所有 chunk 解析（Analyst → Research → Trading → Risk → Portfolio）
4. 日志记录（message.log, tool_calls.log, 各报告文件增量写入）
5. 执行完成后返回 result 字典（含 final_state, decision, stats）

=== 原 app.py 关键逻辑清单（必须保留）===

① TradingAgentsGraph 初始化（Line 961-966）
    graph = TradingAgentsGraph(selected_analyst_keys, config=config, debug=True, callbacks=[stats_handler])

② MessageBuffer 初始化（Line 968-969）
    message_buffer.init_for_analysis(selected_analyst_keys)

③ 结果目录创建（Line 974-980）
    results_dir = Path(config["results_dir"]) / ticker / date
    报告写入: 1_analysts/, 2_research/, 3_trading/, 4_risk/, 5_portfolio/
    日志写入: message_tool.log（每条消息 + 每个 tool call）

④ 日志装饰器（Line 982-1020）
    save_message_decorator: 消息 → message_tool.log
    save_tool_call_decorator: tool call → message_tool.log
    save_report_section_decorator: 报告内容 → 各 report_section 文件（增量写入）

⑤ 初始状态设置（Line 1027-1049）
    - message_buffer.add_message("System", f"Selected ticker: {ticker}")
    - message_buffer.add_message("System", f"Analysis date: {date}")
    - message_buffer.add_message("System", f"Selected analysts: ...")
    - 第一个 analyst 状态设为 "in_progress"

⑥ graph.stream() 主循环（Line 1062-1160）
    for chunk in graph.graph.stream(init_agent_state, **args):
        消息去重（msg_id in _processed_message_ids）
        classify_message_type() 分类: User/Agent/Data/Control/System
        tool_calls 提取并记录
        update_analyst_statuses() — Analyst 状态机
        investment_debate_state 处理 → Research Team 状态转移
        trader_investment_plan 处理 → Trading Team 状态转移
        risk_debate_state 处理 → Risk Team 状态转移
        dashboard.update() 即时刷新

⑦ Agent 状态转移机（Line 819-858）
    ANALYST_ORDER = ["market", "social", "news", "fundamentals"]
    流程: Analyst N 全部 completed → Bull Researcher in_progress → 全部报告 → Trader in_progress
    → Risk: Aggressive/Conservative/Neutral → Portfolio Manager

⑧ 最终处理（Line 1162-1179）
    final_state = graph._synchronize_structured_state(trace[-1])
    decision = graph.process_signal(final_state["final_trade_decision"])
    所有 agent → completed
    update_display() 最后一次刷新

⑨ Live 刷新策略替换（Line 1025 原文）
    原文: with Live(layout, refresh_per_second=4) as live:
    改为: with Live(layout, refresh_per_second=0.33) as live:
          + chunk 到达时立即 live.update(dashboard.update())

⑩ post-analysis 流程（Line 1181-1204）
    - console.print("[bold cyan]Analysis Complete![/cyan]")
    - typer.prompt("Save report?", default="Y") → 调用 save_report_to_disk()
    - typer.prompt("Display full report on screen?", default="Y") → display_complete_report()
```

### 4.3 升级 `tradingagents/ui/live_dashboard.py`（详细面板定义）

```python
# LiveDashboard 类面板结构（对应原 app.py create_layout() 的布局）

# Panel 1: PROGRESS — 4 Stage + Agent 状态
#   Stage 1: Universe/CSI    [■□□□] pending
#   Stage A: Strategy Filter  [■■■□] completed
#   Stage B: Deep Analysis    [●○○○] running
#   Stage C: Merger           [○○○○] pending
#   Agent  : Researcher_A    [✓]  Researcher_B [●]  Trader [○]

# Panel 2: SKILL & SEMANTIC — Agent 内部可观测性
#   Skills: market(✓) social(✓) news(●) fundamentals(○)
#   Semantic: temp=0.7  top_p=0.9  max_tokens=4096
#   Memory: 2 hits | 15 context tokens

# Panel 3: EVENT TRAIL — 时间顺序事件流
#   [12:30:01] StageA.start
#   [12:30:45] StageA.complete (3 candidates)
#   [12:31:02] StageB.start (deep analysis)
#   [12:32:18] Researcher_A.thinking...

# Panel 4: METRICS BAR（Footer）
#   LLM: 5  Tools: 12  ↑3.2K  ↓1.1K  ⏱ 00:42
```

### 4.4 创建 `tradingagents/ui/summary.py`（Analyzer 汇总格式）

```python
# Analyzer 汇总内容（来自原 app.py Line 1181-1204）

def print_summary(result: dict, module_type: str) -> None:
    if module_type == "analyzer":
        # 决策结果 Panel
        console.print(Panel(
            f"[bold green]Analysis Complete![/bold green]\n\n"
            f"[cyan]Ticker:[/cyan] {result['ticker']}\n"
            f"[cyan]Decision:[/cyan] {result['decision']}\n"
            f"[cyan]Confidence:[/cyan] {result['confidence']}%\n"
            f"[cyan]Execution Time:[/cyan] {result['elapsed_time']}\n"
            f"[cyan]LLM Calls:[/cyan] {result['llm_calls']}\n"
            f"[cyan]Token Usage:[/cyan] ↑{result['tokens_in']}  ↓{result['tokens_out']}",
            title="TradingAgents Analysis Summary",
            border_style="green",
        ))

        # 报告保存提示
        if Confirm.ask("[cyan]Save report?[/cyan]", default=True):
            # 写入 reports/{TICKER}_{TIMESTAMP}/ 各子目录
            pass

        # 报告展示
        if Confirm.ask("[cyan]Display full report on screen?[/cyan]", default=True):
            # console.print(Panel(Markdown(report), ...))
            pass

        # HTML 接口预留（下一阶段）
        # def html_export(result, output_path) -> str: ...
        # return output_path

    elif module_type == "screener":
        # 复用 tradingagents/screener/cli/formatters/terminal.py 的 print_executive_summary()
        from tradingagents.screener.cli.formatters.terminal import print_executive_summary
        print_executive_summary(result['screener_result'], result['date'], result.get('output_dir'))
```

### 4.5 Task 4 详细检查清单

| # | 文件/函数 | 来源行数 | 关键操作 |
|---|---------|---------|---------|
| 1 | `cli/analyze/app.py` | 新建 | 读取 welcome.txt + 8 步问卷 + 组装 config |
| 2 | `cli/analyze/run_impl.py` | 新建 | TradingAgentsGraph 初始化 + graph.stream() 循环 + Dashboard 刷新 |
| 3 | `tradingagents/ui/live_dashboard.py` | 新建 | 4-panel Layout + 即时刷新 + 3s 定时器 |
| 4 | `tradingagents/ui/summary.py` | 新建 | Analyzer 决策汇总 + Screener 汇总 + html_export() 空方法 |
| 5 | 问卷 8 步 | `app.py:466-614` | 全部迁移到 `cli/analyze/app.py.get_user_config()` |
| 6 | 欢迎页 | `app.py:469-498` | 迁移到 `_print_welcome()` |
| 7 | 公告获取 | `utils.py` | `fetch_announcements()` / `display_announcements()` 保留 |
| 8 | config 组装 | `app.py:607-614` | 保留字段完整（11 个 key） |
| 9 | Graph 初始化 | `app.py:961-966` | `TradingAgentsGraph(selected_analyst_keys, config, debug=True, callbacks=[stats_handler])` |
| 10 | MessageBuffer | `app.py:968-969` | `message_buffer.init_for_analysis(selected_analyst_keys)` |
| 11 | 结果目录 | `app.py:974-980` | 创建 `1_analysts/` / `2_research/` / `3_trading/` / `4_risk/` / `5_portfolio/` |
| 12 | 日志装饰器 | `app.py:982-1020` | 3 个 decorator（message / tool_call / report_section）|
| 13 | 初始消息 | `app.py:1027-1043` | System 消息 × 3 + 第一个 analyst 设为 in_progress |
| 14 | chunk 主循环 | `app.py:1062-1160` | 消息去重 / classify_message_type / 状态转移机 / 即时刷新 |
| 15 | 状态转移机 | `app.py:819-858` | Analyst → Research → Trading → Risk → Portfolio 完整链路 |
| 16 | Agent 名称映射 | `app.py:803-816` | ANALYST_ORDER, ANALYST_AGENT_NAMES, ANALYST_REPORT_MAP |
| 17 | 消息分类 | `app.py:902-925` | classify_message_type(): User/Agent/Data/Control/System |
| 18 | 工具参数格式化 | `app.py:928-933` | format_tool_args()，超过 80 字符截断 |
| 19 | 最终同步 | `app.py:1162-1164` | `_synchronize_structured_state()` + `process_signal()` |
| 20 | 报告保存 | `app.py:645-732` | `save_report_to_disk()` — 5 个子目录 + complete_report.md |
| 21 | 报告展示 | `app.py:735-793` | `display_complete_report()` — 5 个 Section Panel |
| 22 | 刷新策略 | `app.py:1025` | `refresh_per_second=4` → `0.33` + 即时刷新 |
| 23 | post-analysis 交互 | `app.py:1181-1204` | "Save report?" + "Display full report?" |

---

## Task 5: Theme 增强

**目标：** 统一所有 UI 元素的配色标准。

- [ ] `tradingagents/ui/theme.py` — 补充 CLI 专用的 panel_style 字典
- [ ] 确保 `cli/prompts.py` 中所有 Rich 组件使用 `TRADING_THEME`
- [ ] `cli/static/welcome.txt` 的 ASCII Art 保持不变

---

## 实现顺序

| 优先级 | Task | 说明 | 依赖 |
|--------|------|------|------|
| P0 | Task 2 | 统一 Prompt 层 | 无 — 所有问卷依赖它 |
| P0 | Task 1 | 统一入口层 | 无 |
| P0 | Task 4.3 | LiveDashboard 核心类 | Task 2 |
| P0 | Task 4.4 | Summary 汇总页 | Task 1 |
| P0 | Task 4.1 | Analyze app.py | Task 2, Task 4.3 |
| P0 | Task 4.2 | Analyze run_impl.py | Task 4.1, Task 4.3, Task 4.4 |
| P1 | Task 3 | Screener CLI 重构 | Task 2 |
| P1 | Task 5 | Theme 增强 | Task 1 |

**建议执行顺序：** Task 2 → Task 1 → Task 4.3 → Task 4.4 → Task 4.1 → Task 4.2 → Task 3 → Task 5

---

## 验证计划

**Step 1: CLI 入口验证**
```bash
python -m cli
# 期望：显示 welcome.txt + 主菜单，选择 Q 正常退出
```

**Step 2: Screener 向后兼容验证**
```bash
python -m tradingagents screener
# 期望：问卷流程正常，完成后显示 "返回主菜单？" 并回到主菜单
```

**Step 3: Analyze 向后兼容验证**
```bash
python -m tradingagents analyze
# 期望：8 步问卷正常，Live Dashboard 正常渲染（无报错）
```

**Step 4: Live Dashboard 刷新验证**
- 确认 Dashboard 在 chunk 到达时即时刷新
- 确认 3 秒内无新数据时定时器触发保底刷新
- 确认 Skill 使用、Event Trail 等新 panel 正常显示

**Step 5: 返回主菜单验证**
- Screener 执行完成后输入 Y → 回到主菜单
- Analyzer 执行完成后输入 Y → 回到主菜单
- 再次选 Q → 正常退出

---

## 与原 Plan5CLI.md（Task A-E）的关系

原计划文件中 Task A-E 的内容（Live Dashboard 详细实现）与本计划中 **Task 4.3** 对应，内容基本一致，刷新频率已修正为 3 秒。本计划在此基础上新增：

1. 统一入口层（Task 1）
2. 统一 Prompt 层（Task 2）
3. Screener CLI 重构（Task 3）
4. Analyze CLI 解耦重构（Task 4.1, 4.2, 4.4）
5. Summary 汇总页（Task 4.4）

---

## 附录：刷新建策略详解

```
graph.stream() 产生 chunk
    ↓
parse_chunk(chunk) 解析可观测数据（event_trail, semantic_slots, skill_audit）
    ↓
dashboard.update()  ← 即时刷新（不等定时器）
    ↓
同时 Timer(3s) 触发 dashboard.update()  ← 保底刷新（更新时间戳、Token 计数）
```

**为什么不用 500ms：**
- Graph 每秒最多产生 1-2 个 chunk，500ms 刷新大部分时候拿到完全相同的状态
- 高频刷新导致终端内容抖动，用户阅读体验差
- Token 统计是批量更新的，不会每 500ms 有变化
- 3 秒刷新让用户有足够时间阅读每个状态变化



<!-- 后面的旧计划实现内容已移除 -->
