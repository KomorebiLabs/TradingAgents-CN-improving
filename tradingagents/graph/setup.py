# TradingAgents/graph/setup.py
"""================================================================================
LangGraph DAG 构建器 - 整个框架的"蓝图设计师"
================================================================================
【模块职责】
    GraphSetup 类负责将所有 Agent 节点连接成完整的 DAG（有向无环图）。

    核心工作：
    1. 创建所有节点（Analyst / Researcher / Trader / Risk Manager）
    2. 定义节点之间的边（Edges）和条件路由（Conditional Edges）
    3. 编译生成可执行的 workflow 对象

【DAG 拓扑结构】
    START
       │
       ▼
    ┌─────────────────────────────────────────────────────────────┐
    │              Analyst Team（可配置顺序）                        │
    │   Market Analyst → Social Analyst → News Analyst → ...      │
    │        │              │              │                       │
    │        ▼              ▼              ▼                       │
    │   tools_market   tools_social   tools_news  ...            │
    │        │              │              │                       │
    │        └──────────────┴──────────────┘                       │
    └─────────────────────────────────────────────────────────────┘
       │
       ▼
    ┌─────────────────────────────────────────────────────────────┐
    │              Research Team（多空辩论）                        │
    │   Bull Researcher ◄──────────────────► Bear Researcher     │
    │        │                                    │                │
    │        └───────────► Research Manager ◄────┘                │
    └─────────────────────────────────────────────────────────────┘
       │
       ▼
    ┌─────────────────────────────────────────────────────────────┐
    │              Trading Team                                     │
    │                   Trader                                     │
    └─────────────────────────────────────────────────────────────┘
       │
       ▼
    ┌─────────────────────────────────────────────────────────────┐
    │              Risk Management Team（三方辩论）                  │
    │   Aggressive ◄──► Conservative ◄──► Neutral               │
    │        │                   │              │                  │
    │        └───────────────────┴──────────────┘                │
    │                        │                                    │
    │                        ▼                                    │
    │              Portfolio Manager                                │
    └─────────────────────────────────────────────────────────────┘
       │
       ▼
      END

================================================================================
"""


from typing import Any, Dict, Optional
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from tradingagents.agents import (
    create_msg_delete,
    create_market_analyst,
    create_social_media_analyst,
    create_news_analyst,
    create_fundamentals_analyst,
    create_bull_researcher,
    create_bear_researcher,
    create_research_manager,
    create_trader,
    create_aggressive_debater,
    create_conservative_debator,
    create_neutral_debator,
    create_portfolio_manager,
)
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.agents.utils.state_helpers import (
    build_orchestration_event,
    append_orchestration_event,
    determine_risk_debate_exit_stage,
    extract_semantic_trigger_audit,
)

from tradingagents.dataflows.config import get_config

from .conditional_logic import ConditionalLogic


def create_orchestration_router(source_phase: str, default_next_stage: str):
    def router_node(state: AgentState):
        orchestration = dict(state.get("orchestration", {}))
        semantic_prompt_slots = dict(
            state.get("semantic_prompt_slots", {})
            or state.get("screener_context", {}).get("semantic_prompt_slots", {})
            or {}
        )
        threshold = int(orchestration.get(
            "compression_threshold_chars",
            get_config().get("orchestration_compression_threshold_chars", 36000),
        ))
        existing_next_stage = orchestration.get("next_stage")
        existing_notes = str(orchestration.get("compression_notes", "")).strip()
        route_decision = dict(state.get("route_decision", {}) or orchestration.get("route_decision", {}) or {})
        route_rule = str(orchestration.get("route_rule", "") or route_decision.get("route_family", "") or f"{source_phase}_route")
        applied_controls = dict(orchestration.get("applied_controls", {}) or {})
        route_reason = str(orchestration.get("route_reason", "") or route_decision.get("route_reason", "") or "")

        if source_phase == "analyst":
            analyst_reports = state.get("analyst_reports", {})
            estimated_context = sum(len(str(analyst_reports.get(key, ""))) for key in ["market", "sentiment", "news", "fundamentals"])
        elif source_phase == "research":
            estimated_context = len(str(state.get("investment_debate_state", {}).get("history", "")))
        elif source_phase == "trader":
            estimated_context = len(str(state.get("trader_investment_plan", "")))
        else:
            estimated_context = len(str(state.get("risk_debate_state", {}).get("history", "")))

        orchestration["stage"] = f"route_{default_next_stage}"
        orchestration["phase"] = source_phase
        orchestration["next_stage"] = existing_next_stage or default_next_stage
        wants_handoff = str(orchestration["next_stage"]).endswith("_handoff")
        orchestration["compression_required"] = (
            wants_handoff or (estimated_context >= threshold and not existing_notes)
        )
        if not route_reason:
            if wants_handoff:
                route_reason = f"{source_phase}_handoff_requested"
            elif estimated_context >= threshold and not existing_notes:
                route_reason = f"{source_phase}_compression_threshold_exceeded"
            else:
                route_reason = f"{source_phase}_direct_path"
        applied_controls.update(
            {
                "source_phase": source_phase,
                "compression_threshold_chars": threshold,
                "estimated_context": estimated_context,
                "wants_handoff": wants_handoff,
            }
        )
        semantic_trigger_audit = extract_semantic_trigger_audit(
            route_decision=route_decision,
            semantic_prompt_slots=semantic_prompt_slots,
            applied_controls=applied_controls,
        )
        orchestration["semantic_trigger_audit"] = semantic_trigger_audit

        event = build_orchestration_event(
            node_name=f"Route {source_phase.capitalize()} Phase",
            orchestration=orchestration,
            context_estimate=estimated_context,
            route_rule=route_rule,
            route_reason=route_reason,
            applied_controls=applied_controls,
            semantic_trigger_audit=semantic_trigger_audit,
        )
        existing_trail = orchestration.get("event_trail")
        orchestration["event_trail"] = append_orchestration_event(existing_trail, event)

        return {"orchestration": orchestration, "sender": "Orchestration Router"}

    return router_node


