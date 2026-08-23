"""Rich-based prompts to replace questionary library in the CLI."""
from __future__ import annotations

from datetime import datetime
from typing import List, Tuple, Literal
import requests

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from tradingagents.ui.theme import TRADING_THEME
from cli.models import AnalystType
from tradingagents.llm_clients.model_catalog import get_model_options

console = Console(theme=TRADING_THEME)

TICKER_INPUT_EXAMPLES = "A股输入6位代码: 600519 / 000001 / 300750；港股: 0700.HK；美股: SPY / AAPL"

ANALYST_ORDER = [
    ("Market Analyst 市场技术分析师（K线/均线/技术指标）", AnalystType.MARKET),
    ("Social Media Analyst 社媒情绪分析师（社区/舆情情绪）", AnalystType.SOCIAL),
    ("News Analyst 新闻分析师（财经新闻/公告事件）", AnalystType.NEWS),
    ("Fundamentals Analyst 基本面分析师（财报/估值）", AnalystType.FUNDAMENTALS),
]


def print_step_header(n: int, total: int, title: str) -> None:
    """Print a formatted step header."""
    console.print(f"[bold cyan]─── Step {n}/{total}: {title} ───[/bold cyan]")


def create_question_box(title: str, prompt: str, default: str | None = None) -> Panel:
    """Create a styled question box panel matching commands/analyze/app.py style."""
    content = f"[bold]{title}[/bold]\n[dim]{prompt}[/dim]"
    if default:
        content += f"\n[dim]Default: {default}[/dim]"
    return Panel(content, border_style="blue", padding=(1, 2))


def ask_ticker(default: str = "600519") -> str:
    """Prompt the user to enter a ticker symbol."""
    ticker = Prompt.ask(
        f"[green]Enter the ticker symbol 输入股票代码 ({TICKER_INPUT_EXAMPLES}):[/green]",
        default=default,
    )

    if not ticker or not ticker.strip():
        console.print("[red]No ticker symbol provided. 未输入股票代码，退出。[/red]")
        exit(1)

    return ticker.strip().upper()


def ask_date(prompt: str, default: str) -> str:
    """Prompt the user to enter a date in YYYY-MM-DD format with validation."""
    while True:
        date_str = Prompt.ask(
            f"[green]{prompt}[/green]",
            default=default,
        )

        if not date_str or not date_str.strip():
            console.print("[red]No date provided. Exiting...[/red]")
            exit(1)

        date_str = date_str.strip()

        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
            if parsed_date > datetime.now():
                console.print("[red]Error: Analysis date cannot be in the future 分析日期不能是未来日期[/red]")
                continue
            console.print(f"[green]Date 分析日期: {date_str}[/green]")
            return date_str
        except ValueError:
            console.print("[red]Error: Invalid date format. Please use YYYY-MM-DD 日期格式错误，请用 YYYY-MM-DD[/red]")


def ask_analysts() -> List[AnalystType]:
    """Select analysts using an interactive checkbox-style selection."""
    selected = [True] * len(ANALYST_ORDER)

    console.print("\n[bold]Select Your [Analysts Team] 选择分析师团队:[/bold]")
    console.print("[dim]输入数字切换选中/取消，直接回车确认（至少保留 1 个分析师）[/dim]")
    console.print()

    while True:
        for i, (name, _) in enumerate(ANALYST_ORDER):
            checkbox = "[x]" if selected[i] else "[ ]"
            style = "green" if selected[i] else "dim"
            console.print(f"  [{i + 1}] [{style}]{checkbox}[/ {style}] {name}")

        console.print()
        choice = Prompt.ask(
            "[bold]Enter number to toggle (or press Enter to confirm) 输入数字切换，回车确认:[/bold]",
            default="",
        )

        if not choice:
            if not any(selected):
                console.print("[red]You must select at least one analyst. 至少选择 1 个分析师。[/red]")
                continue
            break

        try:
            idx = int(choice.strip()) - 1
            if 0 <= idx < len(selected):
                selected[idx] = not selected[idx]
        except ValueError:
            pass

        console.print()

    result = [ANALYST_ORDER[i][1] for i, is_sel in enumerate(selected) if is_sel]
    console.print(f"[green]Selected analysts 已选分析师: {', '.join(a.value for a in result)}[/green]")
    return result


