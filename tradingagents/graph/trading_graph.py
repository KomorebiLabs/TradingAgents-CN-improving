# TradingAgents/graph/trading_graph.py

import logging
import os
from copy import deepcopy
from pathlib import Path
import json
from datetime import date
from typing import Dict, Any, Tuple, List, Optional
from tradingagents.agents.utils.memory_manager import (
    save_conclusion_summary,
    load_historical_conclusion,
)

logger = logging.getLogger(__name__)


class GraphExecutionError(Exception):
    """Exception raised when graph execution fails."""

    def __init__(self, message: str, recoverable: bool = False):
        super().__init__(message)
        self.message = message
        self.recoverable = recoverable


class _AnalysisStream:
    """Iterator over one streaming analysis run.

    Returned by :meth:`TradingAgentsGraph.stream_analysis`. Iterating yields
    raw LangGraph state snapshots (``stream_mode="values"``). After the
    iterator is exhausted, ``final_state`` / ``decision`` / ``result`` hold
    the synchronized outcome. Graph failures finalize into an error fallback
    state (matching ``propagate()`` semantics) instead of raising mid-stream.
    """

    def __init__(
        self,
        graph: "TradingAgentsGraph",
        company_name: str,
        trade_date,
        callbacks: Optional[List] = None,
        resume: bool = False,
    ):
        self._graph = graph
        self._company = company_name
        self._trade_date = trade_date
        self._callbacks = callbacks
        self.resume = resume
        self.final_state: Optional[Dict[str, Any]] = None
        self.decision: str = ""
        self._consumed = False

    @property
    def result(self) -> Tuple[Dict[str, Any], str]:
        """``(final_state, decision)`` after the stream has been consumed."""
        if self.final_state is None:
            raise RuntimeError("Analysis stream has not been consumed yet.")
        return self.final_state, self.decision

    def __iter__(self):
        if self._consumed:
            raise RuntimeError("Analysis stream can only be consumed once.")
        self._consumed = True
        yield from self._run()

    def _run(self):
        graph = self._graph
        init_state = graph.propagator.create_initial_state(
            self._company, self._trade_date, graph.graph_setup.selected_analysts
        )
        if graph._historical_context is not None:
            init_state["historical_context"] = graph._historical_context
        args = graph.propagator.get_graph_args(callbacks=self._callbacks)
        if graph.run_id:
            # thread_id == run_id: LangGraph checkpoints every super-step under
            # this id, enabling --resume after a crash (E1).
            args.setdefault("config", {}).setdefault("configurable", {})[
                "thread_id"
            ] = graph.run_id

        # Resume semantics: input=None tells LangGraph to continue the existing
        # thread from its last checkpoint instead of starting a new invocation.
        # init_state is still built above so the error-fallback paths keep a
        # well-formed state dict to annotate.
        stream_input = None if self.resume else init_state

        last_state: Optional[Dict[str, Any]] = None
        try:
            for chunk in graph.graph.stream(stream_input, **args):
                if graph.debug:
                    messages = chunk.get("messages", [])
                    if messages:
                        messages[-1].pretty_print()
                last_state = chunk
                yield chunk
        except RecursionError:
            last_state = graph._create_fallback_state(
                init_state,
                f"Max recursion limit reached for {self._company}"
            )
        except Exception as e:
            last_state = graph._create_fallback_state(
                init_state,
                f"Graph execution failed: {str(e)}"
            )

        if last_state is None:
            if graph.debug:
                raise GraphExecutionError(
                    f"No trace collected for {self._company} on {self._trade_date}"
                )
            last_state = graph._create_fallback_state(
                init_state,
                f"Graph execution produced no state for {self._company}"
            )

        final_state = graph._ensure_structured_state(last_state)
        graph.curr_state = final_state
        graph._log_state(self._trade_date, final_state)
        try:
            self.decision = graph.process_signal(
                final_state.get("final_trade_decision", "")
            )
        except Exception:
            self.decision = "N/A"
        self.final_state = final_state


from langgraph.prebuilt import ToolNode

from tradingagents.llm_clients import create_llm_client

from tradingagents.agents import *
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.agents.utils.memory import FinancialSituationMemory, StructuredMemory
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
    STATE_SCHEMA_VERSION,
)
from tradingagents.dataflows.config import set_config

from tradingagents.agents.utils.agent_utils import (
    get_tools_for_analyst,
    build_instrument_profile,
    derive_semantic_flow_controls,
    derive_semantic_selected_analysts,
    validate_semantic_prompt_slots,
)

from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor
from tradingagents.harness.skills.injector import SkillInjector