def create_phase_handoff_node(source_phase: str, next_stage: str, llm: Any):
    def handoff_node(state: AgentState):
        orchestration = dict(state.get("orchestration", {}))
        semantic_prompt_slots = dict(
            state.get("semantic_prompt_slots", {})
            or state.get("screener_context", {}).get("semantic_prompt_slots", {})
            or {}
        )
        resolved_next_stage = orchestration.get("next_stage") or next_stage
        if source_phase == "analyst":
            analyst_reports = state.get("analyst_reports", {})
            raw_context = "\n\n".join(
                f"{key}: {str(analyst_reports.get(key, '')).strip()}"
                for key in ["market", "sentiment", "news", "fundamentals"]
                if str(analyst_reports.get(key, "")).strip()
            )
            summary_prompt = (
                "Summarize the following analyst outputs into a compact handoff memo for downstream investment debate. "
                "Preserve only the highest-signal evidence, contradictions, and unresolved risks.\n\n"
                f"{raw_context}"
            )
        elif source_phase == "research":
            debate = state.get("investment_debate_state", {})
            raw_context = str(debate.get("history", "")).strip()
            summary_prompt = (
                "You are a research handoff summarizer. Convert the following bull/bear investment debate into a trader-ready handoff memo. "
                "Your memo must preserve: (1) strongest bull thesis, (2) strongest bear thesis, (3) current decision edge, "
                "(4) unresolved risks, and (5) what the trader must pay attention to next.\n\n"
                f"{raw_context}"
            )
        elif source_phase == "trader":
            trader_plan = str(state.get("trader_investment_plan", "")).strip()
            investment_plan = str(state.get("investment_plan", "")).strip()
            raw_context = (
                f"Research manager plan:\n{investment_plan}\n\n"
                f"Trader plan:\n{trader_plan}"
            ).strip()
            summary_prompt = (
                "You are a trader-to-risk handoff summarizer. Compress the following trading plan into a risk-review memo. "
                "Preserve: (1) core trade direction, (2) timing and sizing assumptions, (3) explicit risk controls already proposed, "
                "(4) remaining blind spots that risk analysts must attack next.\n\n"
                f"{raw_context}"
            )
        else:
            debate = state.get("risk_debate_state", {})
            raw_context = str(debate.get("history", "")).strip()
            summary_prompt = (
                "You are a risk handoff summarizer. Convert the following risk debate into a portfolio-manager memo. "
                "Preserve: (1) strongest aggressive case, (2) strongest conservative case, (3) neutral balancing view, "
                "(4) unresolved downside risks, and (5) what the portfolio manager must finalize next.\n\n"
                f"{raw_context}"
            )

        response = llm.invoke(summary_prompt)
        compression_notes = response.content

        orchestration["stage"] = f"{source_phase}_handoff"
        orchestration["phase"] = source_phase
        if str(resolved_next_stage).endswith("_handoff"):
            resolved_next_stage = resolved_next_stage[: -len("_handoff")]
        orchestration["next_stage"] = resolved_next_stage
        orchestration["compression_required"] = False
        orchestration["compression_notes"] = compression_notes
        route_decision = dict(orchestration.get("route_decision", {}) or state.get("route_decision", {}) or {})
        route_rule = str(orchestration.get("route_rule", "") or route_decision.get("route_family", "") or f"{source_phase}_handoff")
        route_reason = str(orchestration.get("route_reason", "") or route_decision.get("route_reason", "") or "compression_handoff_generated")
        applied_controls = dict(orchestration.get("applied_controls", {}) or {})
        applied_controls.update(
            {
                "source_phase": source_phase,
                "handoff_summary_length": len(compression_notes),
                "resolved_next_stage": resolved_next_stage,
            }
        )
        semantic_trigger_audit = extract_semantic_trigger_audit(
            route_decision=route_decision,
            semantic_prompt_slots=semantic_prompt_slots,
            applied_controls=applied_controls,
        )
        orchestration["semantic_trigger_audit"] = semantic_trigger_audit

        event = build_orchestration_event(
            node_name=f"Summarize {source_phase.capitalize()} Phase",
            orchestration=orchestration,
            context_estimate=len(raw_context),
            route_rule=route_rule,
            route_reason=route_reason,
            applied_controls=applied_controls,
            semantic_trigger_audit=semantic_trigger_audit,
        )
        existing_trail = orchestration.get("event_trail")
        orchestration["event_trail"] = append_orchestration_event(existing_trail, event)

        return {
            "orchestration": orchestration,
            "sender": "Phase Handoff",
        }

    return handoff_node


