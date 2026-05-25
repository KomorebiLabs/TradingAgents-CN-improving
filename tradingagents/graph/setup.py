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

from tradingagents.agents import *
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.agents.utils.state_helpers import (
    build_orchestration_event,
    append_orchestration_event,
    determine_risk_debate_exit_stage,
    extract_semantic_trigger_audit,
)

from .conditional_logic import ConditionalLogic


def create_orchestration_router(source_phase: str, default_next_stage: str):
    def router_node(state: AgentState):
        orchestration = dict(state.get("orchestration", {}))
        semantic_prompt_slots = dict(
            state.get("semantic_prompt_slots", {})
            or state.get("screener_context", {}).get("semantic_prompt_slots", {})
            or {}
        )
        threshold = int(orchestration.get("compression_threshold_tokens", 18000))
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
                "compression_threshold_tokens": threshold,
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
        self, selected_analysts=["market", "social", "news", "fundamentals"]
    ):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include. Options are:
                - "market": Market analyst
                - "social": Social media analyst
                - "news": News analyst
                - "fundamentals": Fundamentals analyst
        """
        # 【图构建入口】这是整个 DAG 的核心方法

        # ─────────────────────────────────────────────────────────────────
        # 第一步：校验 - 确保至少选择一个分析师
        # ─────────────────────────────────────────────────────────────────
        if len(selected_analysts) == 0:
            raise ValueError("Trading Agents Graph Setup Error: no analysts selected!")

        self.selected_analysts = list(selected_analysts)

        # ─────────────────────────────────────────────────────────────────
        # 第二步：创建分析师节点（Analyst Team）
        #   注意：这是一个可配置的模块，用户可以选择启用哪些分析师
        # ─────────────────────────────────────────────────────────────────

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

        # ─────────────────────────────────────────────────────────────────
        # 第三步：创建研究团队节点（Research Team）
        #   • Bull Researcher: 看多派研究员（有记忆）
        #   • Bear Researcher: 看空派研究员（有记忆）
        #   • Research Manager: 研究经理（深度思考，裁决多空）
        # ─────────────────────────────────────────────────────────────────

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
        neutral_analyst = create_neutral_debater(
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

        # ─────────────────────────────────────────────────────────────────
        # 第五步：构建 DAG - 创建 StateGraph 实例
        #   【LangGraph 核心概念】
        #   • StateGraph(AgentState): 基于 AgentState 的状态图
        #   • workflow.add_node(): 添加节点
        #   • workflow.add_edge(): 添加普通边（固定跳转）
        #   • workflow.add_conditional_edges(): 添加条件边（根据状态动态跳转）
        # ─────────────────────────────────────────────────────────────────

        # Create workflow
        workflow = StateGraph(AgentState)
        workflow.add_node("Route Research Phase", create_orchestration_router("analyst", "research"))
        workflow.add_node("Route Trader Phase", create_orchestration_router("research", "trader"))
        workflow.add_node("Route Risk Phase", create_orchestration_router("trader", "risk"))
        workflow.add_node("Route Portfolio Phase", create_orchestration_router("risk", "portfolio"))
        workflow.add_node("Finalize Risk Debate", create_risk_finalize_node())
        workflow.add_node("Summarize Analyst Phase", create_phase_handoff_node("analyst", "research", self.quick_thinking_llm))
        workflow.add_node("Summarize Research Phase", create_phase_handoff_node("research", "trader", self.quick_thinking_llm))
        workflow.add_node("Summarize Trader Phase", create_phase_handoff_node("trader", "risk", self.quick_thinking_llm))
        workflow.add_node("Summarize Risk Phase", create_phase_handoff_node("risk", "portfolio", self.quick_thinking_llm))

        # ─────────────────────────────────────────────────────────────────
        # 第六步：添加节点到图中
        #   【节点命名规范】
        #   • Analyst 节点: "Market Analyst", "Social Analyst" 等
        #   • 工具节点: "tools_market", "tools_social" 等
        #   • 清理节点: "Msg Clear Market", "Msg Clear Social" 等
        #   • 辩论节点: "Bull Researcher", "Bear Researcher" 等
        # ─────────────────────────────────────────────────────────────────

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

        # Add other nodes
        # 研究团队节点
        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        # 交易员节点
        workflow.add_node("Trader", trader_node)
        # 风险管理层节点
        workflow.add_node("Aggressive Analyst", aggressive_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Conservative Analyst", conservative_analyst)
        workflow.add_node("Portfolio Manager", portfolio_manager_node)

        # ─────────────────────────────────────────────────────────────────
        # 第七步：定义边（Edges）- 连接节点
        # ─────────────────────────────────────────────────────────────────

        # Define edges
        # 【起点】从 START 到第一个分析师
        # Start with the first analyst
        first_analyst = selected_analysts[0]
        workflow.add_edge(START, f"{first_analyst.capitalize()} Analyst")

        # 【Analyst 链】按顺序连接各个分析师
        # Connect analysts in sequence

        # enumerate() 返回 ：(索引, 值) 的元组
        
        for i, analyst_type in enumerate(selected_analysts):
            current_analyst = f"{analyst_type.capitalize()} Analyst"
            current_tools = f"tools_{analyst_type}"
            current_clear = f"Msg Clear {analyst_type.capitalize()}"

            # 【条件边】分析师 → 工具 或 清理节点
            # Add conditional edges for current analyst
            # 判断逻辑：如果 last_message 有 tool_calls，去工具节点；否则去清理节点
            workflow.add_conditional_edges(
                current_analyst,
                getattr(self.conditional_logic, f"should_continue_{analyst_type}"),
                [current_tools, current_clear],
            )
            # 【普通边】工具节点 → 分析师（获取数据后继续分析）
            workflow.add_edge(current_tools, current_analyst)

            # 【普通边】连接下一个分析师
            # Connect to next analyst or to Bull Researcher if this is the last analyst
            if i < len(selected_analysts) - 1:
                next_analyst = f"{selected_analysts[i+1].capitalize()} Analyst"
                workflow.add_edge(current_clear, next_analyst)
            else:
                # 最后一个分析师 → 进入研究团队
                workflow.add_edge(current_clear, "Route Research Phase")

            """
                    ┌─────────────────────────┐
                    │   Market Analyst         │
                    │   (分析完成)             │
                    └───────────┬─────────────┘
                                │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
          should_continue_market()     should_continue_market()
                    │                     │
              返回 "market"             返回 "clear"
                    │                     │
                    ▼                     ▼
           ┌──────────────┐      ┌──────────────┐
           │ tools_market │      │Msg Clear     │
           │              │      │Market        │
           └──────┬───────┘      └──────┬───────┘
                  │                      │
                  │ 返回 Market Analyst  │ 流向下一个分析师
                  │ (继续分析)           │
                  ▼                      ▼
           ┌──────────────┐      ┌──────────────┐
           │   （回到）     │      │ Social Analyst│
           │Market Analyst │      │  (下一个节点) │
           └──────────────┘      └──────────────┘