class TradingAgentsGraph:
    """Main class that orchestrates the trading agents framework."""

    def __init__(
        self,
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config: Dict[str, Any] = None,
        callbacks: Optional[List] = None,
        run_id: Optional[str] = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
            callbacks: Optional list of callback handlers (e.g., for tracking LLM/tool stats)
            run_id: Unique run identifier. When set, a SqliteSaver checkpointer
                is attached under ~/.tradingagents/checkpoints/<run_id>/ and the
                run's LangGraph thread_id equals the run_id — a crashed run can
                then be resumed from the last completed node (no LLM re-billing
                for finished nodes) instead of restarting from scratch.
        """
        self.debug = debug
        self.run_id = run_id
        checkpointer = self._build_checkpointer(run_id) if run_id else None
        # Merge partial user config over a private copy of the defaults so:
        # 1. callers may override individual keys without KeyError on
        #    data_cache_dir / results_dir / max_debate_rounds etc.;
        # 2. instance-level config writes never leak into DEFAULT_CONFIG
        #    or into the caller's dict.
        self.config = deepcopy(DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self.callbacks = callbacks or []
        semantic_slots = validate_semantic_prompt_slots(
            self.config.get("screener_context", {}).get("semantic_prompt_slots", {})
        )
        semantic_selected_analysts = derive_semantic_selected_analysts(selected_analysts, semantic_slots)
        semantic_flow_controls = derive_semantic_flow_controls(semantic_slots)
        if "screener_context" not in self.config:
            self.config["screener_context"] = {}
        self.config["screener_context"]["semantic_prompt_slots"] = semantic_slots
        self.config["semantic_flow_controls"] = semantic_flow_controls

        # Update the interface's config
        set_config(self.config)

        # Create necessary directories
        os.makedirs(self.config["data_cache_dir"], exist_ok=True)
        os.makedirs(self.config["results_dir"], exist_ok=True)

        # Initialize LLMs with provider-specific thinking configuration
        llm_kwargs = self._get_provider_kwargs()

        # Add callbacks to kwargs if provided (passed to LLM constructor)
        if self.callbacks:
            llm_kwargs["callbacks"] = self.callbacks

        deep_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["deep_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )
        quick_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )

        self.deep_thinking_llm = deep_client.get_llm()
        self.quick_thinking_llm = quick_client.get_llm()
        
        # Initialize memories
        self.bull_memory = FinancialSituationMemory("bull_memory", self.config)
        self.bear_memory = FinancialSituationMemory("bear_memory", self.config)
        self.trader_memory = FinancialSituationMemory("trader_memory", self.config)
        self.invest_judge_memory = FinancialSituationMemory("invest_judge_memory", self.config)
        self.portfolio_manager_memory = FinancialSituationMemory("portfolio_manager_memory", self.config)
        self.route_memory = StructuredMemory("route_memory", self.config)

        # P4 Memory: Load historical conclusion for company_of_interest
        self._historical_context: Optional[Dict[str, Any]] = None
        company = self.config.get("company_of_interest", "")
        if company:
            self._historical_context = load_historical_conclusion(company)

        # Skill injector for decision-node skill injection
        self._skill_injector = SkillInjector()

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config["max_debate_rounds"],
            max_risk_discuss_rounds=self.config["max_risk_discuss_rounds"],
            max_recur_limit=self.config.get("max_recur_limit", 100),
            semantic_flow_controls=semantic_flow_controls,
        )
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            self.bull_memory,
            self.bear_memory,
            self.trader_memory,
            self.invest_judge_memory,
            self.portfolio_manager_memory,
            self.conditional_logic,
            skill_injector=self._skill_injector,
        )

        self.propagator = Propagator(config=self.config)
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Set up the graph
        self.graph = self.graph_setup.setup_graph(
            semantic_selected_analysts, checkpointer=checkpointer
        )

    @staticmethod
    def _build_checkpointer(run_id: str):
        """Create a per-run SqliteSaver under ~/.tradingagents/checkpoints/.

        Falls back to None (no checkpointing) if the sqlite checkpoint package
        is unavailable, so absence never breaks a run — resume simply won't
        be possible for it.
        """
        try:
            import sqlite3

            from langgraph.checkpoint.sqlite import SqliteSaver

            ckpt_dir = Path.home() / ".tradingagents" / "checkpoints" / run_id
            ckpt_dir.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                ckpt_dir / "checkpoint.db", check_same_thread=False
            )
            return SqliteSaver(conn)
        except Exception as exc:  # pragma: no cover - optional dependency
            logging.getLogger(__name__).warning(
                "checkpointer unavailable for run %s: %s", run_id, exc
            )
            return None

    def _get_provider_kwargs(self) -> Dict[str, Any]:
        """Get provider-specific kwargs for LLM client creation."""
        kwargs = {}
        provider = self.config.get("llm_provider", "").lower()

        if provider == "google":
            thinking_level = self.config.get("google_thinking_level")
            if thinking_level:
                kwargs["thinking_level"] = thinking_level

        elif provider == "openai":
            reasoning_effort = self.config.get("openai_reasoning_effort")
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort

        elif provider == "anthropic":
            effort = self.config.get("anthropic_effort")
            if effort:
                kwargs["effort"] = effort

        return kwargs

    def _create_tool_nodes(self) -> Dict[str, ToolNode]:
        """Create tool nodes for different data sources using abstract methods."""
        company_name = self.config.get("company_of_interest", "")
        instrument_profile = build_instrument_profile(company_name, self.config)
        def _safe_tools(analyst_type: str):
            try:
                return get_tools_for_analyst(analyst_type, instrument_profile["symbol"], self.config)
            except Exception as exc:  # tool assembly must not kill the graph, but the cause must be visible
                logger.warning("Tool assembly failed for analyst %s: %s", analyst_type, exc)
                return []
        return {
            "market": ToolNode(_safe_tools("market")),
            "social": ToolNode(_safe_tools("social")),
            "news": ToolNode(_safe_tools("news")),
            "fundamentals": ToolNode(_safe_tools("fundamentals")),
        }

    def stream_analysis(
        self,
        company_name: str,
        trade_date,
        callbacks: Optional[List] = None,
        resume: bool = False,
    ) -> _AnalysisStream:
        """Public streaming API for one analysis run.

        Usage::

            run = graph.stream_analysis(company, date, callbacks=[handler])
            for chunk in run:
                ...  # dashboard updates / logging
            final_state, decision = run.result

        Chunks are raw LangGraph state snapshots (``stream_mode="values"``).
        On graph failure the stream finalizes into an error fallback state
        instead of raising mid-stream, matching ``propagate()`` semantics.

        With ``resume=True`` (requires the graph to have been constructed with
        a ``run_id``), the run continues the checkpointed thread instead of
        starting a new invocation — completed nodes are not re-executed.
        """
        self.ticker = company_name
        return _AnalysisStream(
            self, company_name, trade_date, callbacks=callbacks, resume=resume
        )

    def propagate(self, company_name, trade_date):
        """Run the trading agents graph for a company on a specific date.

        Raises:
            GraphExecutionError: If graph execution fails after retries
        """
        stream = self.stream_analysis(company_name, trade_date)
        for _ in stream:
            pass
        return stream.result

    def _create_fallback_state(
        self, initial_state: Dict[str, Any], error_message: str
    ) -> Dict[str, Any]:
        """Create a fallback state when graph execution fails.

        Args:
            initial_state: The initial state before execution
            error_message: Error message describing the failure

        Returns:
            A state with error information and fallback values
        """
        orchestration = dict(initial_state.get("orchestration", {}))
        orchestration["stage"] = "error"
        orchestration["phase"] = "error"
        orchestration["next_stage"] = "error"
        orchestration["completed"] = False
        orchestration["final_route"] = "error"
        orchestration["final_reason"] = error_message

        initial_state["orchestration"] = orchestration
        initial_state["final_trade_decision"] = (
            f"System error during analysis: {error_message}"
        )
        return initial_state

    def _ensure_structured_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Reconcile canonical structured blocks with legacy flat fields.

        Canonical policy (agent_states.Canonical State Policy, schema v2):
        structured blocks win on conflict; flat fields are filled from
        structured for legacy readers (graph/setup.py routers,
        graph/reflection.py). Structured blocks are filled from flat only
        when missing (legacy-only writers, e.g. _create_fallback_state).

        Historical note: this method was ``_synchronize_structured_state``
        and mirrored FLAT -> structured unconditionally, which would wipe
        structured-only writes. That direction is retired.
        """
        state.setdefault("schema_version", STATE_SCHEMA_VERSION)
        state.setdefault("screener_context", {})
        state["semantic_prompt_slots"] = validate_semantic_prompt_slots(
            state.get("semantic_prompt_slots")
            or state.get("screener_context", {}).get("semantic_prompt_slots", {})
        )
        state["screener_context"]["semantic_prompt_slots"] = state["semantic_prompt_slots"]
        route_decision = dict(
            state.get("route_decision")
            or state.get("screener_context", {}).get("route_decision", {})
            or {}
        )
        state["route_decision"] = route_decision
        state["screener_context"]["route_decision"] = route_decision
        ticker_info = dict(state.get("ticker_info", {}))
        ticker_info.setdefault("symbol", state.get("company_of_interest", ""))
        ticker_info.setdefault("trade_date", state.get("trade_date", ""))
        ticker_info.setdefault("instrument_context", "")
        ticker_info.setdefault(
            "selected_analysts",
            getattr(self.graph_setup, "selected_analysts", []),
        )
        ticker_info.setdefault("route_decision", route_decision)
        instrument_profile = build_instrument_profile(
            ticker_info.get("symbol", state.get("company_of_interest", "")),
            self.config,
        )
        ticker_info.setdefault("market", instrument_profile["market"])
        ticker_info.setdefault("exchange", instrument_profile["exchange"])
        ticker_info.setdefault("is_cn_equity", instrument_profile["is_cn_equity"])
        ticker_info.setdefault("segment", instrument_profile["segment"])
        ticker_info.setdefault("style_bucket", instrument_profile["style_bucket"])
        ticker_info.setdefault("skills", instrument_profile["skills"])
        state["ticker_info"] = ticker_info

        # -- Analyst reports: structured (analyst_reports) is canonical ------
        report_pairs = (
            ("market", "market_report"),
            ("sentiment", "sentiment_report"),
            ("news", "news_report"),
            ("fundamentals", "fundamentals_report"),
        )
        analyst_reports = dict(state.get("analyst_reports") or {})
        for structured_key, flat_key in report_pairs:
            structured_val = analyst_reports.get(structured_key, "")
            flat_val = state.get(flat_key, "")
            if structured_val:
                state[flat_key] = structured_val
            elif flat_val:
                analyst_reports[structured_key] = flat_val
        state["analyst_reports"] = analyst_reports

        # -- Debate states: keep flat and structured as the SAME object ----
        debate_blocks = dict(state.get("debate_blocks") or {})
        investment_debate = (
            state.get("investment_debate_state")
            or debate_blocks.get("investment")
            or {}
        )
        risk_debate = (
            state.get("risk_debate_state")
            or debate_blocks.get("risk")
            or {}
        )
        debate_blocks["investment"] = investment_debate
        debate_blocks["risk"] = risk_debate
        state["debate_blocks"] = debate_blocks
        state["investment_debate_state"] = investment_debate
        state["risk_debate_state"] = risk_debate

        # -- Decisions: structured (decision_blocks) is canonical -----------
        decision_pairs = (
            ("investment_plan", "investment_plan"),
            ("trader_plan", "trader_investment_plan"),
            ("final_trade_decision", "final_trade_decision"),
        )
        decision_blocks = dict(state.get("decision_blocks") or {})
        for structured_key, flat_key in decision_pairs:
            structured_val = decision_blocks.get(structured_key, "")
            flat_val = state.get(flat_key, "")
            if structured_val:
                state[flat_key] = structured_val
            elif flat_val:
                decision_blocks[structured_key] = flat_val
        state["decision_blocks"] = decision_blocks

        orchestration = dict(state.get("orchestration", {}))
        orchestration.setdefault("stage", "completed")
        orchestration.setdefault("phase", "completed")
        orchestration.setdefault("next_stage", "completed")
        orchestration.setdefault("completed", bool(state.get("final_trade_decision")))
        orchestration.setdefault("final_route", "")
        orchestration.setdefault("final_reason", "")
        orchestration.setdefault("context_budget_tokens", 24000)
        orchestration.setdefault("compression_threshold_tokens", 18000)
        orchestration.setdefault("compression_notes", "")
        orchestration.setdefault("compression_required", False)
        orchestration.setdefault(
            "selected_analysts",
            getattr(self.graph_setup, "selected_analysts", []),
        )
        orchestration.setdefault("route_decision", route_decision)
        orchestration.setdefault(
            "enable_confidence_score",
            bool(self.config.get("enable_confidence_score", False)),
        )
        orchestration.setdefault("event_trail", [])
        state["orchestration"] = orchestration
        return state

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file (canonical structured shape).

        Structured blocks are logged once as the source of truth; the flat
        report/debate duplicates of the legacy log format were dropped
        (zero code readers — the log is human-facing only). The flat
        ``final_trade_decision`` is kept as a quick-grep convenience key.
        """
        orchestration = final_state.get("orchestration", {})
        ticker_info = final_state.get("ticker_info", {})
        route_summary = self.reflector.get_route_summary(final_state)
        decision_blocks = final_state.get("decision_blocks", {})

        self.log_states_dict[str(trade_date)] = {
            "schema_version": final_state.get("schema_version", 1),
            "company_of_interest": final_state.get("company_of_interest", ""),
            "trade_date": final_state.get("trade_date", ""),
            "screener_context": final_state.get("screener_context", {}),
            "semantic_prompt_slots": final_state.get("semantic_prompt_slots", {}),
            "route_decision": final_state.get("route_decision", {}),
            "ticker_info": ticker_info,
            "analyst_reports": final_state.get("analyst_reports", {}),
            "debate_blocks": final_state.get("debate_blocks", {}),
            "decision_blocks": decision_blocks,
            "orchestration": orchestration,
            "orchestration_summary": {
                "completed": orchestration.get("completed", False),
                "stage": orchestration.get("stage", ""),
                "phase": orchestration.get("phase", ""),
                "next_stage": orchestration.get("next_stage", ""),
                "final_route": orchestration.get("final_route", ""),
                "final_reason": orchestration.get("final_reason", ""),
                "compression_required": orchestration.get("compression_required", False),
                "compression_notes_preview": str(orchestration.get("compression_notes", ""))[:300],
                "selected_analysts": orchestration.get("selected_analysts", []),
                "segment": ticker_info.get("segment", ""),
                "style_bucket": ticker_info.get("style_bucket", ""),
                "skills": ticker_info.get("skills", []),
            },
            "route_summary": route_summary,
            "event_trail": orchestration.get("event_trail", []),
            # Legacy quick-access key (identical to decision_blocks.final_trade_decision)
            "final_trade_decision": decision_blocks.get("final_trade_decision", ""),
        }

        # Save to file
        directory = Path(self.config["results_dir"]) / self.ticker / "TradingAgentsStrategy_logs"
        directory.mkdir(parents=True, exist_ok=True)

        log_path = directory / f"full_states_log_{trade_date}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self.log_states_dict[str(trade_date)], f, indent=4)

    def reflect_and_remember(self, returns_losses):
        """Reflect on decisions and update memory based on returns."""
        if self.curr_state is None:
            raise ValueError("No current state available for reflection.")
        self.reflector.reflect_bull_researcher(
            self.curr_state, returns_losses, self.bull_memory
        )
        self.reflector.reflect_bear_researcher(
            self.curr_state, returns_losses, self.bear_memory
        )
        self.reflector.reflect_trader(
            self.curr_state, returns_losses, self.trader_memory
        )
        self.reflector.reflect_invest_judge(
            self.curr_state, returns_losses, self.invest_judge_memory
        )
        self.reflector.reflect_portfolio_manager(
            self.curr_state, returns_losses, self.portfolio_manager_memory,
            route_memory=self.route_memory
        )
        # P4 Memory: Generate and persist conclusion summary
        try:
            summary = self.reflector.generate_conclusion_summary(self.curr_state)
            ticker = self.curr_state.get("company_of_interest", "")
            trade_date = str(self.curr_state.get("trade_date", ""))
            if ticker and trade_date:
                save_conclusion_summary(ticker, trade_date, summary)
        except Exception:
            # Memory persistence must never crash the reflection flow
            pass

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal)

    def get_route_history(self) -> List[Dict[str, Any]]:
        """Get the route summary from the last execution.

        Returns:
            Route summary dictionary with pattern analysis
        """
        if self.curr_state is None:
            return {}
        return self.reflector.get_route_summary(self.curr_state)

    def get_similar_routes(
        self,
        segment: str = "",
        style_bucket: str = "",
        n_matches: int = 3,
        compression_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Retrieve similar route patterns from memory.

        Args:
            segment: Segment to match (e.g., "cn_main_board_equity")
            style_bucket: Style bucket to match (e.g., "growth_style_candidate")
            n_matches: Number of similar cases to retrieve
            compression_only: If True, only return routes where compression was triggered

        Returns:
            List of similar route cases from memory with metadata
        """
        filters = {}
        if segment:
            filters["segment"] = segment
        if style_bucket:
            filters["style_bucket"] = style_bucket
        if compression_only:
            filters["compression_triggered"] = True

        query = f"Segment: {segment}\nStyle: {style_bucket}"

        if filters:
            return self.route_memory.get_memories(
                query, n_matches=n_matches, filters=filters
            )
        else:
            return self.route_memory.get_memories(query, n_matches=n_matches)

    def get_route_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored route patterns.

        Returns:
            Dict with route distribution, segment distribution, and compression stats
        """
        return self.route_memory.get_route_statistics()