_CONVERGENCE_SPEECH_BUDGET = 8000  # chars per side; beyond this, head+tail sampling
_CONVERGENCE_RE = None  # compiled lazily to keep module import cheap


def _latest_turn(history: str, marker: str) -> str:
    """Extract the most recent speech from an accumulated debate history."""
    if not history:
        return ""
    parts = history.split("\n" + marker)
    return marker + parts[-1] if parts[-1] else history[-_CONVERGENCE_SPEECH_BUDGET:]


def _truncate_speech(text: str, budget: int = _CONVERGENCE_SPEECH_BUDGET):
    """Head 30% + tail 60% with an explicit omission marker (A2 rule).

    Rebuttals cluster at the end of a speech (quote-then-refute), hence the
    tail-heavy split. Returns (text, truncated) — the caller must floor the
    divergence score at 3 when truncated: no early stop on partial evidence.
    """
    if len(text) <= budget:
        return text, False
    head, tail = int(budget * 0.3), int(budget * 0.6)
    omitted = len(text) - head - tail
    return f"{text[:head]}\n[已省略 {omitted} 字符]\n{text[-tail:]}", True


def create_debate_convergence_node(llm: Any):
    """A2: convergence-driven debate stopping.

    Runs after every completed Bull+Bear round. A quick-model judge scores
    divergence 1-5 by the operational criterion "does an unanswered core
    rebuttal remain?" — NOT tone. Design rules:
    - full speeches within budget; explicit marker + score floor 3 if truncated;
    - parse failure / disabled config -> neutral score 3 (falls back to
      round-count routing);
    - every judgment lands in orchestration.convergence_log for audit.
    """
    import re

    from tradingagents.dataflows.config import get_config

    def convergence_node(state: AgentState):
        debate = dict(state.get("investment_debate_state", {}) or {})
        if not get_config().get("convergence_check", True):
            return {}  # feature flag off: routing falls back to round counts

        bull_speech, bull_trunc = _truncate_speech(
            _latest_turn(debate.get("bull_history", ""), "Bull Analyst: ")
        )
        bear_speech, bear_trunc = _truncate_speech(
            _latest_turn(debate.get("bear_history", ""), "Bear Analyst: ")
        )

        prompt = (
            "You are a debate convergence judge. Two analysts have debated an "
            "investment. Score their divergence 1-5 using ONE criterion: does a "
            "CORE rebuttal remain unanswered? (1-2 = core points addressed, "
            "positions converged; 3 = mixed or uncertain; 4-5 = significant "
            "unanswered core rebuttals remain). Judge substance, not tone or "
            "length. If parts were omitted, be conservative.\n\n"
            f"Latest Bull argument:\n{bull_speech}\n\n"
            f"Latest Bear argument:\n{bear_speech}\n\n"
            'Respond ONLY with: <convergence score="N" divergences="..." '
            'consensus="..."/> where divergences lists unanswered core '
            "rebuttals (empty if converged) and consensus lists points both "
            "sides already agree on."
        )

        score, divergences, consensus = 3, "", ""
        truncated = bull_trunc or bear_trunc
        try:
            response = llm.invoke(prompt)
            text = str(getattr(response, "content", response))
            match = re.search(
                r'<convergence\s+score\s*=\s*"?(\d)"?', text
            )
            if match:
                score = min(5, max(1, int(match.group(1))))
            div = re.search(r'divergences\s*=\s*"([^"]*)"', text)
            con = re.search(r'consensus\s*=\s*"([^"]*)"', text)
            divergences = div.group(1) if div else ""
            consensus = con.group(1) if con else ""
        except Exception:
            score, divergences, consensus = 3, "", ""  # neutral: no routing change

        if truncated and score < 3:
            score = 3  # never early-stop on partial evidence (A2 hard rule)

        debate["convergence_score"] = score
        debate["convergence_divergences"] = divergences
        debate["convergence_consensus"] = consensus
        log = list(debate.get("convergence_log") or [])
        log.append({
            "count": debate.get("count", 0),
            "score": score,
            "truncated": truncated,
            "divergences": divergences,
            "consensus": consensus,
        })
        debate["convergence_log"] = log

        orchestration = dict(state.get("orchestration", {}) or {})
        orchestration["convergence_log"] = log

        return {
            "investment_debate_state": debate,
            "orchestration": orchestration,
            "sender": "Debate Convergence Check",
        }

    return convergence_node


