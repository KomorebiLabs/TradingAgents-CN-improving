"""TradingAgents Analyze UI adapter.

Since the application-layer extraction this module is presentation only:
it wires the ``AnalysisService`` event stream to the LiveDashboard and the
message/report buffer. All execution logic (graph, fallback, state sync,
result assembly) lives in ``tradingagents.application``; all chunk
interpretation lives in ``ChunkEventTranslator``. This file maps events to
widgets and never reads a raw graph state chunk.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cli.stats_handler import StatsCallbackHandler
from tradingagents.application import (
    AgentStatusChanged,
    AnalysisEvent,
    AnalysisRequest,
    AnalysisService,
    MessageEmitted,
    MetricsUpdated,
    ReportSectionUpdated,
    StageMarked,
    TimelineNoted,
    ToolCallObserved,
)
from tradingagents.application.events import ANALYST_AGENT_NAMES
from tradingagents.ui.live_dashboard import LiveDashboard
from tradingagents.ui.theme import TRADING_THEME

console = Console(theme=TRADING_THEME)


def _apply_event(event: AnalysisEvent, msg_buf, dashboard) -> None:
    """Map one execution event to message-buffer + dashboard updates."""
    if isinstance(event, MessageEmitted):
        msg_buf.add_message(event.mtype, event.content)
        dashboard.add_message(event.mtype, event.content)
    elif isinstance(event, ToolCallObserved):
        msg_buf.add_tool_call(event.name, event.args_repr)
        dashboard.add_tool_call(event.name, event.args_repr)
    elif isinstance(event, ReportSectionUpdated):
        msg_buf.update_report_section(event.section_key, event.content)
    elif isinstance(event, AgentStatusChanged):
        msg_buf.update_agent_status(event.agent, event.status)
        dashboard.update_agent_status(event.agent, event.status)
    elif isinstance(event, TimelineNoted):
        dashboard.add_event(event.text)
    elif isinstance(event, StageMarked):
        dashboard.update_metrics(current_stage=event.stage)
    elif isinstance(event, MetricsUpdated):
        dashboard.update_metrics(
            llm_calls=event.llm_calls,
            tool_calls=event.tool_calls,
            tokens_in=event.tokens_in,
            tokens_out=event.tokens_out,
        )
    # AnalysisStarted / AnalysisCompleted carry no widget mapping here.


def run_analysis(config: dict | AnalysisRequest) -> dict:
    """Run the full TradingAgents analysis pipeline (UI adapter).

    Args:
        config: questionnaire dict (cli/analyze/app.get_user_config) or an
            already-typed AnalysisRequest.

    Returns:
        dict with: ticker, decision, confidence, elapsed_time,
        llm_calls, tool_calls, tokens_in, tokens_out,
        report_path, final_state   (AnalysisResult.to_dict shape)
    """
    request = (
        config
        if isinstance(config, AnalysisRequest)
        else AnalysisRequest.from_questionnaire(config)
    )

    stats_handler = StatsCallbackHandler()
    service = AnalysisService()
    stream = service.stream_events(request, stats_handler=stats_handler)

    # Message buffer for dashboard + incremental report artifacts
    log_file = stream.results_dir / "message_tool.log"
    log_file.touch(exist_ok=True)

    class MessageBuffer:
        def __init__(self):
            self.messages: list = []
            self.tool_calls: list = []
            self.report_sections: dict = {}
            self.agent_status: dict = {}

        def add_message(self, mtype: str, content: str):
            ts = datetime.now().strftime("%H:%M:%S")
            self.messages.append((ts, mtype, content))
            clean = content.replace("\n", " ")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{ts} [{mtype}] {clean}\n")

        def add_tool_call(self, name: str, args: str):
            ts = datetime.now().strftime("%H:%M:%S")
            self.tool_calls.append((ts, name, args))
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{ts} [Tool Call] {name}({args})\n")

        def update_agent_status(self, agent: str, status: str):
            self.agent_status[agent] = status

        def update_report_section(self, section: str, content: str):
            existing = self.report_sections.get(section, "")
            if content not in existing:
                self.report_sections[section] = existing + "\n" + content
                filepath = stream.report_dir / f"{section}.md"
                filepath.write_text(self.report_sections[section], encoding="utf-8")

    msg_buf = MessageBuffer()
    msg_buf.update_agent_status("Market Analyst", "in_progress")

    dashboard = LiveDashboard(
        ticker=request.ticker,
        selected_analysts=[ANALYST_AGENT_NAMES[k] for k in request.analyst_keys()],
        refresh_interval=3.0,
    )

    # Initial dashboard messages
    dashboard.add_message("System", f"Selected ticker: {request.ticker}")
    dashboard.add_message("System", f"Analysis date: {request.trade_date}")
    dashboard.add_message(
        "System", f"Selected analysts: {', '.join(request.selected_analysts)}"
    )

    for name in [ANALYST_AGENT_NAMES[k] for k in request.analyst_keys()]:
        dashboard.update_agent_status(name, "pending")

    def events_with_dashboard():
        for event in stream:
            _apply_event(event, msg_buf, dashboard)
            yield event

    dashboard.run(events_with_dashboard(), stats_callback=stats_handler)

    assert stream.result is not None, "event stream exhausted without a result"
    result = stream.result.to_dict()

    print_reports_saved(stream.report_dir, request.ticker, request.trade_date)
    return result


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
