"""TradingAgents Analyze CLI — Stage 2: Multi-Agent Deep Analysis.

Entry point: python -m cli.analyze
Called by: cli.main_menu._run_analyzer()
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from rich.align import Align
from rich.console import Console
from rich.panel import Panel

from tradingagents.ui.theme import TRADING_THEME

# Import prompts from the unified prompt layer
from cli.prompts import (
    ask_ticker,
    ask_date,
    ask_output_language,
    ask_analysts,
    ask_research_depth,
    ask_llm_provider,
    ask_model,
    ask_provider_thinking_config,
    create_question_box,
)

console = Console(theme=TRADING_THEME)


def _print_welcome() -> None:
    """Print ASCII logo + welcome Panel + announcements.
    
    Replicates tradingagents/commands/analyze/app.py lines 469-498.
    """
    # Read and print ASCII logo from cli/static/welcome.txt
    welcome_path = Path(__file__).parent.parent / "static" / "welcome.txt"
    if welcome_path.exists():
        console.print(welcome_path.read_text(encoding="utf-8"))

    # Welcome box content
    welcome_content = (
        "[bold green]TradingAgents: Multi-Agents LLM Financial Trading Framework - CLI[/bold green]\n\n"
        "[bold cyan]面向中国A股的多智能体LLM金融交易决策框架（Stage 2 深度分析）[/bold cyan]\n\n"
        "[bold]Workflow Steps 工作流程:[/bold]\n"
        "I. Analyst Team 分析师团队 → II. Research Team 多空研究辩论 → III. Trader 交易员 "
        "→ IV. Risk Management 风险辩论 → V. Portfolio Manager 组合经理决策\n\n"
        "[dim]Built by [Tauric Research](https://github.com/TauricResearch)[/dim]"
    )
    console.print(Align.center(Panel(
        welcome_content,
        border_style="green",
        padding=(1, 2),
        title="Welcome to TradingAgents",
        subtitle="Multi-Agents LLM Financial Trading Framework",
    )))
    console.print()

    # Fetch and display announcements (silent on failure)
    try:
        from cli.announcements import fetch_announcements, display_announcements
        announcements = fetch_announcements()
        if announcements:
            display_announcements(console, announcements)
    except Exception:
        pass  # Announcements are best-effort only


def get_user_config() -> dict:
    """Execute the 8-step questionnaire and return a config dictionary.
    
    Replicates tradingagents/commands/analyze/app.py lines 500-618.
    Each step uses create_question_box() followed by a prompt from cli/prompts.py.
    """
    _print_welcome()

    # Step 1: Ticker
    console.print(create_question_box(
        "Step 1: Ticker Symbol 股票代码",
        "A股股票直接输入6位数字代码（如 600519 贵州茅台、000001 平安银行、300750 宁德时代）；"
        "港股/美股需带交易所后缀 (e.g. 0700.HK, SPY, AAPL)",
        "600519"
    ))
    ticker = ask_ticker()

    # Step 2: Date
    default_date = datetime.now().strftime("%Y-%m-%d")
    console.print(create_question_box(
        "Step 2: Analysis Date 分析日期",
        "Enter the analysis date (YYYY-MM-DD) 输入分析日期，建议选择最近一个交易日"
        "（周末/节假日无行情数据）",
        default_date
    ))
    date = ask_date("Enter the analysis date 输入分析日期 (YYYY-MM-DD):", default_date)

    # Step 3: Output Language
    console.print(create_question_box(
        "Step 3: Output Language 输出语言",
        "Select the language for analyst reports and final decision "
        "选择分析师报告与最终决策的输出语言（推荐中文）"
    ))
    language = ask_output_language()

    # Step 4: Analysts Team
    console.print(create_question_box(
        "Step 4: Analysts Team 分析师团队",
        "Select your LLM analyst agents for the analysis "
        "选择参与分析的分析师Agent（市场/社媒/新闻/基本面，至少选1个）"
    ))
    selected_analysts = ask_analysts()

    # Step 5: Research Depth
    console.print(create_question_box(
        "Step 5: Research Depth 研究深度",
        "Select your research depth level 选择研究深度（影响多空辩论轮数与耗时）"
    ))
    depth = ask_research_depth()

    # Step 6: LLM Provider
    console.print(create_question_box(
        "Step 6: LLM Provider 大模型服务商",
        "Select your LLM provider 选择LLM服务商（国内推荐 DeepSeek / Qwen / GLM）"
    ))
    provider, backend_url = ask_llm_provider()

    # Step 7: Thinking Agents
    console.print(create_question_box(
        "Step 7: Thinking Agents 思考模型",
        "Select your thinking agents for analysis 选择快慢思考模型"
        "（Quick 供分析师/交易员使用，Deep 供研究经理/组合经理使用）"
    ))
    shallow_model = ask_model(provider, "quick")
    deep_model = ask_model(provider, "deep")

    # Step 8: Provider-specific thinking configuration
    thinking_level = None
    reasoning_effort = None
    anthropic_effort = None

    p = provider.lower()
    if p == "google":
        console.print(create_question_box(
            "Step 8: Thinking Mode 思考模式",
            "Configure Gemini thinking mode 配置 Gemini 思考模式"
        ))
        thinking_level = ask_provider_thinking_config(provider)
    elif p == "openai":
        console.print(create_question_box(
            "Step 8: Reasoning Effort 推理强度",
            "Configure OpenAI reasoning effort level 配置 OpenAI 推理强度（影响深度与耗时）"
        ))
        reasoning_effort = ask_provider_thinking_config(provider)
    elif p == "anthropic":
        console.print(create_question_box(
            "Step 8: Effort Level 思考投入",
            "Configure Anthropic effort level 配置 Claude 思考投入等级"
        ))
        anthropic_effort = ask_provider_thinking_config(provider)
    # Other providers: Step 8 skipped 其他服务商跳过此步

    # Assemble and return config
    return {
        "ticker": ticker,
        "date": date,
        "output_language": language,
        "analysts": selected_analysts,
        "research_depth": depth,
        "llm_provider": provider,
        "backend_url": backend_url,
        "shallow_thinking_model": shallow_model,
        "deep_thinking_model": deep_model,
        "thinking_level": thinking_level,
        "reasoning_effort": reasoning_effort,
        "anthropic_effort": anthropic_effort,
    }


def run(hitl: bool = False) -> None:
    """Main entry point for the Analyze CLI.

    1. Run 8-step questionnaire
    2. Execute analysis via run_impl
    3. Show summary
    4. Return to caller (caller handles "返回主菜单？" prompt)
    """
    import sys
    config = get_user_config()

    # Import and run the execution engine
    from cli.analyze.run_impl import run_analysis
    result = run_analysis(config, hitl=hitl)

    # Show summary
    from tradingagents.ui.summary import print_summary
    print_summary(result, module_type="analyzer")