class HumanGateAbort(Exception):
    """A5: user chose to abort at the final-decision gate."""


def create_human_gate_node():
    """A5: in-the-loop gate before the Portfolio Manager's final decision.

    Mode "interactive" (config hitl_mode): the node interrupts; the CLI
    shows trader plan + risk summary + cost context and collects one of
    proceed / comment / abort. The comment is ADVISORY — it may influence
    the PM's reasoning weight, but the user has no direct channel to edit
    numbers (authorship stays clean: AI writes, human annotates).
    Default mode "auto": no-op, behavior identical to pre-A5.
    """
    from langgraph.types import interrupt

    def gate_node(state: AgentState):
        if get_config().get("hitl_mode", "auto") != "interactive":
            return {}
        payload = interrupt({
            "gate": "final_decision",
            "trader_plan": str(state.get("trader_investment_plan") or "")[:1500],
            "risk_tail": str((state.get("risk_debate_state") or {}).get("history") or "")[-800:],
            "options": {"proceed": "继续", "comment": "追加评语后继续", "abort": "中止"},
        })
        action = payload.get("action", "proceed") if isinstance(payload, dict) else "proceed"
        if action == "abort":
            raise HumanGateAbort("User aborted at the final-decision gate")
        update: Dict[str, Any] = {"sender": "Human Gate"}
        if action == "comment":
            text = str(payload.get("text") or "")[:2000]
            if text:
                update["human_override_comment"] = text
        return update

    return gate_node


def create_constraint_enforcer_node():
    """B3: programmatic portfolio-constraint enforcement (soft prompt -> hard clamp).

    LLMs under strong conviction ignore soft constraints; the enforcer parses
    the proposed position weight from the final decision, clamps it to
    max_single, annotates the report explicitly and records an auditable
    constraint_override. No portfolio file -> no-op.
    """
    from tradingagents.agents.utils.decision_constraints import (
        enforce_portfolio_constraints,
    )
    from tradingagents.agents.utils.exchange_rules import validate_execution_decision

    def enforcer_node(state: AgentState):
        portfolio = get_config().get("portfolio_context") or {}
        decision = str(state.get("final_trade_decision") or "")
        corrected, raw_overrides = (
            enforce_portfolio_constraints(decision, portfolio)
            if portfolio else (decision, [])
        )
        execution_context = state.get("execution_context") or {}
        trade_date_close = state.get("trade_date_close")
        if trade_date_close is None:
            trade_date_close = execution_context.get("trade_date_close")
        corrected, execution_warnings = validate_execution_decision(
            corrected,
            trade_date_close=trade_date_close,
            segment=str(execution_context.get("segment") or ""),
            trade_date=str(state.get("trade_date") or ""),
        )
        if not raw_overrides and not execution_warnings:
            return {}

        notices = []
        overrides = []
        for item in raw_overrides:
            field = item["field"]
            proposed = item["proposed"]
            cap = item["cap"]
            if field == "max_single":
                notices.append(
                    "【组合约束修正】原建议仓位 "
                    f"{proposed:g}%，触发单票上限约束（{cap:g}%），"
                    f"系统已强制修正为 {cap:g}%。"
                )
                overrides.append({
                    "field": "position_weight",
                    "proposed": proposed,
                    "cap": cap,
                })
            else:
                notices.append(
                    f"【组合约束修正】{field} 原值 {proposed:g}%，系统修正为 {cap:g}%。"
                )
                overrides.append(item)
        new_decision = corrected
        if notices:
            new_decision += "\n\n" + "\n".join(notices)
        if execution_warnings:
            new_decision += "\n\n【执行规则校验】" + "；".join(
                warning["message"] for warning in execution_warnings
            )
        decision_blocks = dict(state.get("decision_blocks") or {})
        decision_blocks["final_trade_decision"] = new_decision
        orchestration = dict(state.get("orchestration") or {})
        existing_overrides = list(orchestration.get("constraint_overrides") or [])
        orchestration["constraint_overrides"] = existing_overrides + overrides
        orchestration["execution_rule_warnings"] = execution_warnings
        return {
            "final_trade_decision": new_decision,
            "decision_blocks": decision_blocks,
            "orchestration": orchestration,
            "sender": "ConstraintEnforcer",
        }

    return enforcer_node


