# TradingAgents/graph/conditional_logic.py
# =============================================================================
# 条件逻辑控制模块 - 负责决定工作流的走向
# =============================================================================
# 核心思想：每个"路由函数"检查当前状态(state)，返回一个字符串
#          这个字符串决定了下一个要执行哪个节点
# =============================================================================

from typing import Optional
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.agents.utils.state_helpers import (
    determine_risk_follow_up_speaker,
    has_full_risk_debate_coverage,
    normalize_next_stage,
)


class ConditionalLogic:
    """
    条件逻辑类 - 工作流的"交通枢纽"

    作用：决定 workflow 中条件边的走向
    原理：每个方法检查 state 中的某个字段，返回目标节点名称

    边缘情况保护：
    - 辩论轮次上限保护
    - 空状态保护
    - 未知 stage 降级处理
    """

    def __init__(
        self,
        max_debate_rounds: int = 1,
        max_risk_discuss_rounds: int = 1,
        max_recur_limit: int = 100,
        semantic_flow_controls: Optional[dict] = None,
    ):
        """
        初始化辩论轮次配置

        Args:
            max_debate_rounds: 多空辩论的最大轮数（默认1轮）
            max_risk_discuss_rounds: 风险辩论的最大轮数（默认1轮）
            max_recur_limit: 最大递归限制，用于计算安全上限

        实际效果：
            - 多空辩论：最多 2 * max_debate_rounds 次来回（Bull一次 + Bear一次 = 1轮）
            - 风险辩论：最多 3 * max_risk_discuss_rounds 次来回（Aggressive + Conservative + Neutral = 1轮）
        """
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds
        self.max_recur_limit = max_recur_limit
        self.semantic_flow_controls = semantic_flow_controls or {}

        self._debate_warning_threshold = 2 * max_debate_rounds + 2
        self._risk_warning_threshold = 3 * max_risk_discuss_rounds + 3

    @staticmethod
    def _get_route_decision(state: AgentState) -> dict:
        orchestration = state.get("orchestration", {}) or {}
        ticker_info = state.get("ticker_info", {}) or {}
        route_decision = dict(
            state.get("route_decision")
            or orchestration.get("route_decision")
            or ticker_info.get("route_decision")
            or {}
        )
        route_decision.setdefault("policy_role", "")
        route_decision.setdefault("capital_quality", "")
        route_decision.setdefault("conflict_tier", "")
        route_decision.setdefault("debate_rounds", "")
        route_decision.setdefault("debate_risk_weight", "")
        route_decision.setdefault("semantic_priority", 0)
        route_decision.setdefault("analyst_focus", [])
        route_decision.setdefault("selected_analysts", [])
        route_decision.setdefault("semantic_flow_controls", {})
        return route_decision

    def _resolve_debate_rounds(self, state: AgentState) -> int:
        route_decision = self._get_route_decision(state)
        controls = route_decision.get("semantic_flow_controls", {}) or self.semantic_flow_controls
        execution_profile = dict(
            state.get("orchestration", {}).get("semantic_execution_profile", {})
            or state.get("semantic_execution_profile", {})
            or {}
        )
        semantic_limit = controls.get("debate_round_limit")
        debate_rounds = semantic_limit if semantic_limit is not None else self.max_debate_rounds

        policy_role = str(route_decision.get("policy_role", "") or "")
        capital_quality = str(route_decision.get("capital_quality", "") or "")
        conflict_tier = str(route_decision.get("conflict_tier", "") or "")
        analyst_focus = route_decision.get("analyst_focus", []) or []
        semantic_priority = int(route_decision.get("semantic_priority", 0) or 0)

        if policy_role == "policy_top_stock" and capital_quality == "capital_quality_high" and conflict_tier in {"aligned", "moderate"}:
            debate_rounds += 1
        elif policy_role in {"policy_top_stock", "policy_core_member"} and capital_quality == "capital_quality_speculative":
            debate_rounds = max(1, debate_rounds - 1)
        elif policy_role == "policy_core_member" and capital_quality in {"capital_quality_mixed", "capital_quality_speculative"}:
            debate_rounds = max(1, debate_rounds - 1)
        if "concept_overlap" in analyst_focus:
            debate_rounds += 1
        if "heat_quality_gap" in analyst_focus and capital_quality in {"capital_quality_speculative", "capital_quality_mixed"}:
            debate_rounds = max(1, debate_rounds - 1)
        if semantic_priority <= -3:
            debate_rounds = max(1, debate_rounds - 1)
        if str(execution_profile.get("response_style", "")) == "concise_risk_first":
            debate_rounds = max(1, debate_rounds - 1)
        if bool(execution_profile.get("compress_to_highest_signal", False)):
            debate_rounds = max(1, debate_rounds - 1)

        return min(debate_rounds, self.max_recur_limit // 2 or debate_rounds)

    def _debate_route_reason(self, state: AgentState, debate_rounds: int) -> str:
        route_decision = self._get_route_decision(state)
        policy_role = str(route_decision.get("policy_role", "") or "")
        capital_quality = str(route_decision.get("capital_quality", "") or "")
        conflict_tier = str(route_decision.get("conflict_tier", "") or "")
        analyst_focus = route_decision.get("analyst_focus", []) or []
        if policy_role == "policy_top_stock" and capital_quality == "capital_quality_high":
            return f"top_stock_high_quality_debate_extension_{debate_rounds}"
        if capital_quality == "capital_quality_speculative":
            return f"speculative_flow_debate_shortened_{debate_rounds}"
        if "concept_overlap" in analyst_focus:
            return f"multi_concept_overlap_debate_extension_{debate_rounds}"
        if "heat_quality_gap" in analyst_focus:
            return f"heat_quality_gap_debate_hardening_{debate_rounds}"
        if conflict_tier in {"high", "severe"}:
            return f"high_conflict_debate_hardening_{debate_rounds}"
        if policy_role == "policy_core_member":
            return f"core_member_balanced_debate_{debate_rounds}"
        return f"standard_debate_{debate_rounds}"

    def _resolve_risk_rounds(self, state: AgentState) -> int:
        route_decision = self._get_route_decision(state)
        controls = route_decision.get("semantic_flow_controls", {}) or self.semantic_flow_controls
        execution_profile = dict(
            state.get("orchestration", {}).get("semantic_execution_profile", {})
            or state.get("semantic_execution_profile", {})
            or {}
        )
        semantic_limit = controls.get("risk_round_limit")
        risk_rounds = semantic_limit if semantic_limit is not None else self.max_risk_discuss_rounds

        policy_role = str(route_decision.get("policy_role", "") or "")
        capital_quality = str(route_decision.get("capital_quality", "") or "")
        conflict_tier = str(route_decision.get("conflict_tier", "") or "")
        analyst_focus = route_decision.get("analyst_focus", []) or []
        semantic_priority = int(route_decision.get("semantic_priority", 0) or 0)

        if capital_quality == "capital_quality_speculative" or conflict_tier in {"high", "severe"}:
            risk_rounds += 1
        elif policy_role == "policy_top_stock" and capital_quality in {"capital_quality_high", "capital_quality_persistent"}:
            risk_rounds = max(1, risk_rounds - 1)
        elif policy_role == "policy_core_member" and capital_quality == "capital_quality_mixed":
            risk_rounds = max(1, risk_rounds - 1)
        if "heat_quality_gap" in analyst_focus or "technical_risk" in analyst_focus:
            risk_rounds += 1
        if "concept_overlap" in analyst_focus and semantic_priority >= 4 and capital_quality in {"capital_quality_high", "capital_quality_persistent"}:
            risk_rounds = max(1, risk_rounds - 1)
        if bool(execution_profile.get("emphasize_risk", False)):
            risk_rounds += 1
        if str(execution_profile.get("conclusion_mode", "")) == "risk_first":
            risk_rounds += 1

        return min(risk_rounds, self.max_recur_limit // 3 or risk_rounds)

    def _risk_route_reason(self, state: AgentState, risk_rounds: int) -> str:
        route_decision = self._get_route_decision(state)
        policy_role = str(route_decision.get("policy_role", "") or "")
        capital_quality = str(route_decision.get("capital_quality", "") or "")
        conflict_tier = str(route_decision.get("conflict_tier", "") or "")
        analyst_focus = route_decision.get("analyst_focus", []) or []
        if capital_quality == "capital_quality_speculative":
            return f"speculative_risk_hardening_{risk_rounds}"
        if "heat_quality_gap" in analyst_focus:
            return f"heat_quality_gap_risk_extension_{risk_rounds}"
        if "technical_risk" in analyst_focus:
            return f"technical_structure_risk_extension_{risk_rounds}"
        if policy_role == "policy_top_stock" and capital_quality in {"capital_quality_high", "capital_quality_persistent"}:
            return f"top_stock_risk_fast_track_{risk_rounds}"
        if conflict_tier in {"high", "severe"}:
            return f"high_conflict_risk_extension_{risk_rounds}"
        return f"standard_risk_{risk_rounds}"

    # =========================================================================
    # 分析师团队的条件路由（4个方法，逻辑完全相同，只是节点名称不同）
    # =========================================================================

    def should_continue_market(self, state: AgentState):
        """
        【Market Analyst 的路由函数】
        
        判断逻辑：
            最后一条消息是否调用了工具？
            ├── 是（tool_calls 非空）→ 返回 "tools_market"（继续获取数据）
            └── 否（tool_calls 为空）→ 返回 "Msg Clear Market"（清理消息，进入下一个分析师）
        
        为什么这样设计？
            LangChain/LangGraph 的 LLM 在调用工具时：
            1. LLM 判断需要数据 → 调用 tool_call → 路由到 tools_market
            2. 工具执行完毕 → LLM 收到数据 → 不再调用 tool_call → 路由到清理节点
        """
        messages = state["messages"]              # 获取所有消息历史
        last_message = messages[-1]              # 取最后一条消息
        if last_message.tool_calls:              # 检查是否调用了工具
            return "tools_market"                # 需要工具 → 去数据获取节点
        return "Msg Clear Market"                 # 不需要工具 → 清理消息

    def should_continue_social(self, state: AgentState):
        """
        【Social Analyst 的路由函数】
        
        逻辑同上，只是针对社交媒体分析师
        """
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_social"
        return "Msg Clear Social"

    def should_continue_news(self, state: AgentState):
        """
        【News Analyst 的路由函数】
        
        逻辑同上，只是针对新闻分析师
        """
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_news"
        return "Msg Clear News"

    def should_continue_fundamentals(self, state: AgentState):
        """
        【Fundamentals Analyst 的路由函数】
        
        逻辑同上，只是针对基本面分析师
        """
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_fundamentals"
        return "Msg Clear Fundamentals"

    def route_orchestration_stage(self, state: AgentState) -> str:
        """
        【编排阶段路由函数】

        根据 orchestration 状态决定下一步节点。

        边缘情况保护：
            - 缺少 orchestration 字段时使用默认值
            - 未知 phase/stage 时有降级策略
            - completed 状态强制结束
        """
        orchestration = state.get("orchestration", {})
        next_stage = normalize_next_stage(
            orchestration.get("next_stage") or orchestration.get("phase") or orchestration.get("stage"),
            "research",
        )
        completed = orchestration.get("completed", False)
        compression_required = orchestration.get("compression_required", False)

        if completed:
            return "Portfolio Manager"

        if compression_required:
            phase = orchestration.get("phase", "")
            phase_to_summary = {
                "analyst": "Summarize Analyst Phase",
                "research": "Summarize Research Phase",
                "trader": "Summarize Trader Phase",
                "risk": "Summarize Risk Phase",
            }
            return phase_to_summary.get(phase, "Summarize Analyst Phase")

        stage_map = {
            "analysis": "Bull Researcher",
            "analyst": "Bull Researcher",
            "research": "Bull Researcher",
            "trader": "Trader",
            "risk": "Aggressive Analyst",
            "risk_finalize": "Finalize Risk Debate",
            "portfolio": "Portfolio Manager",
            "completed": "Portfolio Manager",
        }
        return stage_map.get(next_stage, "Bull Researcher")

    # =========================================================================
    # 研究团队辩论路由（多空双方你来我往）
    # =========================================================================

    def should_continue_debate(self, state: AgentState) -> str:
        """
        【Bull/Bear 辩论的路由函数】

        核心机制：多方辩论循环

        辩论流程：
            Bull Researcher（看多） ◄──► Bear Researcher（看空）

        辩论状态 state["investment_debate_state"] 包含：
            - count: 已辩论的轮数
            - current_response: 当前回复内容

        判断逻辑：
            1️⃣ 是否达到辩论上限？
               └── 是 → 返回 "Research Manager"（结束辩论，进入决策）

            2️⃣ 最后是谁发言？
               ├── Bull 发言 → 返回 "Bear Researcher"（让空头反驳）
               └── Bear 发言 → 返回 "Bull Researcher"（让多头反驳）

        轮次计算：
            max_debate_rounds = 1 时
            count >= 2*1 = 2 时结束

            辩论序列示例（max=1）：
                1. Bull 发言 → count=1 → 返回 Bear
                2. Bear 发言 → count=2 → >= 2 成立 → 返回 Research Manager

            辩论序列示例（max=2）：
                1. Bull 发言 → count=1
                2. Bear 发言 → count=2
                3. Bull 发言 → count=3
                4. Bear 发言 → count=4 → >= 4 成立 → 结束

        边缘情况保护：
            - count < 0 时视为 0
            - 异常高的 count 值直接结束辩论
        """
        debate_state = state.get("investment_debate_state", {})
        count = max(0, debate_state.get("count", 0))
        current_response = str(debate_state.get("current_response", ""))

        debate_rounds = self._resolve_debate_rounds(state)
        route_reason = self._debate_route_reason(state, debate_rounds)
        debate_limit = 2 * debate_rounds
        hard_limit = min(debate_limit + 10, self.max_recur_limit)
        route_decision = self._get_route_decision(state)
        applied_controls = {
            **dict(route_decision.get("semantic_flow_controls", {}) or self.semantic_flow_controls),
            "applied_debate_round_limit": debate_rounds,
        }
        state.setdefault("orchestration", {})["route_rule"] = route_reason
        state["orchestration"]["route_reason"] = route_reason
        state["orchestration"]["applied_controls"] = applied_controls

        if count >= debate_limit or count >= hard_limit:
            return "Research Manager"

        latest_speaker = str(debate_state.get("latest_speaker", ""))
        if latest_speaker.startswith("Bull"):
            return "Bear Researcher"
        if latest_speaker.startswith("Bear"):
            return "Bull Researcher"

        # Fallback: Bull goes first if latest_speaker is unknown/empty
        return "Bull Researcher"

    # =========================================================================
    # 风险管理辩论路由（三方循环）
    # =========================================================================

    def should_continue_risk_analysis(self, state: AgentState) -> str:
        """
        【风险辩论的路由函数】

        核心机制：三方辩论循环

        辩论流程：
            Aggressive Analyst（激进派）
                    ▲
                    │
                    ▼
            Conservative Analyst（保守派）
                    ▲
                    │
                    ▼
            Neutral Analyst（中立派）
                    │
                    ▼
            （回到 Aggressive，形成三角循环）

        辩论状态 state["risk_debate_state"] 包含：
            - count: 已辩论的轮数
            - latest_speaker: 最后发言的是谁

        判断逻辑：
            1️⃣ 是否达到辩论上限？
               └── 是 → 检查是否有 full coverage
                    ├── 有 full coverage → 返回 "Finalize Risk Debate"
                    └── 没有 full coverage → 继续辩论直到有 full coverage

            2️⃣ 最后是谁发言？
               ├── Aggressive 发言 → 返回 "Conservative"（让保守派来压制）
               ├── Conservative 发言 → 返回 "Neutral"（让中立派来平衡）
               └── Neutral 发言 → 返回 "Aggressive"（让激进派来挑战）

        轮次计算：
            max_risk_discuss_rounds = 1 时
            count >= 3*1 = 3 时视为达到上限

            辩论序列示例（max=1）：
                1. Aggressive 发言 → count=1 → 返回 Conservative
                2. Conservative 发言 → count=2 → 返回 Neutral
                3. Neutral 发言 → count=3 → >= 3 成立
                   - 如果 full coverage → 结束
                   - 如果缺某个声音 → 继续

        边缘情况保护：
            - count < 0 时视为 0
            - 异常高的 count 值直接结束辩论
        """
        risk_debate_state = state.get("risk_debate_state", {})
        count = max(0, risk_debate_state.get("count", 0))

        risk_rounds = self._resolve_risk_rounds(state)
        route_reason = self._risk_route_reason(state, risk_rounds)
        risk_limit = 3 * risk_rounds
        hard_limit = min(risk_limit + 10, self.max_recur_limit)

        full_coverage = has_full_risk_debate_coverage(risk_debate_state)
        force_risk_review = bool(self.semantic_flow_controls.get("force_risk_review", False))
        risk_hardening = bool(self.semantic_flow_controls.get("risk_hardening", False))
        route_decision = self._get_route_decision(state)
        capital_quality = str(route_decision.get("capital_quality", "") or "")
        policy_role = str(route_decision.get("policy_role", "") or "")
        applied_controls = {
            **dict(route_decision.get("semantic_flow_controls", {}) or self.semantic_flow_controls),
            "applied_risk_round_limit": risk_rounds,
        }
        state.setdefault("orchestration", {})["route_rule"] = route_reason
        state["orchestration"]["route_reason"] = route_reason
        state["orchestration"]["applied_controls"] = applied_controls

        if policy_role == "policy_top_stock" and capital_quality == "capital_quality_speculative":
            if count >= 3:
                if str(risk_debate_state.get("latest_speaker", "") or "") != "Conservative":
                    return "Conservative Analyst"
                return "Finalize Risk Debate"

        if count >= hard_limit:
            return "Finalize Risk Debate"

        if (
            policy_role == "policy_top_stock"
            and capital_quality == "capital_quality_speculative"
            and count >= risk_limit
        ):
            latest_speaker = str(risk_debate_state.get("latest_speaker", "") or "")
            if latest_speaker != "Conservative":
                return "Conservative Analyst"
            return "Finalize Risk Debate"

        if policy_role == "policy_top_stock" and capital_quality == "capital_quality_high" and full_coverage:
            if count >= risk_limit:
                return "Finalize Risk Debate"
            if current_speaker := str(risk_debate_state.get("latest_speaker", "") or ""):
                if current_speaker == "Aggressive":
                    return "Conservative Analyst"

        if count >= risk_limit and full_coverage and not force_risk_review:
            return "Finalize Risk Debate"
        if count >= risk_limit and full_coverage and force_risk_review and risk_hardening:
            latest_speaker = str(risk_debate_state.get("latest_speaker", "") or "")
            if latest_speaker != "Conservative":
                return "Conservative Analyst"
            return "Finalize Risk Debate"

        return determine_risk_follow_up_speaker(risk_debate_state)
