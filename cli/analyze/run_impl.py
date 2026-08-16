"""TradingAgents Analyze execution engine.

Replaces the run_analysis() function from tradingagents/commands/analyze/app.py.
Handles:
1. TradingAgentsGraph initialization
2. LiveDashboard management (chunk-triggered + 3s timer)
3. graph.stream() processing with agent status tracking
4. Report saving and display
5. Returns result dict for summary.py
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cli.stats_handler import StatsCallbackHandler
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.ui.live_dashboard import LiveDashboard
from tradingagents.ui.theme import TRADING_THEME

console = Console(theme=TRADING_THEME)

# Constants from commands/analyze/app.py
ANALYST_ORDER = ["market", "social", "news", "fundamentals"]
ANALYST_AGENT_NAMES = {
    "market": "Market Analyst",
    "social": "Social Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}
ANALYST_REPORT_MAP = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}


def _classify_message(message) -> tuple[str, str | None]:
    """Classify a LangChain message into display type and extract content."""
    content = getattr(message, "content", None)
    if content is None:
        return "System", None

    text = ""
    if isinstance(content, str):
        text = content.strip()
    elif isinstance(content, dict):
        text = content.get("text", "")
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        text = " ".join(p.strip() for p in parts if p.strip())
    else:
        text = str(content)

    if isinstance(message, HumanMessage):
        return "User", text[:100] if text else None
    if isinstance(message, ToolMessage):
        return "Data", text[:80] if text else None
    if isinstance(message, AIMessage):
        return "Agent", text[:100] if text else None
    return "System", text[:100] if text else None


def run_analysis(config: dict) -> dict:
    """Run the full TradingAgents analysis pipeline.

    Args:
        config: Dictionary from cli/analyze/app.py.get_user_config():
            - ticker: str
            - date: str (YYYY-MM-DD)
            - output_language: str
            - analysts: List[AnalystType]
            - research_depth: int (1/3/5)
            - llm_provider: str
            - backend_url: str | None
            - shallow_thinking_model: str
            - deep_thinking_model: str
            - thinking_level: str | None (Google)
            - reasoning_effort: str | None (OpenAI)
            - anthropic_effort: str | None (Anthropic)

    Returns:
        dict with: ticker, decision, confidence, elapsed_time,
        llm_calls, tool_calls, tokens_in, tokens_out,
        report_path, final_state
    """
    ticker = config["ticker"]
    date = config["date"]

    # Build TradingAgentsGraph config
    graph_config = DEFAULT_CONFIG.copy()
    graph_config["max_debate_rounds"] = config["research_depth"]
    graph_config["max_risk_discuss_rounds"] = config["research_depth"]
    graph_config["quick_think_llm"] = config["shallow_thinking_model"]
    graph_config["deep_think_llm"] = config["deep_thinking_model"]
    graph_config["backend_url"] = config["backend_url"]
    graph_config["llm_provider"] = config["llm_provider"].lower()
    graph_config["google_thinking_level"] = config.get("thinking_level")
    graph_config["openai_reasoning_effort"] = config.get("reasoning_effort")
    graph_config["anthropic_effort"] = config.get("anthropic_effort")
    graph_config["output_language"] = config.get("output_language", "English")

    # Stats handler
    stats_handler = StatsCallbackHandler()

    # Normalize analyst selection
    selected_set = {a.value for a in config["analysts"]}
    selected_analyst_keys = [a for a in ANALYST_ORDER if a in selected_set]

    # Initialize graph
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    graph = TradingAgentsGraph(
        selected_analyst_keys,
        config=graph_config,
        debug=True,
        callbacks=[stats_handler],
    )

    # Create results directory — save to project reports/ folder
    project_root = Path(__file__).resolve().parents[2]
    results_dir = project_root / "reports" / ticker / date
    results_dir.mkdir(parents=True, exist_ok=True)
    report_dir = results_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    log_file = results_dir / "message_tool.log"
    log_file.touch(exist_ok=True)

    # Start time
    start_time = time.time()

    # Message buffer for dashboard
    class MessageBuffer:
        def __init__(self):
            self.messages: list = []
            self.tool_calls: list = []
            self.report_sections: dict = {}
            self.agent_status: dict = {}
            self._processed_ids: set = set()

        def add_message(self, mtype: str, content: str):
            ts = datetime.now().strftime("%H:%M:%S")
            self.messages.append((ts, mtype, content))
            # Log to file
            clean = content.replace("\n", " ")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{ts} [{mtype}] {clean}\n")

        def add_tool_call(self, name: str, args: dict):
            ts = datetime.now().strftime("%H:%M:%S")
            self.tool_calls.append((ts, name, args))
            args_str = ", ".join(f"{k}={v}" for k, v in args.items()) if isinstance(args, dict) else str(args)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{ts} [Tool Call] {name}({args_str})\n")

        def update_agent_status(self, agent: str, status: str):
            self.agent_status[agent] = status

        def update_report_section(self, section: str, content: str):
            existing = self.report_sections.get(section, "")
            if content not in existing:
                self.report_sections[section] = existing + "\n" + content
                # Save incrementally
                filepath = report_dir / f"{section}.md"
                text = self.report_sections[section]
                filepath.write_text(text, encoding="utf-8")

    msg_buf = MessageBuffer()
    msg_buf.update_agent_status("Market Analyst", "in_progress")

    # Dashboard
    dashboard = LiveDashboard(
        ticker=ticker,
        selected_analysts=[ANALYST_AGENT_NAMES[k] for k in selected_analyst_keys],
        refresh_interval=3.0,
    )

    # Initial dashboard messages
    dashboard.add_message("System", f"Selected ticker: {ticker}")
    dashboard.add_message("System", f"Analysis date: {date}")
    dashboard.add_message("System", f"Selected analysts: {', '.join(a.value for a in config['analysts'])}")

    for name in [ANALYST_AGENT_NAMES[k] for k in selected_analyst_keys]:
        dashboard.update_agent_status(name, "pending")

    # Run the graph through its public streaming API.
    # The stream finalizes final_state/decision after exhaustion.
    run = graph.stream_analysis(ticker, date, callbacks=[stats_handler])

    def stream_with_dashboard():
        for chunk in run:
            # Process messages
            for message in chunk.get("messages", []):
                msg_id = getattr(message, "id", None)
                if msg_id is not None:
                    if msg_id in msg_buf._processed_ids:
                        continue
                    msg_buf._processed_ids.add(msg_id)

                mtype, content = _classify_message(message)
                if content:
                    msg_buf.add_message(mtype, content)
                    dashboard.add_message(mtype, content)

                if hasattr(message, "tool_calls") and message.tool_calls:
                    for tc in message.tool_calls:
                        if isinstance(tc, dict):
                            name, args = tc.get("name", "?"), tc.get("args", {})
                        else:
                            name, args = tc.name, tc.args
                        msg_buf.add_tool_call(name, args)
                        dashboard.add_tool_call(name, ", ".join(f"{k}={v}" for k, v in args.items()) if isinstance(args, dict) else str(args))

            # Update analyst statuses
            _update_analyst_statuses(msg_buf, dashboard, chunk, selected_analyst_keys, selected_set)

            # Update metrics
            stats = stats_handler.get_stats()
            dashboard.update_metrics(
                llm_calls=stats.get("llm_calls", 0),
                tool_calls=stats.get("tool_calls", 0),
                tokens_in=stats.get("tokens_in", 0),
                tokens_out=stats.get("tokens_out", 0),
            )

            # Handle debate states
            _handle_debate_states(msg_buf, dashboard, chunk)

            yield chunk

    # Run dashboard with stream
    dashboard.run(stream_with_dashboard(), stats_callback=stats_handler)

    # Final processing (outside Live context)
    elapsed = time.time() - start_time
    final_state = run.final_state if run.final_state is not None else {}
    decision = run.decision if run.final_state is not None else "N/A"

    # Build result dict
    stats = stats_handler.get_stats()
    result = {
        "ticker": ticker,
        "decision": decision,
        "confidence": None,  # TODO: extract from final_state if available
        "elapsed_time": elapsed,
        "llm_calls": stats.get("llm_calls", 0),
        "tool_calls": stats.get("tool_calls", 0),
        "tokens_in": stats.get("tokens_in", 0),
        "tokens_out": stats.get("tokens_out", 0),
        "report_path": report_dir,
        "final_state": final_state,
    }

    # Notify user where report files were saved
    print_reports_saved(report_dir, ticker, date)

    return result


def _update_analyst_statuses(
    msg_buf, dashboard, chunk, selected_keys, selected_set
) -> None:
    """Update analyst statuses based on accumulated report state."""
    found_active = False
    for key in ANALYST_ORDER:
        if key not in selected_set:
            continue
        agent = ANALYST_AGENT_NAMES[key]
        report_key = ANALYST_REPORT_MAP[key]

        # Capture new report
        if report_key in chunk and chunk[report_key]:
            msg_buf.update_report_section(report_key, chunk[report_key])

        has_report = bool(msg_buf.report_sections.get(report_key))
        if has_report:
            msg_buf.update_agent_status(agent, "completed")
            dashboard.update_agent_status(agent, "completed")
        elif not found_active:
            msg_buf.update_agent_status(agent, "in_progress")
            dashboard.update_agent_status(agent, "in_progress")
            found_active = True
        else:
            msg_buf.update_agent_status(agent, "pending")
            dashboard.update_agent_status(agent, "pending")

    # Transition to research team when all analysts done
    if not found_active and selected_keys:
        bull = "Bull Researcher"
        if msg_buf.agent_status.get(bull, "pending") == "pending":
            msg_buf.update_agent_status(bull, "in_progress")
            dashboard.update_agent_status(bull, "in_progress")
            dashboard.add_event(f"Stage 1 complete, {bull} started")


def _handle_debate_states(msg_buf, dashboard, chunk) -> None:
    """Handle investment_debate_state, trader_investment_plan, and risk_debate_state."""
    # Investment debate
    if "investment_debate_state" in chunk:
        debate = chunk["investment_debate_state"]
        bull = debate.get("bull_history", "").strip()
        bear = debate.get("bear_history", "").strip()
        judge = debate.get("judge_decision", "").strip()

        if bull or bear:
            dashboard.add_event("Research: debate in progress")
        if bull:
            msg_buf.update_report_section("investment_plan", f"### Bull Researcher\n{bull}")
        if bear:
            msg_buf.update_report_section("investment_plan", f"### Bear Researcher\n{bear}")
        if judge:
            msg_buf.update_report_section("investment_plan", f"### Research Manager\n{judge}")
            msg_buf.update_agent_status("Research Manager", "completed")
            dashboard.update_agent_status("Research Manager", "completed")
            msg_buf.update_agent_status("Bull Researcher", "completed")
            dashboard.update_agent_status("Bull Researcher", "completed")
            msg_buf.update_agent_status("Trader", "in_progress")
            dashboard.update_agent_status("Trader", "in_progress")
            dashboard.add_event("Research complete, Trader started")
            dashboard.update_metrics(current_stage="Stage C")

    # Trader
    if "trader_investment_plan" in chunk and chunk["trader_investment_plan"]:
        msg_buf.update_report_section("trader_investment_plan", chunk["trader_investment_plan"])
        if msg_buf.agent_status.get("Trader") != "completed":
            msg_buf.update_agent_status("Trader", "completed")
            dashboard.update_agent_status("Trader", "completed")
            msg_buf.update_agent_status("Aggressive Analyst", "in_progress")
            dashboard.update_agent_status("Aggressive Analyst", "in_progress")
            dashboard.add_event("Trader: plan complete, Risk team started")

    # Risk debate
    if "risk_debate_state" in chunk:
        risk = chunk["risk_debate_state"]
        for field, agent in [
            ("aggressive_history", "Aggressive Analyst"),
            ("conservative_history", "Conservative Analyst"),
            ("neutral_history", "Neutral Analyst"),
        ]:
            content = risk.get(field, "").strip()
            if content:
                if msg_buf.agent_status.get(agent) != "completed":
                    msg_buf.update_agent_status(agent, "in_progress")
                    dashboard.update_agent_status(agent, "in_progress")
                msg_buf.update_report_section("final_trade_decision", f"### {agent}\n{content}")

        judge = risk.get("judge_decision", "").strip()
        if judge:
            msg_buf.update_report_section("final_trade_decision", f"### Portfolio Manager\n{judge}")
            for agent in ["Aggressive Analyst", "Conservative Analyst", "Neutral Analyst", "Portfolio Manager"]:
                msg_buf.update_agent_status(agent, "completed")
                dashboard.update_agent_status(agent, "completed")
            dashboard.add_event("Portfolio: final decision complete")


def print_reports_saved(report_dir: Path, ticker: str, date: str) -> None:
    """Print a Rich-formatted notification showing where report files were saved.

    Args:
        report_dir: Path to the reports directory (e.g. ~/.tradingagents/logs/<TICKER>/<DATE>/reports/)
        ticker: Stock ticker symbol
        date: Analysis date string (YYYY-MM-DD)
    """
    # Expand ~ to actual home directory path for display
    expanded_path = Path(os.path.expanduser(str(report_dir)))

    # Collect files that were actually saved
    report_files = [
        ("market_report.md", "Market Analysis"),
        ("sentiment_report.md", "Social Sentiment"),
        ("news_report.md", "News Analysis"),
        ("fundamentals_report.md", "Fundamentals Analysis"),
        ("investment_plan.md", "Research Team Decision"),
        ("trader_investment_plan.md", "Trading Team Plan"),
        ("final_trade_decision.md", "Portfolio Management Decision"),
    ]

    # Build file list table
    file_table = Table(box=None, show_header=True, padding=(0, 2))
    file_table.add_column("File", style="cyan", width=30)
    file_table.add_column("Description", style="white")

    saved_count = 0
    for filename, description in report_files:
        filepath = report_dir / filename
        if filepath.exists() and filepath.stat().st_size > 0:
            file_table.add_row(f"[green]{filename}[/green]", description)
            saved_count += 1

    if saved_count == 0:
        console.print(Panel(
            "[yellow]No report files were saved.[/yellow]",
            title="[bold]Reports Saved[/bold]",
            border_style="yellow",
            padding=(1, 2),
        ))
        return

    # Path line
    path_text = Text(f"  {expanded_path}", style="dim")

    # Build content
    grouped_content = Group(
        path_text,
        Text(""),
        file_table,
        Text(""),
        Text(f"  {saved_count} report file(s) saved", style="dim"),
    )

    console.print(Panel(
        grouped_content,
        title="[bold green]Reports Saved[/bold green]",
        border_style="green",
        padding=(1, 2),
    ))
