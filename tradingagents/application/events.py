"""Stable execution events + the state-chunk translator.

The UI (dashboard, logs, future Web API) consumes ONLY these events; the
translator is the single place allowed to understand LangGraph chunk
internals. Event semantics are frozen by tests — renaming fields is a
breaking change for every consumer.

The translator is a faithful port of the per-chunk logic that used to live in
``cli/analyze/run_impl.py`` (message classification/dedup, analyst status
derivation, debate/trader/risk cascade), so dashboard behavior is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

# ---------------------------------------------------------------------------
# Event protocol
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AnalysisEvent:
    """Base class for all analysis execution events."""


@dataclass(frozen=True)
class AnalysisStarted(AnalysisEvent):
    ticker: str
    trade_date: str
    selected_analysts: tuple
    run_id: str = ""  # unique per run; also the checkpoint thread_id (E1/E7)


@dataclass(frozen=True)
class AnalysisCompleted(AnalysisEvent):
    final_state: Dict[str, Any]
    decision: str


@dataclass(frozen=True)
class MessageEmitted(AnalysisEvent):
    """A new chat message (deduplicated by message id)."""

    mtype: str          # "Agent" | "User" | "Data" | "System"
    content: str


@dataclass(frozen=True)
class ToolCallObserved(AnalysisEvent):
    name: str
    args_repr: str


@dataclass(frozen=True)
class ReportSectionUpdated(AnalysisEvent):
    """A report section gained content (section_key doubles as the md filename)."""

    section_key: str    # e.g. "market_report", "investment_plan"
    content: str


@dataclass(frozen=True)
class AgentStatusChanged(AnalysisEvent):
    agent: str          # display name, e.g. "Market Analyst"
    status: str         # "pending" | "in_progress" | "completed"


@dataclass(frozen=True)
class TimelineNoted(AnalysisEvent):
    """A one-line timeline entry for the dashboard event trail."""

    text: str


@dataclass(frozen=True)
class StageMarked(AnalysisEvent):
    stage: str          # e.g. "Stage C"


@dataclass(frozen=True)
class MetricsUpdated(AnalysisEvent):
    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0


# ---------------------------------------------------------------------------
# Shared display vocabulary (part of the event contract)
# ---------------------------------------------------------------------------

ANALYST_AGENT_NAMES = {
    "market": "Market Analyst",
    "social": "Social Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}

# analyst key -> report section key (also the .md filename stem)
REPORT_SECTION_KEYS = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}

RISK_DEBATE_FIELDS = (
    ("aggressive_history", "Aggressive Analyst"),
    ("conservative_history", "Conservative Analyst"),
    ("neutral_history", "Neutral Analyst"),
)


# ---------------------------------------------------------------------------
# Chunk -> events translation
# ---------------------------------------------------------------------------

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


def _strip_speaker_prefix(content: str, agent: str) -> str:
    """Drop a self-introduced speaker prefix ("Aggressive Analyst: ...").

    Debater outputs often open with their own name, but report sections are
    already wrapped in a "### {agent}" heading — keeping both duplicates the
    byline in the final .md artifact.
    """
    prefix = f"{agent}:"
    if content.startswith(prefix):
        return content[len(prefix):].lstrip()
    return content


class ChunkEventTranslator:
    """Translate raw graph state chunks into stable execution events.

    Stateful: deduplicates messages by id and mirrors agent-status bookkeeping
    so downstream consumers can stay dumb. One translator per run.
    """

    def __init__(self, stats_provider: Optional[Callable[[], Dict[str, Any]]] = None):
        self._stats_provider = stats_provider
        self._processed_ids: set = set()
        self.agent_status: Dict[str, str] = {}
        self._report_sections: Dict[str, str] = {}

    def translate(self, chunk: Dict[str, Any], selected_analysts: List[str]) -> List[AnalysisEvent]:
        events: List[AnalysisEvent] = []
        selected_set = set(selected_analysts)
        for message in chunk.get("messages", []):
            msg_id = getattr(message, "id", None)
            if msg_id is not None:
                if msg_id in self._processed_ids:
                    continue
                self._processed_ids.add(msg_id)

            mtype, content = _classify_message(message)
            if content:
                events.append(MessageEmitted(mtype=mtype, content=content))

            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    if isinstance(tc, dict):
                        name, args = tc.get("name", "?"), tc.get("args", {})
                    else:
                        name, args = tc.name, tc.args
                    args_repr = ", ".join(f"{k}={v}" for k, v in args.items()) if isinstance(args, dict) else str(args)
                    events.append(ToolCallObserved(name=name, args_repr=args_repr))

        events.extend(self._analyst_status_events(chunk, selected_analysts, selected_set))
        # A4: verification summary becomes its own report artifact
        verification = chunk.get("verification")
        if isinstance(verification, dict):
            total = verification.get("claims_total", 0)
            if total and total != getattr(self, "_last_verification_total", None):
                self._last_verification_total = total
                events.append(ReportSectionUpdated(
                    section_key="verification_summary",
                    content=str(verification.get("summary", "")),
                ))
                events.append(TimelineNoted(
                    text=f"Evidence verified {verification.get('verified', 0)}/{total} numeric claims"
                ))

        # B3/A5: constraint overrides and gate comments surface on the timeline
        orch = chunk.get("orchestration") or {}
        overrides = orch.get("constraint_overrides")
        if (
            isinstance(overrides, list)
            and overrides
            and len(overrides) != getattr(self, "_last_override_count", 0)
        ):
            self._last_override_count = len(overrides)
            last = overrides[-1]
            events.append(TimelineNoted(
                text=f"ConstraintEnforcer: proposed {last.get('proposed')}% clamped to {last.get('cap')}% (max_single)"
            ))
        gate_comment = chunk.get("human_override_comment")
        if gate_comment and gate_comment != getattr(self, "_last_gate_comment", None):
            self._last_gate_comment = gate_comment
            events.append(TimelineNoted(text=f"HumanGate comment: {str(gate_comment)[:80]}"))

        events.extend(self._debate_events(chunk))
        events.extend(self._metrics_events())
        return events

    # -- Analyst statuses ----------------------------------------------------

    def _analyst_status_events(
        self, chunk, selected_keys, selected_set
    ) -> List[AnalysisEvent]:
        events: List[AnalysisEvent] = []
        found_active = False
        structured_reports = chunk.get("analyst_reports") or {}
        for key in [k for k in ["market", "social", "news", "fundamentals"] if k in selected_set]:
            agent = ANALYST_AGENT_NAMES[key]
            section_key = REPORT_SECTION_KEYS[key]

            report_value = structured_reports.get(key) or chunk.get(section_key)
            if report_value:
                events.append(ReportSectionUpdated(section_key=section_key, content=report_value))
                self._report_sections[section_key] = report_value

            has_report = bool(self._report_sections.get(section_key))
            if has_report:
                if self.agent_status.get(agent) != "completed":
                    events.append(AgentStatusChanged(agent=agent, status="completed"))
                    self.agent_status[agent] = "completed"
            elif not found_active:
                if self.agent_status.get(agent) != "in_progress":
                    events.append(AgentStatusChanged(agent=agent, status="in_progress"))
                self.agent_status[agent] = "in_progress"
                found_active = True
            else:
                if self.agent_status.get(agent) != "pending":
                    events.append(AgentStatusChanged(agent=agent, status="pending"))
                self.agent_status[agent] = "pending"

        # Transition to research team when all analysts done
        if not found_active and selected_keys:
            bull = "Bull Researcher"
            if self.agent_status.get(bull, "pending") == "pending":
                events.append(AgentStatusChanged(agent=bull, status="in_progress"))
                self.agent_status[bull] = "in_progress"
                events.append(TimelineNoted(text=f"Stage 1 complete, {bull} started"))
        return events

    # -- Debate / trader / risk cascade ---------------------------------------

    def _debate_events(self, chunk) -> List[AnalysisEvent]:
        events: List[AnalysisEvent] = []
        debate_blocks = chunk.get("debate_blocks") or {}
        decision_blocks = chunk.get("decision_blocks") or {}

        # Investment debate
        debate = debate_blocks.get("investment") or chunk.get("investment_debate_state")
        if debate:
            bull = debate.get("bull_history", "").strip()
            bear = debate.get("bear_history", "").strip()
            judge = debate.get("judge_decision", "").strip()

            if bull or bear:
                events.append(TimelineNoted(text="Research: debate in progress"))
            if bull:
                events.append(ReportSectionUpdated(
                    section_key="investment_plan",
                    content=f"### Bull Researcher\n{_strip_speaker_prefix(bull, 'Bull Researcher')}"))
            if bear:
                events.append(ReportSectionUpdated(
                    section_key="investment_plan",
                    content=f"### Bear Researcher\n{_strip_speaker_prefix(bear, 'Bear Researcher')}"))
            if judge:
                events.append(ReportSectionUpdated(
                    section_key="investment_plan",
                    content=f"### Research Manager\n{_strip_speaker_prefix(judge, 'Research Manager')}"))
                for agent in ("Research Manager", "Bull Researcher"):
                    if self.agent_status.get(agent) != "completed":
                        events.append(AgentStatusChanged(agent=agent, status="completed"))
                        self.agent_status[agent] = "completed"
                if self.agent_status.get("Trader") != "in_progress":
                    events.append(AgentStatusChanged(agent="Trader", status="in_progress"))
                    self.agent_status["Trader"] = "in_progress"
                events.append(TimelineNoted(text="Research complete, Trader started"))
                events.append(StageMarked(stage="Stage C"))

        # A2: convergence judgments surface on the dashboard timeline
        debate_score = (debate or {}).get("convergence_score")
        if debate_score is not None and debate_score != getattr(self, "_last_convergence", None):
            self._last_convergence = debate_score
            tag = "converged-early-stop" if debate_score <= 2 else "escalate" if debate_score >= 4 else "neutral"
            events.append(TimelineNoted(text=f"Debate convergence: score={debate_score} ({tag})"))

        # Trader
        trader_plan = decision_blocks.get("trader_plan") or chunk.get("trader_investment_plan")
        if trader_plan:
            events.append(ReportSectionUpdated(
                section_key="trader_investment_plan", content=trader_plan))
            if self.agent_status.get("Trader") != "completed":
                events.append(AgentStatusChanged(agent="Trader", status="completed"))
                self.agent_status["Trader"] = "completed"
                if self.agent_status.get("Aggressive Analyst") != "in_progress":
                    events.append(AgentStatusChanged(agent="Aggressive Analyst", status="in_progress"))
                    self.agent_status["Aggressive Analyst"] = "in_progress"
                events.append(TimelineNoted(text="Trader: plan complete, Risk team started"))

        # Risk debate
        risk = debate_blocks.get("risk") or chunk.get("risk_debate_state")
        if risk:
            for field_name, agent in RISK_DEBATE_FIELDS:
                content = _strip_speaker_prefix(risk.get(field_name, "").strip(), agent)
                if content:
                    if self.agent_status.get(agent) != "completed":
                        if self.agent_status.get(agent) != "in_progress":
                            events.append(AgentStatusChanged(agent=agent, status="in_progress"))
                            self.agent_status[agent] = "in_progress"
                    events.append(ReportSectionUpdated(
                        section_key="final_trade_decision", content=f"### {agent}\n{content}"))

            judge = _strip_speaker_prefix(risk.get("judge_decision", "").strip(), "Portfolio Manager")
            if judge:
                events.append(ReportSectionUpdated(
                    section_key="final_trade_decision", content=f"### Portfolio Manager\n{judge}"))
                for agent in ("Aggressive Analyst", "Conservative Analyst", "Neutral Analyst", "Portfolio Manager"):
                    if self.agent_status.get(agent) != "completed":
                        events.append(AgentStatusChanged(agent=agent, status="completed"))
                        self.agent_status[agent] = "completed"
                events.append(TimelineNoted(text="Portfolio: final decision complete"))
        return events

    # -- Metrics ----------------------------------------------------------------

    def _metrics_events(self) -> List[AnalysisEvent]:
        if self._stats_provider is None:
            return []
        stats = self._stats_provider()
        return [
            MetricsUpdated(
                llm_calls=stats.get("llm_calls", 0),
                tool_calls=stats.get("tool_calls", 0),
                tokens_in=stats.get("tokens_in", 0),
                tokens_out=stats.get("tokens_out", 0),
            )
        ]