def create_risk_finalize_node():
    def finalize_node(state: AgentState):
        orchestration = dict(state.get("orchestration", {}))
        risk_debate_state = dict(state.get("risk_debate_state", {}))
        semantic_prompt_slots = dict(
            state.get("semantic_prompt_slots", {})
            or state.get("screener_context", {}).get("semantic_prompt_slots", {})
            or {}
        )
        compression_notes = str(orchestration.get("compression_notes", ""))
        next_stage = determine_risk_debate_exit_stage(risk_debate_state, compression_notes)

        orchestration["stage"] = "risk_finalize"
        orchestration["phase"] = "risk"
        orchestration["next_stage"] = next_stage
        orchestration["compression_required"] = str(next_stage).endswith("_handoff")
        orchestration["final_route"] = next_stage
        if orchestration["compression_required"]:
            orchestration["final_reason"] = "risk_debate_exceeded_safe_context"
        elif str(compression_notes).strip():
            orchestration["final_reason"] = "existing_risk_handoff_available"
        else:
            orchestration["final_reason"] = "risk_debate_ready_for_portfolio"
        route_rule = str(orchestration.get("route_rule", "") or "risk_finalize")
        route_reason = str(orchestration.get("final_reason", "") or "risk_finalize")
        applied_controls = dict(orchestration.get("applied_controls", {}) or {})
        applied_controls.update(
            {
                "final_route": next_stage,
                "compression_required": orchestration["compression_required"],
            }
        )
        route_decision = dict(orchestration.get("route_decision", {}) or state.get("route_decision", {}) or {})
        semantic_trigger_audit = extract_semantic_trigger_audit(
            route_decision=route_decision,
            semantic_prompt_slots=semantic_prompt_slots,
            applied_controls=applied_controls,
        )
        orchestration["semantic_trigger_audit"] = semantic_trigger_audit

        event = build_orchestration_event(
            node_name="Finalize Risk Debate",
            orchestration=orchestration,
            context_estimate=len(str(risk_debate_state.get("history", ""))),
            route_rule=route_rule,
            route_reason=route_reason,
            applied_controls=applied_controls,
            semantic_trigger_audit=semantic_trigger_audit,
        )
        existing_trail = orchestration.get("event_trail")
        orchestration["event_trail"] = append_orchestration_event(existing_trail, event)

        return {
            "orchestration": orchestration,
            "sender": "Risk Finalizer",
        }

    return finalize_node


