from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

from tradingagents.screener.config import DeepAnalyzerConfig, build_graph_config
from tradingagents.screener.models import DeepAnalysisResult, SignalCard
from tradingagents.ui.screener_console import console
from tradingagents.agents.utils.agent_utils import (
    build_semantic_execution_profile,
    derive_semantic_flow_controls,
    validate_semantic_prompt_slots,
)
from tradingagents.agents.utils.state_helpers import extract_semantic_trigger_audit

try:
    from tradingagents.graph.trading_graph import TradingAgentsGraph
except Exception:  # pragma: no cover - graph deps may be unavailable in local test env
    TradingAgentsGraph = None


SEMANTIC_PROMPT_SCHEMA_NAME = "screener.semantic_prompt_slots"
SEMANTIC_PROMPT_SCHEMA_VERSION = "1.0"


class DeepAnalyzer:
    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}
        deep_config = self.config.get("deep_analyzer", {})
        self.deep_config = DeepAnalyzerConfig(
            max_stocks=deep_config.get("max_stocks", 3),
            delay_between_stocks=deep_config.get("delay_between_stocks", 2.0),
            retry_on_failure=deep_config.get("retry_on_failure", True),
            max_retries=deep_config.get("max_retries", 1),
        )
        self.config_warnings: List[str] = []
        # H3 FIX: extract enable_real_deep_analysis from config (with env var fallback)
        self._enable_real_analysis = self._resolve_real_analysis_flag()

        # H3 可观测性：初始化 CostTracker 和 TokenCountingCallback
        from tradingagents.harness.engine import CostTracker, TokenCountingCallback
        self._token_tracker = CostTracker()
        self._token_callback = TokenCountingCallback(self._token_tracker)

    def _resolve_real_analysis_flag(self) -> bool:
        """Resolve nested explicit config, legacy config, env, then default."""
        import os
        deep_config = self.config.get("deep_analyzer", {})
        if "enable_real_deep_analysis" in deep_config:
            return bool(deep_config["enable_real_deep_analysis"])
        if "enable_real_deep_analysis" in self.config:
            self.config_warnings.append(
                "[DEPRECATED] 顶层 enable_real_deep_analysis 已废弃，请迁移到 deep_analyzer.enable_real_deep_analysis"
            )
            return bool(self.config["enable_real_deep_analysis"])
        env_val = os.environ.get("TRADINGAGENTS_DEEP_ANALYSIS_ENABLED", "").strip().lower()
        if env_val in ("true", "1", "yes"):
            return True
        if env_val in ("false", "0", "no"):
            return False
        return True

    def analyze(self, signal_card: SignalCard, trade_date: str) -> DeepAnalysisResult:
        started = datetime.now()
        try:
            semantic_context = self._build_semantic_context(signal_card)
            route_decision = self._build_route_decision(signal_card, semantic_context)
            execution_profile = build_semantic_execution_profile(
                {
                    "semantic_prompt_slots": semantic_context["prompt_slots"],
                    "route_decision": route_decision,
                    "orchestration": {
                        "semantic_trigger_audit": extract_semantic_trigger_audit(
                            route_decision=route_decision,
                            semantic_prompt_slots=semantic_context["prompt_slots"],
                            applied_controls=route_decision.get("semantic_flow_controls", {}),
                        )
                    },
                },
                "portfolio_manager",
            )
        except Exception as exc:
            return self._failed_result(signal_card, started, str(exc))
        if not self._enable_real_analysis:
            return self._dry_run(
                signal_card,
                trade_date,
                started,
                reason="real_deep_analysis_disabled",
                semantic_context=semantic_context,
                route_decision=route_decision,
                execution_profile=execution_profile,
            )

        try:
            if TradingAgentsGraph is None:
                raise RuntimeError("TradingAgentsGraph unavailable")
            graph_config = build_graph_config(self.config.get("graph_overrides"))
            graph_config["company_of_interest"] = signal_card.ticker
            graph_config["semantic_flow_controls"] = route_decision["semantic_flow_controls"]
            graph_config["semantic_execution_profile"] = execution_profile
            graph_config["screener_context"] = {
                "trigger_reason": signal_card.trigger_reason,
                "strategy_sources": signal_card.strategy_sources,
                "screening_score": signal_card.screening_score,
                "initial_confidence": signal_card.initial_confidence,
                "risk_flags": signal_card.risk_flags,
                "sector_tags": signal_card.sector_tags,
                "concept_tags": signal_card.concept_tags,
                "semantic_context": semantic_context,
                "semantic_prompt_slots": semantic_context["prompt_slots"],
                "route_decision": route_decision,
                "selected_analysts": route_decision["selected_analysts"],
                "semantic_flow_controls": route_decision["semantic_flow_controls"],
                "semantic_execution_profile": execution_profile,
            }

            ta = TradingAgentsGraph(debug=False, config=graph_config, callbacks=[self._token_callback])
            final_state, decision = ta.propagate(signal_card.ticker, trade_date)
            elapsed = (datetime.now() - started).total_seconds()
            return DeepAnalysisResult(
                signal_card=signal_card,
                success=True,
                execution_status="GRAPH_COMPLETED",
                final_decision=decision,
                elapsed_seconds=elapsed,
                token_usage={
                    "input_tokens": self._token_tracker.total.input_tokens,
                    "output_tokens": self._token_tracker.total.output_tokens,
                    "total_tokens": self._token_tracker.total.total_tokens,
                },
                final_state_summary={
                    "analysis_mode": "graph",
                    "config_warnings": list(self.config_warnings),
                    "route_decision": route_decision,
                    "fallback_used": False,
                    "fallback_reason": "",
                    "graph_config_snapshot": self._build_graph_config_snapshot(graph_config),
                    "company_of_interest": final_state.get("company_of_interest", signal_card.ticker),
                    "final_trade_decision": final_state.get("final_trade_decision", ""),
                    "semantic_context": semantic_context,
                    "semantic_context_summary": semantic_context["summary"],
                    "semantic_prompt_slots": semantic_context["prompt_slots"],
                    "semantic_execution_profile": final_state.get("orchestration", {}).get("semantic_execution_profile", execution_profile),
                    "semantic_trigger_audit": final_state.get("orchestration", {}).get("semantic_trigger_audit", {}),
                    "semantic_route_audit_trail": final_state.get("orchestration", {}).get("route_summary", {}).get("semantic_route_audit_trail", []),
                },
            )
        except Exception as exc:
            try:
                return self._dry_run(
                    signal_card,
                    trade_date,
                    started,
                    reason=str(exc),
                    semantic_context=semantic_context,
                    route_decision=route_decision,
                    execution_profile=execution_profile,
                    fallback_used=True,
                )
            except Exception as fallback_exc:
                return self._failed_result(
                    signal_card,
                    started,
                    f"graph_error={exc}; fallback_error={fallback_exc}",
                )

    def analyze_top_candidates(self, candidates: List[SignalCard], trade_date: str) -> List[DeepAnalysisResult]:
        limit = min(len(candidates), self.deep_config.max_stocks)
        if limit == 0:
            console.print("[yellow]  DeepAnalysis: no candidates to analyze[/yellow]")
            return []
        results = []
        for i, card in enumerate(candidates[:limit], 1):
            console.print(
                f"[cyan]  Analyzing[/cyan] [white]{i}/{limit}[/white]  "
                f"[bold white]{card.ticker}[/bold white]  "
                f"[dim]score={card.screening_score:.1f}[/dim]",
                end="\r",
            )
            results.append(self.analyze(card, trade_date))
        console.print()
        status_counts = Counter(result.execution_status for result in results)
        status_summary = ", ".join(
            f"{status}={status_counts.get(status, 0)}"
            for status in (
                "GRAPH_COMPLETED",
                "DRY_RUN_REQUESTED",
                "FALLBACK_COMPLETED",
                "FAILED",
            )
            if status_counts.get(status, 0)
        )
        console.print(
            f"[green][OK] DeepAnalysis done[/green]  "
            f"[cyan]{len(results)}/{limit}[/cyan] results  [dim]{status_summary}[/dim]"
        )
        return results

    def _dry_run(
        self,
        signal_card: SignalCard,
        trade_date: str,
        started: datetime,
        reason: str,
        semantic_context: Dict[str, Any],
        route_decision: Dict[str, Any],
        execution_profile: Dict[str, Any],
        fallback_used: bool = False,
    ) -> DeepAnalysisResult:
        elapsed = (datetime.now() - started).total_seconds()
        decision = (
            f"DRY_RUN: {signal_card.ticker} passed screener with score {signal_card.screening_score:.1f}. "
            f"Primary signals: {', '.join(signal_card.strategy_sources)}. "
            f"Semantic context: {semantic_context['summary']}."
        )
        return DeepAnalysisResult(
            signal_card=signal_card,
            success=True,
            execution_status="FALLBACK_COMPLETED" if fallback_used else "DRY_RUN_REQUESTED",
            final_decision=decision,
            elapsed_seconds=elapsed,
            token_usage={
                "input_tokens": self._token_tracker.total.input_tokens,
                "output_tokens": self._token_tracker.total.output_tokens,
                "total_tokens": self._token_tracker.total.total_tokens,
            },
            final_state_summary={
                "analysis_mode": "fallback" if fallback_used else "dry_run_requested",
                "config_warnings": list(self.config_warnings),
                "reason": reason,
                "route_decision": route_decision,
                "fallback_used": fallback_used,
                "fallback_reason": reason if fallback_used else "",
                "graph_config_snapshot": {},
                "trade_date": trade_date,
                "semantic_context": semantic_context,
                "semantic_context_summary": semantic_context["summary"],
                "semantic_prompt_slots": semantic_context["prompt_slots"],
                "semantic_execution_profile": execution_profile,
                "semantic_trigger_audit": extract_semantic_trigger_audit(
                    route_decision=route_decision,
                    semantic_prompt_slots=semantic_context["prompt_slots"],
                    applied_controls=route_decision.get("semantic_flow_controls", {}),
                ),
                "semantic_route_audit_trail": [],
            },
        )

    def _failed_result(
        self,
        signal_card: SignalCard,
        started: datetime,
        error: str,
    ) -> DeepAnalysisResult:
        return DeepAnalysisResult(
            signal_card=signal_card,
            success=False,
            execution_status="FAILED",
            elapsed_seconds=(datetime.now() - started).total_seconds(),
            error=error,
            final_state_summary={
                "analysis_mode": "failed",
                "fallback_used": False,
                "fallback_reason": "",
                "config_warnings": list(self.config_warnings),
            },
        )

    @staticmethod
    def _build_semantic_context(signal_card: SignalCard) -> Dict[str, Any]:
        policy_tag = str(signal_card.evidence_snapshot.get("policy_selection_tag", "none") or "none")
        capital_tag = str(signal_card.evidence_snapshot.get("capital_quality_tag", "none") or "none")
        semantic_decision = str(signal_card.evidence_snapshot.get("semantic_decision_summary", "") or "")
        technical_summary = str(signal_card.evidence_snapshot.get("technical_structure_summary", "") or "")
        semantic_reason_payload = dict(signal_card.evidence_snapshot.get("semantic_reason_payload", {}) or {})
        cross_strategy_conflict = signal_card.evidence_snapshot.get("cross_strategy_conflict", {}) or {}
        conflict_resolution = str(signal_card.evidence_snapshot.get("conflict_resolution", "none") or "none")

        policy_hint = {
            "policy_top_stock": "board top-stock",
            "policy_core_member": "board core member",
            "policy_cross_hit_candidate": "concept cross-hit candidate",
            "policy_keyword_fallback": "keyword fallback concept mapping",
        }.get(policy_tag, "no strong policy-board semantic")

        capital_hint = {
            "capital_quality_high": "high-quality persistent capital",
            "capital_quality_persistent": "persistent multi-day capital",
            "capital_quality_mixed": "mixed capital quality",
            "capital_quality_speculative": "high-heat low-quality speculative capital",
        }.get(capital_tag, "no strong capital-quality semantic")

        summary = (
            f"Policy semantic: {policy_hint}; "
            f"Capital semantic: {capital_hint}; "
            f"Technical semantic: {technical_summary or 'no technical structure summary'}; "
            f"Merger decision: {semantic_decision or 'no semantic decision summary'}"
        )
        policy_reason = dict(semantic_reason_payload.get("policy", {}) or {})
        capital_reason = dict(semantic_reason_payload.get("capital", {}) or {})
        technical_reason = dict(semantic_reason_payload.get("technical", {}) or {})
        prompt_slots = {
            "schema_name": SEMANTIC_PROMPT_SCHEMA_NAME,
            "schema_version": SEMANTIC_PROMPT_SCHEMA_VERSION,
            "policy_role": policy_tag,
            "policy_interpretation": policy_hint,
            "capital_quality": capital_tag,
            "capital_interpretation": capital_hint,
            "decision_summary": semantic_decision or "no semantic decision summary",
            "technical_structure_summary": technical_summary or "no technical structure summary",
            "cross_strategy_conflict": cross_strategy_conflict,
            "conflict_resolution": conflict_resolution,
            "risk_flags": list(signal_card.risk_flags),
            "trigger_reason": signal_card.trigger_reason,
            "strategy_sources": list(signal_card.strategy_sources),
            "semantic_reason_payload": semantic_reason_payload,
            "semantic_decision_reasons": list(semantic_reason_payload.get("reasons", []) or []),
            "semantic_priority": semantic_reason_payload.get("semantic_priority", signal_card.evidence_snapshot.get("semantic_priority", 0)),
            "policy_strength": policy_reason.get("policy_strength", 0),
            "policy_primary_concept_score": policy_reason.get("primary_concept_score", "N/A"),
            "policy_concept_competition_score": policy_reason.get("concept_competition_score", "N/A"),
            "policy_multi_concept_overlap_count": policy_reason.get("multi_concept_overlap_count", "N/A"),
            "policy_primary_concept_selection_summary": policy_reason.get("primary_concept_selection_summary", ""),
            "capital_heat_quality_gap_score": capital_reason.get("heat_quality_gap_score", "N/A"),
            "capital_quality_weight": capital_reason.get("capital_quality_weight", "N/A"),
            "capital_risk_constraint_score": capital_reason.get("risk_constraint_score", "N/A"),
            "capital_continuity_score": capital_reason.get("continuity_score", "N/A"),
            "capital_quality_stability_index": capital_reason.get("quality_stability_index", "N/A"),
            "technical_structure_risk_score": technical_reason.get("structure_risk_score", "N/A"),
            "technical_trend_consistency_score": technical_reason.get("trend_consistency_score", "N/A"),
            "technical_recent_extension_pct": technical_reason.get("recent_extension_pct", "N/A"),
            "technical_volume_confirmation_score": technical_reason.get("volume_confirmation_score", "N/A"),
            "technical_breakout_quality_score": technical_reason.get("breakout_quality_score", "N/A"),
            "technical_volume_price_divergence_score": technical_reason.get("volume_price_divergence_score", "N/A"),
            "technical_signal_consistency_index": technical_reason.get("signal_consistency_index", "N/A"),
            "policy_concept_conviction_score": policy_reason.get("concept_conviction_score", "N/A"),
        }
        return {
            "policy_selection_tag": policy_tag,
            "capital_quality_tag": capital_tag,
            "semantic_decision_summary": semantic_decision,
            "technical_structure_summary": technical_summary,
            "semantic_reason_payload": semantic_reason_payload,
            "cross_strategy_conflict": cross_strategy_conflict,
            "conflict_resolution": conflict_resolution,
            "policy_hint": policy_hint,
            "capital_hint": capital_hint,
            "summary": summary,
            "prompt_slots": prompt_slots,
        }

    @staticmethod
    def _build_route_decision(signal_card: SignalCard, semantic_context: Dict[str, Any]) -> Dict[str, Any]:
        raw_prompt_slots = dict(semantic_context.get("prompt_slots", {}) or {})
        prompt_slots = validate_semantic_prompt_slots(raw_prompt_slots)
        policy_role = str(prompt_slots.get("policy_role", "none") or "none")
        capital_quality = str(prompt_slots.get("capital_quality", "none") or "none")
        conflict_resolution = str(raw_prompt_slots.get("conflict_resolution", "none") or "none")
        cross_conflict = raw_prompt_slots.get("cross_strategy_conflict", {}) or {}
        conflict_tier = str(cross_conflict.get("tier", "none") or "none")

        analyst_focus = ["baseline"]
        if policy_role in {"policy_top_stock", "policy_core_member"}:
            analyst_focus.append("policy_board")
        if capital_quality in {"capital_quality_speculative", "capital_quality_mixed"}:
            analyst_focus.append("risk_capital")
        elif capital_quality in {"capital_quality_high", "capital_quality_persistent"}:
            analyst_focus.append("capital_confirmation")
        if prompt_slots.get("policy_multi_concept_overlap_count", 0) not in {"N/A", None}:
            try:
                if int(prompt_slots.get("policy_multi_concept_overlap_count", 0)) >= 2:
                    analyst_focus.append("concept_overlap")
            except (TypeError, ValueError):  # non-numeric slot value — skip this focus
                pass
        if prompt_slots.get("capital_heat_quality_gap_score", "N/A") not in {"N/A", None}:
            try:
                if float(prompt_slots.get("capital_heat_quality_gap_score", 0.0)) >= 22:
                    analyst_focus.append("heat_quality_gap")
            except (TypeError, ValueError):  # non-numeric slot value — skip this focus
                pass
        if conflict_tier in {"high", "severe"}:
            analyst_focus.append("conflict_resolution")
        if (
            "trend_structure_extended" in signal_card.risk_flags
            or "lost_ma20_support" in signal_card.risk_flags
            or "volume_exhaustion_risk" in signal_card.risk_flags
            or "price_volume_divergence" in signal_card.risk_flags
        ):
            analyst_focus.append("technical_risk")

        debate_risk_weight = "high" if capital_quality == "capital_quality_speculative" or conflict_tier == "severe" else "normal"
        debate_rounds = "compressed" if capital_quality == "capital_quality_speculative" else "standard"

        selected_analysts = DeepAnalyzer._derive_semantic_selected_analysts(
            ["market", "social", "news", "fundamentals"],
            prompt_slots,
        )
        semantic_flow_controls = derive_semantic_flow_controls(prompt_slots)
        semantic_flow_controls["debate_round_limit"] = (
            1 if debate_rounds == "compressed" else semantic_flow_controls.get("debate_round_limit")
        )
        semantic_flow_controls["force_risk_review"] = (
            True if debate_risk_weight == "high" else semantic_flow_controls.get("force_risk_review", False)
        )
        semantic_flow_controls["prompt_slot_mode"] = "structured_semantic_payload"
        if "policy_top_stock" in {policy_role}:
            semantic_flow_controls["analysis_priority"] = "policy_leadership"
        elif "policy_core_member" == policy_role:
            semantic_flow_controls["analysis_priority"] = "policy_supporting_member"
        else:
            semantic_flow_controls["analysis_priority"] = "general_screening"

        return {
            "route_family": "semantic_router_v1",
            "policy_role": policy_role,
            "capital_quality": capital_quality,
            "conflict_tier": conflict_tier,
            "conflict_resolution": conflict_resolution,
            "analyst_focus": analyst_focus,
            "debate_risk_weight": debate_risk_weight,
            "debate_rounds": debate_rounds,
            "semantic_priority": prompt_slots.get("semantic_priority", 0),
            "selected_analysts": selected_analysts,
            "semantic_flow_controls": semantic_flow_controls,
        }

    @staticmethod
    def _build_graph_config_snapshot(graph_config: Dict[str, Any]) -> Dict[str, Any]:
        screener_context = graph_config.get("screener_context", {}) if isinstance(graph_config, dict) else {}
        return {
            "has_screener_context": bool(screener_context),
            "semantic_schema_name": screener_context.get("semantic_prompt_slots", {}).get("schema_name", ""),
            "semantic_schema_version": screener_context.get("semantic_prompt_slots", {}).get("schema_version", ""),
            "route_family": screener_context.get("route_decision", {}).get("route_family", ""),
            "company_of_interest": graph_config.get("company_of_interest", ""),
            "selected_analysts": screener_context.get("selected_analysts", []),
            "semantic_flow_controls": graph_config.get("semantic_flow_controls", {}),
        }

    @staticmethod
    def _derive_semantic_selected_analysts(
        requested_analysts: List[str],
        semantic_slots: Dict[str, Any] | None,
    ) -> List[str]:
        slots = dict(semantic_slots or {})
        policy_role = str(slots.get("policy_role", "none") or "none")
        selected = list(requested_analysts)
        if policy_role == "policy_top_stock":
            prioritized = ["news", "market", "social", "fundamentals"]
            selected = [name for name in prioritized if name in selected]
        elif policy_role == "policy_core_member":
            prioritized = ["news", "market", "fundamentals"]
            selected = [name for name in prioritized if name in selected]
        heat_gap = slots.get("capital_heat_quality_gap_score", "N/A")
        try:
            if float(heat_gap) >= 22 and "social" in selected:
                selected = [name for name in selected if name != "social"] + ["social"]
        except (TypeError, ValueError):  # non-numeric heat-gap value — keep original order
            pass
        return selected or list(requested_analysts)