==================================================================================

                                    ┌────────────────────────────────────────┐
                                    │  selected_analysts = ["market", "social"]
                                    └────────────────────────────────────────┘
                                                      │
                                                      ▼
                                    ┌────────────────────────────────────┐
                                    │ i=0, analyst_type="market"          │
                                    └────────────────────────────────────┘
                                                      │
                                                      ▼
  START ──► "Market Analyst" ──► should_continue_market()
                                           │
                         ┌─────────────────┴─────────────────┐
                         │                                   │
                    有 tool_calls                          没有
                         │                                   │
                         ▼                                   ▼
              ┌─────────────────┐              ┌─────────────────────┐
              │   tools_market  │              │   Msg Clear Market  │
              └────────┬────────┘              └──────────┬──────────┘
                       │                                  │
                       │ 回到                              │ 流向
                       ▼                                  ▼
              ┌─────────────────┐              ┌─────────────────────┐
              │ Market Analyst  │              │  Social Analyst     │
              │ (继续分析)       │              │  (下一个分析师)       │
              └────────┬────────┘              └──────────┬──────────┘
                       │                                  │
                       └──────► (循环直到不需要工具)        │
                                                          │
                                                          ▼ i=1, analyst_type="social"
                                    ┌────────────────────────────────────┐
                                    │ should_continue_social()           │
                                    │ 最后判断：这是最后一个吗？           │
                                    │ i=1, len=2, 1 < 1? → False         │
                                    │ 所以不是最后一个...                  │
                                    └────────────────────────────────────┘
                                                          │
                                                          ▼
                                              ┌─────────────────────┐
                                              │ Msg Clear Social    │
                                              │ (最后一个分析师)     │
                                              └──────────┬──────────┘
                                                         │
                                                         ▼
                                              ┌─────────────────────┐
                                              │  Bull Researcher    │
                                              │  (进入研究团队)      │
                                              └─────────────────────┘

            """


        # ─────────────────────────────────────────────────────────────────
        # 第八步：定义研究团队的辩论边（多空辩论循环）
        # ─────────────────────────────────────────────────────────────────

        # 【多空辩论条件边】
        # Add remaining edges
        # Bull Researcher → (Bear Researcher 或 Research Manager)
        workflow.add_conditional_edges(
            "Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bear Researcher": "Bear Researcher",
                "Research Manager": "Research Manager",
            },
        )
        # Bear Researcher → (Bull Researcher 或 Research Manager)
        workflow.add_conditional_edges(
            "Bear Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bull Researcher": "Bull Researcher",
                "Research Manager": "Research Manager",
            },
        )

        # 【普通边】Research Manager → Trader
        workflow.add_edge("Research Manager", "Route Trader Phase")

        """
            ┌────────────────────────────────────────────────────────────────┐
            │                    Bull/Bear 辩论循环                          │
            │                                                                │
            │              ┌─────────────────────────────────┐              │
            │              │    should_continue_debate()     │              │
            │              │        返回值决定去向            │              │
            │              └─────────────┬───────────────────┘              │
            │                            │                                  │
            │        ┌───────────────────┴───────────────────┐              │
            │        │                                       │              │
            │        ▼                                       ▼              │
            │  ┌─────────────┐                       ┌─────────────┐        │
            │  │   返回      │                       │   返回      │        │
            │  │ "debate"   │                        │ "finished" │         │
            │  └──────┬──────┘                       └──────┬──────┘        │
            │         │                                     │              │
            │         ▼                                     ▼              │
            │  ┌─────────────┐                       ┌─────────────┐        │
            │  │  Bear      │ ◄────────────────────► │  Research   │        │
            │  │  Researcher│      继续辩论          │  Manager    │        │
            │  └──────┬─────┘                       └──────┬──────┘        │
            │         │                                     │              │
            │         └──────► ◄─────────────────────► ◄───┘              │
            │                                                                │
            └────────────────────────────────────────────────────────────────┘



        """

        # ─────────────────────────────────────────────────────────────────
        # 第九步：定义风险管理团队的辩论边（三方循环）
        # ─────────────────────────────────────────────────────────────────

        # 【普通边】Trader → Aggressive Analyst（开始风险辩论）
        workflow.add_edge("Trader", "Route Risk Phase")

        workflow.add_conditional_edges(
            "Route Research Phase",
            self.conditional_logic.route_orchestration_stage,
            {
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
            },
        )
        workflow.add_conditional_edges(
            "Route Trader Phase",
            self.conditional_logic.route_orchestration_stage,
            {
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
            },
        )
        workflow.add_conditional_edges(
            "Route Risk Phase",
            self.conditional_logic.route_orchestration_stage,
            {
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
            },
        )
        workflow.add_conditional_edges(
            "Route Portfolio Phase",
            self.conditional_logic.route_orchestration_stage,
            {
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
            },
        )

        workflow.add_edge("Finalize Risk Debate", "Route Portfolio Phase")
        workflow.add_edge("Summarize Analyst Phase", "Route Research Phase")
        workflow.add_edge("Summarize Research Phase", "Route Trader Phase")
        workflow.add_edge("Summarize Trader Phase", "Route Risk Phase")
        workflow.add_edge("Summarize Risk Phase", "Route Portfolio Phase")

        # 【三方辩论条件边】
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
        workflow.add_edge("Portfolio Manager", END)

        # ─────────────────────────────────────────────────────────────────
        # 第十步：编译 DAG - 生成可执行的工作流
        # ─────────────────────────────────────────────────────────────────

        # Compile and return
        return workflow.compile()
        # 【返回值】CompiledGraph 对象，可用于 graph.invoke() 或 graph.stream()