ORCHESTRATION_ROUTE_TARGETS = {
    "Route Research Phase": "Route Research Phase",
    "Bull Researcher": "Bull Researcher",
    "Trader": "Trader",
    "Aggressive Analyst": "Aggressive Analyst",
    "Finalize Risk Debate": "Finalize Risk Debate",
    "Portfolio Manager": "Portfolio Manager",
    "Summarize Analyst Phase": "Summarize Analyst Phase",
    "Summarize Research Phase": "Summarize Research Phase",
    "Summarize Trader Phase": "Summarize Trader Phase",
    "Summarize Risk Phase": "Summarize Risk Phase",
}


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""
    # 【职责】图构建器 - 负责将所有 Agent 连接成完整的 DAG

    def __init__(
        self,
        quick_thinking_llm: Any,      # 快速思考 LLM（用于简单推理）
        deep_thinking_llm: Any,        # 深度思考 LLM（用于复杂决策）
        tool_nodes: Dict[str, ToolNode],  # 工具节点字典
        bull_memory,                   # 多头记忆
        bear_memory,                   # 空头记忆
        trader_memory,                 # 交易员记忆
        invest_judge_memory,           # 投资裁判记忆
        portfolio_manager_memory,       # 组合经理记忆
        conditional_logic: ConditionalLogic,  # 条件路由逻辑
        skill_injector=None,           # Skill injector for decision-node skill injection
    ):
        """Initialize with required components."""
        # 【参数说明】
        #   • quick_thinking_llm: 简单任务用（如分析师报告）
        #   • deep_thinking_llm: 复杂任务用（如投资决策、风险评估）
        #   • tool_nodes: Analyst 调用的外部工具（市场数据、新闻等）
        #   • *_memory: 每个 Agent 的历史记忆（用于反思和学习）

        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.tool_nodes = tool_nodes
        self.bull_memory = bull_memory
        self.bear_memory = bear_memory
        self.trader_memory = trader_memory
        self.invest_judge_memory = invest_judge_memory
        self.portfolio_manager_memory = portfolio_manager_memory
        self.conditional_logic = conditional_logic
        self._skill_injector = skill_injector

    def setup_graph(
        self, selected_analysts=["market", "social", "news", "fundamentals"],
        checkpointer=None,
    ):
        """Set up and compile the agent workflow graph.

        Thin orchestrator since the Phase-4 B-group split: node creation and
        per-phase wiring live in the _create_*/_add_*/_wire_* methods below.

        Args:
            selected_analysts (list): analyst types to include
                ("market" / "social" / "news" / "fundamentals").
            checkpointer: optional LangGraph checkpointer enabling resume —
                completed super-steps are persisted under the run's thread_id
                so a crashed run continues from the last finished node
                instead of restarting (and re-billing) from scratch.
        """
        # ─────────────────────────────────────────────────────────────────
        # 第一步：校验 - 确保至少选择一个分析师
        # ─────────────────────────────────────────────────────────────────
        if len(selected_analysts) == 0:
            raise ValueError("Trading Agents Graph Setup Error: no analysts selected!")

        self.selected_analysts = list(selected_analysts)

        workflow = StateGraph(AgentState)
        agents = self._create_agent_nodes()
        self._add_orchestration_nodes(workflow)
        analyst_nodes, delete_nodes, tool_nodes = self._create_analyst_nodes(selected_analysts)
        self._add_nodes_to_graph(workflow, analyst_nodes, delete_nodes, tool_nodes, agents)
        self._wire_analyst_chain(workflow, selected_analysts)
        self._wire_research_debate(workflow)
        self._wire_orchestration_routing(workflow)
        self._wire_risk_debate(workflow)
        return workflow.compile(checkpointer=checkpointer)

    def _create_analyst_nodes(self, selected_analysts):
        """Build the per-analyst node/delete/tool dicts for selected analysts."""
        # 【初始化三个字典】
        analyst_nodes = {}    # 分析师节点
        delete_nodes = {}     # 消息清理节点（清除中间消息，避免状态膨胀）
        tool_nodes = {}       # 工具节点（对应每个分析师的数据源）

        # 【Market Analyst】市场技术分析师 - K线、均线、技术指标
        if "market" in selected_analysts:
            analyst_nodes["market"] = create_market_analyst(
                self.quick_thinking_llm
            )
            delete_nodes["market"] = create_msg_delete()  # 创建消息清理节点
            tool_nodes["market"] = self.tool_nodes["market"]

        # 【Social Analyst】社交媒体分析师 - Twitter、Reddit 情绪
        if "social" in selected_analysts:
            analyst_nodes["social"] = create_social_media_analyst(
                self.quick_thinking_llm
            )
            delete_nodes["social"] = create_msg_delete()
            tool_nodes["social"] = self.tool_nodes["social"]

        # 【News Analyst】新闻分析师 - 全球财经新闻
        if "news" in selected_analysts:
            analyst_nodes["news"] = create_news_analyst(
                self.quick_thinking_llm
            )
            delete_nodes["news"] = create_msg_delete()
            tool_nodes["news"] = self.tool_nodes["news"]

        # 【Fundamentals Analyst】基本面分析师 - 财务报表、估值
        if "fundamentals" in selected_analysts:
            analyst_nodes["fundamentals"] = create_fundamentals_analyst(
                self.quick_thinking_llm
            )
            delete_nodes["fundamentals"] = create_msg_delete()
            tool_nodes["fundamentals"] = self.tool_nodes["fundamentals"]

        return analyst_nodes, delete_nodes, tool_nodes

    def _create_agent_nodes(self):
        """Build research / trading / risk team nodes (memory + skill injected)."""
        # Create researcher and manager nodes
        bull_researcher_node = create_bull_researcher(
            self.quick_thinking_llm, self.bull_memory,
            skill_injector=self._skill_injector,
        )
        bear_researcher_node = create_bear_researcher(
            self.quick_thinking_llm, self.bear_memory,
            skill_injector=self._skill_injector,
        )
        research_manager_node = create_research_manager(
            self.deep_thinking_llm, self.invest_judge_memory,
            skill_injector=self._skill_injector,
        )
        trader_node = create_trader(
            self.quick_thinking_llm, self.trader_memory,
            skill_injector=self._skill_injector,
        )

        # ─────────────────────────────────────────────────────────────────
        # 第四步：创建风险管理层节点（Risk Management Team）
        #   • Aggressive Analyst: 激进派 - 追求高收益
        #   • Conservative Analyst: 保守派 - 控制风险
        #   • Neutral Analyst: 中立派 - 平衡观点
        #   • Portfolio Manager: 组合经理（深度思考，做出最终决策）
        # ─────────────────────────────────────────────────────────────────

        # Create risk analysis nodes
        aggressive_analyst = create_aggressive_debater(
            self.quick_thinking_llm,
            skill_injector=self._skill_injector,
        )
        neutral_analyst = create_neutral_debator(
            self.quick_thinking_llm,
            skill_injector=self._skill_injector,
        )
        conservative_analyst = create_conservative_debator(
            self.quick_thinking_llm,
            skill_injector=self._skill_injector,
        )
        portfolio_manager_node = create_portfolio_manager(
            self.deep_thinking_llm, self.portfolio_manager_memory,
            skill_injector=self._skill_injector,
        )

        return {
            "bull": bull_researcher_node,
            "bear": bear_researcher_node,
            "research_manager": research_manager_node,
            "trader": trader_node,
            "aggressive": aggressive_analyst,
            "neutral": neutral_analyst,
            "conservative": conservative_analyst,
            "portfolio_manager": portfolio_manager_node,
        }

    def _add_orchestration_nodes(self, workflow):
        """Register the phase routers, risk finalizer and handoff summarizers."""
        workflow.add_node("Route Research Phase", create_orchestration_router("analyst", "research"))
        workflow.add_node("Route Trader Phase", create_orchestration_router("research", "trader"))
        workflow.add_node("Route Risk Phase", create_orchestration_router("trader", "risk"))
        workflow.add_node("Route Portfolio Phase", create_orchestration_router("risk", "portfolio"))
        workflow.add_node("Finalize Risk Debate", create_risk_finalize_node())
        workflow.add_node("Summarize Analyst Phase", create_phase_handoff_node("analyst", "research", self.quick_thinking_llm))
        workflow.add_node("Summarize Research Phase", create_phase_handoff_node("research", "trader", self.quick_thinking_llm))
        workflow.add_node("Summarize Trader Phase", create_phase_handoff_node("trader", "risk", self.quick_thinking_llm))
        workflow.add_node("Summarize Risk Phase", create_phase_handoff_node("risk", "portfolio", self.quick_thinking_llm))


    def _add_nodes_to_graph(self, workflow, analyst_nodes, delete_nodes, tool_nodes, agents):
        """Register all team nodes onto the workflow."""
        # Add analyst nodes to the graph
        for analyst_type, node in analyst_nodes.items():
            # 分析师节点，如 "Market Analyst"
            workflow.add_node(f"{analyst_type.capitalize()} Analyst", node)
            # 消息清理节点，用于清除中间消息
            workflow.add_node(
                f"Msg Clear {analyst_type.capitalize()}", delete_nodes[analyst_type]
            )
            # 工具节点，用于获取外部数据
            workflow.add_node(f"tools_{analyst_type}", tool_nodes[analyst_type])

        # A4: pure-program evidence verification runs after the analyst
        # chain, before anything downstream consumes the reports.
        from tradingagents.agents.utils.evidence_verifier import run_verification
        workflow.add_node("Evidence Verifier", lambda state: run_verification(state))
        workflow.add_node("Human Gate", create_human_gate_node())
        workflow.add_node("ConstraintEnforcer", create_constraint_enforcer_node())

        workflow.add_node("Bull Researcher", agents["bull"])
        workflow.add_node("Bear Researcher", agents["bear"])
        workflow.add_node(
            "Debate Convergence Check",
            create_debate_convergence_node(self.quick_thinking_llm),
        )
        workflow.add_node("Research Manager", agents["research_manager"])
        workflow.add_node("Trader", agents["trader"])
        workflow.add_node("Aggressive Analyst", agents["aggressive"])
        workflow.add_node("Neutral Analyst", agents["neutral"])
        workflow.add_node("Conservative Analyst", agents["conservative"])
        workflow.add_node("Portfolio Manager", agents["portfolio_manager"])

    def _wire_analyst_chain(self, workflow, selected_analysts):
        """START -> analyst chain (tool loops) -> Route Research Phase."""
        first_analyst = selected_analysts[0]
        workflow.add_edge(START, f"{first_analyst.capitalize()} Analyst")

        for i, analyst_type in enumerate(selected_analysts):
            current_analyst = f"{analyst_type.capitalize()} Analyst"
            current_tools = f"tools_{analyst_type}"
            current_clear = f"Msg Clear {analyst_type.capitalize()}"

            workflow.add_conditional_edges(
                current_analyst,
                getattr(self.conditional_logic, f"should_continue_{analyst_type}"),
                [current_tools, current_clear],
            )
            workflow.add_edge(current_tools, current_analyst)

            if i < len(selected_analysts) - 1:
                next_analyst = f"{selected_analysts[i+1].capitalize()} Analyst"
                workflow.add_edge(current_clear, next_analyst)
            else:
                workflow.add_edge(current_clear, "Evidence Verifier")

        workflow.add_edge("Evidence Verifier", "Route Research Phase")

    def _wire_research_debate(self, workflow):
        """Bull/Bear debate loop with convergence-driven stopping (A2).

        Flow: Bull → (router) → Bear → Debate Convergence Check →
        (convergence router: continue with Bull | conclude with Research
        Manager). The convergence router reads the score the check node just
        wrote; missing/neutral score (3) falls back to round-count logic.
        """
        # Bull Researcher → (Bear Researcher 或 Research Manager)
        workflow.add_conditional_edges(
            "Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bear Researcher": "Bear Researcher",
                "Research Manager": "Research Manager",
            },
        )
        # Bear Researcher 完成一轮 → 收敛判定节点（A2）
        workflow.add_edge("Bear Researcher", "Debate Convergence Check")
        # 收敛判定 → (继续加轮 Bull 或 裁决 Research Manager)
        workflow.add_conditional_edges(
            "Debate Convergence Check",
            self.conditional_logic.should_continue_after_convergence,
            {
                "Bull Researcher": "Bull Researcher",
                "Research Manager": "Research Manager",
            },
        )

        # 【普通边】Research Manager → Trader
        workflow.add_edge("Research Manager", "Route Trader Phase")


    def _wire_orchestration_routing(self, workflow):
        """Route-* phase routers + handoff summarizer edges."""
        workflow.add_edge("Trader", "Route Risk Phase")
        for router in (
            "Route Research Phase",
            "Route Trader Phase",
            "Route Risk Phase",
            "Route Portfolio Phase",
        ):
            workflow.add_conditional_edges(
                router,
                self.conditional_logic.route_orchestration_stage,
                ORCHESTRATION_ROUTE_TARGETS,
            )

        # A5: gate sits after the risk debate, before the final decision —
        # all analysis cost is spent, the decision is not yet issued.
        workflow.add_edge("Finalize Risk Debate", "Human Gate")
        workflow.add_edge("Human Gate", "Route Portfolio Phase")
        workflow.add_edge("Summarize Analyst Phase", "Route Research Phase")
        workflow.add_edge("Summarize Research Phase", "Route Trader Phase")
        workflow.add_edge("Summarize Trader Phase", "Route Risk Phase")
        workflow.add_edge("Summarize Risk Phase", "Route Portfolio Phase")

    def _wire_risk_debate(self, workflow):
        """Three-way risk debate loop, Portfolio Manager -> END."""
        # Aggressive → (Conservative 或 Portfolio Manager)
        workflow.add_conditional_edges(
            "Aggressive Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Conservative Analyst": "Conservative Analyst",
                "Neutral Analyst": "Neutral Analyst",
                "Aggressive Analyst": "Aggressive Analyst",
                "Finalize Risk Debate": "Finalize Risk Debate",
            },
        )
        # Conservative → (Neutral 或 Portfolio Manager)
        workflow.add_conditional_edges(
            "Conservative Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Aggressive Analyst": "Aggressive Analyst",
                "Neutral Analyst": "Neutral Analyst",
                "Conservative Analyst": "Conservative Analyst",
                "Finalize Risk Debate": "Finalize Risk Debate",
            },
        )
        # Neutral → (Aggressive 或 Portfolio Manager)
        workflow.add_conditional_edges(
            "Neutral Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Aggressive Analyst": "Aggressive Analyst",
                "Conservative Analyst": "Conservative Analyst",
                "Neutral Analyst": "Neutral Analyst",
                "Finalize Risk Debate": "Finalize Risk Debate",
            },
        )

        # 【终点】Portfolio Manager → END（结束）
        # B3: hard clamp after the final decision, before completion.
        workflow.add_edge("Portfolio Manager", "ConstraintEnforcer")
        workflow.add_edge("ConstraintEnforcer", END)

