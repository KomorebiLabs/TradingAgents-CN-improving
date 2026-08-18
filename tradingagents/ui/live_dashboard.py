"""Bloomberg-style live dashboard for TradingAgents Analyze CLI.

Refresh strategy: immediate refresh on new data + 3-second timer fallback.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from tradingagents.ui.theme import TRADING_THEME


_STAGE_ORDER = ["Stage 1", "Stage A", "Stage B", "Stage C"]


def _stage_index(name: str) -> int:
    try:
        return _STAGE_ORDER.index(name)
    except ValueError:
        return -1


class LiveDashboard:
    """Bloomberg-style live dashboard for TradingAgents.
    
    Tracks agent status, event trail, and metrics during graph execution.
    Refresh strategy: chunk-triggered immediate refresh + 3-second timer fallback.
    """

    def __init__(
        self,
        ticker: str,
        selected_analysts: List[str],
        refresh_interval: float = 3.0,
    ):
        self.console = Console(theme=TRADING_THEME)
        self.ticker = ticker
        self.selected_analysts = selected_analysts

        # Agent state: name -> pending | in_progress | completed | error
        self.agent_status: Dict[str, str] = {}
        self.report_sections: Dict[str, str] = {}
        self.messages: List[tuple[str, str, str]] = []  # (ts, type, content)
        self.tool_calls: List[tuple[str, str, str]] = []  # (ts, tool, args_str)
        self.event_trail: List[str] = []

        # Stage
        self.current_stage = "Stage 1"
        self._completed_stages: set = set()

        # Metrics
        self.start_time = time.time()
        self.llm_calls = 0
        self.tool_call_count = 0
        self.tokens_in = 0
        self.tokens_out = 0

        # Refresh
        self.refresh_interval = refresh_interval
        self._dirty = threading.Event()
        self._dirty.set()
        self._lock = threading.RLock()

    # ── Public API (called from run_impl) ──────────────────────────────

    def update_agent_status(self, agent_name: str, status: str) -> None:
        with self._lock:
            self.agent_status[agent_name] = status
            self._dirty.set()

    def add_message(self, msg_type: str, content: str) -> None:
        with self._lock:
            ts = datetime.now().strftime("%H:%M:%S")
            self.messages.append((ts, msg_type, content[:120]))
            if len(self.messages) > 30:
                self.messages = self.messages[-30:]
            self._dirty.set()

    def add_tool_call(self, tool_name: str, args_str: str) -> None:
        with self._lock:
            ts = datetime.now().strftime("%H:%M:%S")
            self.tool_calls.append((ts, tool_name, args_str[:80]))
            if len(self.tool_calls) > 30:
                self.tool_calls = self.tool_calls[-30:]
            self._dirty.set()

    def add_event(self, event: str) -> None:
        with self._lock:
            ts = datetime.now().strftime("%H:%M:%S")
            self.event_trail.append(f"[{ts}] {event}")
            if len(self.event_trail) > 50:
                self.event_trail = self.event_trail[-50:]
            self._dirty.set()

    def update_metrics(
        self,
        llm_calls: int | None = None,
        tool_calls: int | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        current_stage: str | None = None,
    ) -> None:
        with self._lock:
            if llm_calls is not None:
                self.llm_calls = llm_calls
            if tool_calls is not None:
                self.tool_call_count = tool_calls
            if tokens_in is not None:
                self.tokens_in = tokens_in
            if tokens_out is not None:
                self.tokens_out = tokens_out
            if current_stage is not None:
                if self.current_stage != current_stage:
                    if _stage_index(current_stage) > _stage_index(self.current_stage):
                        self._completed_stages.add(self.current_stage)
                    self.current_stage = current_stage
            self._dirty.set()

    # ── Layout building ────────────────────────────────────────────────

    def _build_layout(self) -> Layout:
        layout = Layout(name="root")
        layout.split(
            Layout(name="top", ratio=1),
            Layout(name="bottom", ratio=1),
        )
        layout["top"].split(
            Layout(name="progress", ratio=1),
            Layout(name="agents", ratio=1),
        )
        layout["bottom"].split(
            Layout(name="events", ratio=3),
            Layout(name="metrics", ratio=1),
        )
        with self._lock:
            layout["progress"].update(self._build_progress_panel())
            layout["agents"].update(self._build_agent_panel())
            layout["events"].update(self._build_event_panel())
            layout["metrics"].update(self._build_metrics_panel())
        return layout

    def _build_progress_panel(self) -> Panel:
        table = Table(box=None, show_header=False, pad_edge=True)
        table.add_column("Stage", style="cyan", width=22)
        table.add_column("Status", width=16)

        for stage in _STAGE_ORDER:
            idx = _stage_index(stage)
            current_idx = _stage_index(self.current_stage)

            if stage == self.current_stage:
                bar = "[cyan]●○○○[/cyan]"
                status = "[cyan]● RUNNING[/cyan]"
            elif idx < current_idx or stage in self._completed_stages:
                bar = "[green]■■■■[/green]"
                status = "[green]✓ DONE[/green]"
            else:
                bar = "[yellow]○○○○[/yellow]"
                status = "[yellow]○ WAIT[/yellow]"

            table.add_row(stage, f"{status} {bar}")

        return Panel(
            table,
            title="[bold]PROGRESS[/bold]",
            border_style="cyan",
            padding=(1, 1),
        )

    def _build_agent_panel(self) -> Panel:
        table = Table(box=None, show_header=False, pad_edge=True)
        table.add_column("Agent", style="white", width=22)
        table.add_column("Status", width=10)

        for agent, status in self.agent_status.items():
            icon = {
                "completed": "[green]✓[/green]",
                "in_progress": "[cyan]●[/cyan]",
                "error": "[red]✗[/red]",
            }.get(status, "[yellow]○[/yellow]")
            table.add_row(agent, icon)

        return Panel(
            table,
            title="[bold]AGENT STATUS[/bold]",
            border_style="green",
            padding=(1, 1),
        )

    def _build_event_panel(self) -> Panel:
        with self._lock:
            lines = self.event_trail[-10:]
        if not lines:
            content = "[dim]Waiting for events...[/dim]"
        else:
            content = "\n".join(lines)
        return Panel(
            content,
            title="[bold]EVENT TRAIL[/bold]",
            border_style="magenta",
            padding=(1, 1),
        )

    def _build_metrics_panel(self) -> Panel:
        elapsed = int(time.time() - self.start_time)
        mins, secs = divmod(elapsed, 60)

        def fmt(n: int) -> str:
            if n >= 1_000_000:
                return f"{n / 1_000_000:.1f}M"
            if n >= 1000:
                return f"{n // 1000}K"
            return str(n)

        metrics = (
            f"[cyan]LLM:[/cyan] {self.llm_calls}  "
            f"[cyan]Tools:[/cyan] {self.tool_call_count}  "
            f"[cyan]↑[/cyan]{fmt(self.tokens_in)}  "
            f"[cyan]↓[/cyan]{fmt(self.tokens_out)}  "
            f"[cyan]⏱[/cyan] {mins:02d}:{secs:02d}"
        )
        return Panel(
            metrics,
            title="[bold]METRICS[/bold]",
            border_style="yellow",
            padding=(1, 1),
        )

    # ── Main run method ────────────────────────────────────────────────

    def run(self, chunk_iterator, stats_callback=None):
        """Run live dashboard with a chunk iterator.

        Args:
            chunk_iterator: An iterable of graph chunks (e.g. graph.stream())
            stats_callback: A StatsCallbackHandler instance to poll metrics
        """
        layout = self._build_layout()
        last_poll = time.time()

        _live_obj = Live(
            layout,
            refresh_per_second=4,
            transient=False,
            console=self.console,
        )
        with _live_obj as live:
            # Force an immediate render of the initial layout before waiting for the first chunk.
            # Using update() instead of refresh() because refresh() is best-effort and may not
            # render on all terminal types (especially Windows/PowerShell).
            live.update(layout, refresh=True)

            for chunk in chunk_iterator:
                self._process_chunk(chunk)

                # Poll stats
                if stats_callback:
                    now = time.time()
                    if now - last_poll > 0.5:
                        stats = stats_callback.get_stats()
                        self.update_metrics(
                            llm_calls=stats.get("llm_calls", 0),
                            tool_calls=stats.get("tool_calls", 0),
                            tokens_in=stats.get("tokens_in", 0),
                            tokens_out=stats.get("tokens_out", 0),
                        )
                        last_poll = now

                # Immediate refresh
                try:
                    live.update(self._build_layout())
                except Exception:
                    pass

            # Final refresh
            try:
                live.update(self._build_layout())
            except Exception:
                pass

    # ── Chunk processing ───────────────────────────────────────────────

    def _process_chunk(self, chunk: Dict[str, Any]) -> None:
        """Process a single graph chunk and update dashboard state."""
        # Messages
        for message in chunk.get("messages", []):
            content = getattr(message, "content", None) or ""
            text = str(content)

            if isinstance(message, HumanMessage):
                self.add_message("User", text[:100])
            elif isinstance(message, AIMessage):
                self.add_message("Agent", text[:100])
            elif isinstance(message, ToolMessage):
                tool_name = getattr(message, "name", "tool")
                self.add_message("Data", f"{tool_name}: {text[:60]}")

            # Tool calls
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    if isinstance(tc, dict):
                        name = tc.get("name", "?")
                        args = tc.get("args", {})
                    else:
                        name = tc.name
                        args = tc.args
                    args_str = ", ".join(f"{k}={v}" for k, v in args.items()) if isinstance(args, dict) else str(args)
                    self.add_tool_call(name, args_str)

        # Stage transitions based on report sections
        report_map = {
            "market_report": "Market Analyst",
            "sentiment_report": "Social Analyst",
            "news_report": "News Analyst",
            "fundamentals_report": "Fundamentals Analyst",
        }
        for key, agent in report_map.items():
            if key in chunk and chunk[key]:
                self.update_agent_status(agent, "completed")
                if agent == self.selected_analysts[-1] if self.selected_analysts else False:
                    pass  # handled by update_analyst_statuses

        # Investment debate state → research team
        if "investment_debate_state" in chunk:
            debate = chunk["investment_debate_state"]
            if debate.get("bull_history"):
                self.update_agent_status("Bull Researcher", "in_progress")
                self.add_event("Research: Bull analysis in progress")
            if debate.get("judge_decision"):
                self.update_agent_status("Bull Researcher", "completed")
                self.update_agent_status("Research Manager", "completed")
                self.update_agent_status("Trader", "in_progress")
                self.current_stage = "Stage C"
                self.add_event("Research: decision complete, Trader started")

        # Trader plan
        if "trader_investment_plan" in chunk and chunk["trader_investment_plan"]:
            self.update_agent_status("Trader", "completed")
            self.add_event("Trader: plan ready")

        # Risk debate state
        if "risk_debate_state" in chunk:
            risk = chunk["risk_debate_state"]
            latest_speaker = risk.get("latest_speaker", "")

            # Mark agents as completed when they finish speaking
            if latest_speaker == "Aggressive" and risk.get("aggressive_history"):
                # Conservative or Neutral will speak next, so Aggressive is done
                self.update_agent_status("Aggressive Analyst", "completed")
            if latest_speaker == "Conservative" and risk.get("conservative_history"):
                # Neutral will speak next, so Conservative is done
                self.update_agent_status("Conservative Analyst", "completed")
            if latest_speaker == "Neutral" and risk.get("neutral_history"):
                # Round complete, Neutral is done
                self.update_agent_status("Neutral Analyst", "completed")

            if any(risk.get(k) for k in ["aggressive_history", "conservative_history", "neutral_history"]):
                self.update_agent_status("Aggressive Analyst", "in_progress")
                self.add_event("Risk: analysis in progress")
            if risk.get("judge_decision"):
                self.update_agent_status("Portfolio Manager", "completed")
                self.add_event("Portfolio: final decision made")