def ask_research_depth() -> int:
    """Select research depth using an interactive numbered selection."""
    console.print("\n[bold]Select Your [Research Depth] 研究深度（影响多空辩论轮数与耗时）:[/bold]")
    console.print("  [1] [yellow]Shallow 浅度[/yellow] - Quick research, few debate rounds 快速研究，辩论轮数最少")
    console.print("  [2] [yellow]Medium 中度[/yellow]   - Moderate debate rounds (recommended 推荐，均衡速度与质量)")
    console.print("  [3] [yellow]Deep 深度[/yellow]     - Comprehensive research & debate 深入研究，辩论轮数最多")

    DEPTH_MAP = {"1": 1, "2": 3, "3": 5}

    choice = Prompt.ask(
        "\n[yellow]Choose depth 选择研究深度 (1/2/3)[/yellow]",
        choices=["1", "2", "3"],
        default="2",
    )

    return DEPTH_MAP[choice]


def ask_llm_provider() -> Tuple[str, str | None]:
    """Select the LLM provider and its API endpoint."""
    PROVIDERS = [
        "OpenAI",
        "Google",
        "Anthropic",
        "xAI",
        "DeepSeek",
        "Qwen",
        "GLM",
        "OpenRouter",
        "Azure OpenAI",
        "Ollama",
        "Agnes AI",
    ]

    PROVIDER_CONFIG = {
        "OpenAI": ("openai", "https://api.openai.com/v1"),
        "Google": ("google", None),
        "Anthropic": ("anthropic", "https://api.anthropic.com/"),
        "xAI": ("xai", "https://api.x.ai/v1"),
        "DeepSeek": ("deepseek", "https://api.deepseek.com"),
        "Qwen": ("qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "GLM": ("glm", "https://open.bigmodel.cn/api/paas/v4/"),
        "OpenRouter": ("openrouter", "https://openrouter.ai/api/v1"),
        "Azure OpenAI": ("azure", None),
        "Ollama": ("ollama", "http://localhost:11434/v1"),
        "Agnes AI": ("agnes", "https://apihub.agnes-ai.com/v1"),
    }

    console.print("\n[bold]Select your LLM Provider 选择LLM服务商:[/bold]")
    console.print(
        "[dim]提示: 国内推荐 DeepSeek / Qwen / GLM（价格低、直连可用）；"
        "OpenAI / Google / Anthropic 需海外网络；Ollama 为本地部署；Agnes AI 为聚合网关[/dim]"
    )
    choice = Prompt.ask(
        "[magenta]Choose a provider 选择服务商:[/magenta]",
        choices=PROVIDERS,
    )

    provider_key, url = PROVIDER_CONFIG[choice]
    return provider_key, url


def _fetch_openrouter_models() -> List[Tuple[str, str]]:
    """Fetch available models from the OpenRouter API."""
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        resp.raise_for_status()
        models = resp.json().get("data", [])
        return [(m.get("name") or m["id"], m["id"]) for m in models]
    except Exception as e:
        console.print(f"\n[yellow]Could not fetch OpenRouter models: {e}[/yellow]")
        return []


def ask_model(provider: str, mode: Literal["quick", "deep"]) -> str:
    """Select a model for the given provider and mode (quick/deep)."""
    if provider.lower() == "openrouter":
        models = _fetch_openrouter_models()

        choices = [name for name, _ in models[:5]]
        choices.append("Custom model ID")

        console.print(f"\n[bold]Select OpenRouter Model (latest available) 选择OpenRouter模型（实时拉取）:[/bold]")
        choice = Prompt.ask(
            "[magenta]Choose a model:[/magenta]",
            choices=choices,
        )

        if choice == "Custom model ID":
            custom_id = Prompt.ask(
                "[green]Enter OpenRouter model ID (e.g. google/gemma-4-26b-a4b-it):[/green]"
            )
            if not custom_id or not custom_id.strip():
                console.print("[red]No model ID provided. Exiting...[/red]")
                exit(1)
            return custom_id.strip()

        for name, mid in models[:5]:
            if name == choice:
                return mid
        return choice

    if provider.lower() == "azure":
        deployment = Prompt.ask(
            f"[green]Enter Azure deployment name 输入Azure部署名 ({mode}-thinking):[/green]"
        )
        if not deployment or not deployment.strip():
            console.print("[red]No deployment name provided. Exiting...[/red]")
            exit(1)
        return deployment.strip()

    options = get_model_options(provider, mode)
    choices = []
    seen_values = set()
    for display, value in options:
        if value in seen_values:
            continue
        seen_values.add(value)
        choices.append((display, value))

    mode_label = "Quick 快速模型（供分析师/交易员使用，速度优先）" if mode == "quick" else "Deep 深度模型（供研究经理/组合经理使用，质量优先）"
    console.print(f"\n[bold]Select Your [{mode.title()}-Thinking LLM Engine]:[/bold]")
    console.print(f"[dim]{mode_label}[/dim]")
    for index, (display, _) in enumerate(choices, 1):
        console.print(f"  [{index}] {display}")

    choice = Prompt.ask(
        "[magenta]Choose a model number 选择模型编号:[/magenta]",
        choices=[str(index) for index in range(1, len(choices) + 1)],
        default="1",
    )
    _, value = choices[int(choice) - 1]

    if value == "custom":
        custom_id = Prompt.ask("[green]Enter model ID 输入自定义模型ID:[/green]")
        if not custom_id or not custom_id.strip():
            console.print("[red]No model ID provided. Exiting...[/red]")
            exit(1)
        return custom_id.strip()

    return value


def ask_provider_thinking_config(provider: str) -> str | None:
    """Ask for provider-specific thinking configuration."""
    provider = provider.lower()

    if provider == "google":
        console.print("\n[bold]Select Thinking Mode 选择Gemini思考模式:[/bold]")
        choice = Prompt.ask(
            "[green]Choose thinking mode:[/green]",
            choices=[
                "Enable Thinking (recommended)",
                "Minimal/Disable Thinking",
            ],
        )
        if "Enable" in choice:
            return "high"
        return "minimal"

    if provider == "openai":
        console.print("\n[bold]Select Reasoning Effort 选择OpenAI推理强度:[/bold]")
        choice = Prompt.ask(
            "[cyan]Choose reasoning effort:[/cyan]",
            choices=[
                "Medium (Default)",
                "High (More thorough)",
                "Low (Faster)",
            ],
        )
        effort_map = {
            "Medium (Default)": "medium",
            "High (More thorough)": "high",
            "Low (Faster)": "low",
        }
        return effort_map.get(choice, "medium")

    if provider == "anthropic":
        console.print("\n[bold]Select Effort Level 选择Claude思考投入:[/bold]")
        choice = Prompt.ask(
            "[cyan]Choose effort level:[/cyan]",
            choices=[
                "High (recommended)",
                "Medium (balanced)",
                "Low (faster, cheaper)",
            ],
        )
        effort_map = {
            "High (recommended)": "high",
            "Medium (balanced)": "medium",
            "Low (faster, cheaper)": "low",
        }
        return effort_map.get(choice, "high")

    return None


def ask_output_language() -> str:
    """Ask for report output language using numbered selection."""
    LANGUAGES = [
        ("English", "English"),
        ("Chinese (中文)", "Chinese (中文)"),
        ("Japanese (日本語)", "Japanese (日本語)"),
        ("Korean (한국어)", "Korean (한국어)"),
        ("Hindi (हिन्दी)", "Hindi (हिन्दी)"),
        ("Spanish (Español)", "Spanish (Español)"),
        ("Portuguese (Português)", "Portuguese (Português)"),
        ("French (Français)", "French (Français)"),
        ("German (Deutsch)", "German (Deutsch)"),
        ("Arabic (العربية)", "Arabic (العربية)"),
        ("Russian (Русский)", "Russian (Русский)"),
        ("Custom language", "custom"),
    ]

    console.print("\n[bold]Select Output Language 选择输出语言:[/bold]")
    for i, (label, _) in enumerate(LANGUAGES, 1):
        console.print(f"  [{i}] {label}")

    choice = Prompt.ask(
        "\n[yellow]Choose language 选择语言编号 (1-12)[/yellow]",
        choices=[str(i) for i in range(1, len(LANGUAGES) + 1)],
        default="1",
    )

    idx = int(choice) - 1
    label, value = LANGUAGES[idx]

    if value == "custom":
        custom = Prompt.ask(
            "\n[green]Enter language name 输入语言名称:[/green]"
        )
        if not custom or not custom.strip():
            console.print("[red]No language name provided. 未输入语言名称，退出。[/red]")
            exit(1)
        return custom.strip()

    return value
