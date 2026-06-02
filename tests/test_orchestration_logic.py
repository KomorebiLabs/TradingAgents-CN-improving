import unittest

from tradingagents.agents.utils.state_helpers import (
    determine_risk_debate_exit_stage,
    determine_risk_follow_up_speaker,
    determine_research_manager_next_stage,
    determine_risk_next_stage,
    determine_trader_next_stage,
    has_full_risk_debate_coverage,
)
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.setup import (
    create_orchestration_router,
    create_phase_handoff_node,
    create_risk_finalize_node,
)
from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.managers.portfolio_manager import create_portfolio_manager
from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
from tradingagents.agents.risk_mgmt.conservative_debator import create_conservative_debator
from tradingagents.agents.risk_mgmt.neutral_debator import create_neutral_debator
from tradingagents.agents.trader.trader import create_trader
from tradingagents.agents.utils.agent_utils import (
    derive_semantic_flow_controls,
    derive_semantic_selected_analysts,
)


class OrchestrationLogicTests(unittest.TestCase):
    class _StubResponse:
        def __init__(self, content):
            self.content = content

    class _StubLLM:
        def __init__(self, content):
            self.content = content
            self.last_prompt = None

        def invoke(self, prompt):
            self.last_prompt = prompt
            return OrchestrationLogicTests._StubResponse(self.content)

    def test_orchestration_router_sets_stage_phase_and_next_stage(self):
        router = create_orchestration_router("analyst", "research")
        result = router(
            {
                "orchestration": {"stage": "analysis"},
                "semantic_prompt_slots": {
                    "schema_name": "screener.semantic_prompt_slots",
                    "schema_version": "1.0",
                    "policy_role": "policy_top_stock",
                    "capital_quality": "capital_quality_high",
                    "policy_multi_concept_overlap_count": 2,
                },
                "route_decision": {
                    "route_family": "semantic_router_v1",
                    "policy_role": "policy_top_stock",
                    "capital_quality": "capital_quality_high",
                    "semantic_priority": 5,
                    "analyst_focus": ["baseline", "policy_board", "concept_overlap"],
                    "selected_analysts": ["news", "market"],
                },
            }
        )

        self.assertEqual(result["orchestration"]["stage"], "route_research")
        self.assertEqual(result["orchestration"]["phase"], "analyst")
        self.assertEqual(result["orchestration"]["next_stage"], "research")
        audit = result["orchestration"]["event_trail"][0]["semantic_trigger_audit"]
        self.assertIn("policy_role=policy_top_stock", audit["semantic_trigger_reasons"])
        self.assertIn("analyst_focus:concept_overlap", audit["semantic_trigger_reasons"])
        self.assertEqual(audit["route_decision_snapshot"]["route_family"], "semantic_router_v1")

    def test_conditional_logic_routes_by_next_stage(self):
        logic = ConditionalLogic()

        self.assertEqual(
            logic.route_orchestration_stage({"orchestration": {"next_stage": "research"}}),
            "Bull Researcher",
        )
        self.assertEqual(
            logic.route_orchestration_stage({"orchestration": {"next_stage": "trader"}}),
            "Trader",
        )
        self.assertEqual(
            logic.route_orchestration_stage({"orchestration": {"next_stage": "risk"}}),
            "Aggressive Analyst",
        )
        self.assertEqual(
            logic.route_orchestration_stage({"orchestration": {"next_stage": "analysis"}}),
            "Route Research Phase",
        )

    def test_semantic_selected_analysts_prioritize_policy_top_stock(self):
        selected = derive_semantic_selected_analysts(
            ["market", "social", "news", "fundamentals"],
            {
                "schema_name": "screener.semantic_prompt_slots",
                "schema_version": "1.0",
                "policy_role": "policy_top_stock",
                "capital_quality": "capital_quality_high",
                "policy_multi_concept_overlap_count": 2,
            },
        )
        self.assertEqual(selected, ["news", "market", "social", "fundamentals"])

    def test_semantic_selected_analysts_reduce_pipeline_for_core_member(self):
        selected = derive_semantic_selected_analysts(
            ["market", "social", "news", "fundamentals"],
            {
                "schema_name": "screener.semantic_prompt_slots",
                "schema_version": "1.0",
                "policy_role": "policy_core_member",
                "capital_quality": "capital_quality_high",
            },
        )
        self.assertEqual(selected, ["news", "market", "fundamentals"])

    def test_semantic_flow_controls_harden_speculative_capital_path(self):
        controls = derive_semantic_flow_controls(
            {
                "schema_name": "screener.semantic_prompt_slots",
                "schema_version": "1.0",
                "policy_role": "policy_top_stock",
                "capital_quality": "capital_quality_speculative",
                "capital_heat_quality_gap_score": 28.0,
                "technical_volume_price_divergence_score": 38.0,
            }
        )
        self.assertEqual(controls["debate_round_limit"], 1)
        self.assertEqual(controls["risk_round_limit"], 2)
        self.assertTrue(controls["force_risk_review"])
        self.assertTrue(controls["risk_hardening"])
        self.assertEqual(controls["prompt_slot_mode"], "structured_semantic_payload")

    def test_semantic_instruction_includes_graph_route_decision(self):
        from tradingagents.agents.utils.agent_utils import build_screener_semantic_instruction

        instruction = build_screener_semantic_instruction(
            {
                "semantic_prompt_slots": {
                    "schema_name": "screener.semantic_prompt_slots",
                    "schema_version": "1.0",
                    "policy_role": "policy_top_stock",
                    "capital_quality": "capital_quality_speculative",
                    "decision_summary": "retained_priority: concept top-stock gained priority",
                    "trigger_reason": "policy_concept_top_pick",
                    "risk_flags": ["trend_structure_extended"],
                    "policy_multi_concept_overlap_count": 2,
                    "capital_heat_quality_gap_score": 29.0,
                    "technical_volume_price_divergence_score": 37.0,
                },
                "route_decision": {
                    "route_family": "semantic_router_v1",
                    "conflict_tier": "severe",
                    "analyst_focus": ["baseline", "policy_board", "risk_capital", "concept_overlap", "heat_quality_gap", "conflict_resolution"],
                    "debate_rounds": "compressed",
                    "debate_risk_weight": "high",
                    "selected_analysts": ["news", "market", "social", "fundamentals"],
                },
            },
            "trader",
        )

        self.assertIn("Graph route decision: route_family=semantic_router_v1", instruction)
        self.assertIn("debate_rounds=compressed", instruction)
        self.assertIn("selected_analysts=['news', 'market', 'social', 'fundamentals']", instruction)
        self.assertIn("policy_overlap=2", instruction)
        self.assertIn("capital_heat_gap=29.0", instruction)
        self.assertIn("technical_volume_divergence=37.0", instruction)

    def test_router_marks_compression_required_when_context_exceeds_threshold(self):
        router = create_orchestration_router("analyst", "research")
        state = {
            "analyst_reports": {
                "market": "a" * 20,
                "sentiment": "b" * 20,
                "news": "c" * 20,
                "fundamentals": "d" * 20,
            },
            "orchestration": {
                "compression_threshold_tokens": 50,
            },
        }

        result = router(state)

        self.assertTrue(result["orchestration"]["compression_required"])

    def test_phase_handoff_generates_compression_notes_and_clears_flag(self):
        llm = self._StubLLM("compressed memo")
        handoff = create_phase_handoff_node("analyst", "research", llm)
        state = {
            "analyst_reports": {
                "market": "market summary",
                "news": "news summary",
            },
            "orchestration": {
                "compression_required": True,
            },
        }

        result = handoff(state)

        self.assertFalse(result["orchestration"]["compression_required"])
        self.assertEqual(result["orchestration"]["next_stage"], "research")
        self.assertEqual(result["orchestration"]["compression_notes"], "compressed memo")
        self.assertIn("market: market summary", llm.last_prompt)

    def test_research_handoff_uses_trader_ready_prompt(self):
        llm = self._StubLLM("research memo")
        handoff = create_phase_handoff_node("research", "trader", llm)
        state = {
            "investment_debate_state": {
                "history": "Bull says growth. Bear says valuation risk.",
            },
            "orchestration": {},
        }

        result = handoff(state)

        self.assertEqual(result["orchestration"]["next_stage"], "trader")
        self.assertIn("trader-ready handoff memo", llm.last_prompt)

    def test_conditional_logic_prefers_summary_when_compression_required(self):
        logic = ConditionalLogic()

        target = logic.route_orchestration_stage(
            {
                "orchestration": {
                    "phase": "analyst",
                    "next_stage": "research",
                    "compression_required": True,
                }
            }
        )

        self.assertEqual(target, "Summarize Analyst Phase")

    def test_conditional_logic_prefers_trader_and_risk_summaries(self):
        logic = ConditionalLogic()

        trader_target = logic.route_orchestration_stage(
            {
                "orchestration": {
                    "phase": "trader",
                    "next_stage": "risk",
                    "compression_required": True,
                }
            }
        )
        risk_target = logic.route_orchestration_stage(
            {
                "orchestration": {
                    "phase": "risk",
                    "next_stage": "portfolio",
                    "compression_required": True,
                }
            }
        )

        self.assertEqual(trader_target, "Summarize Trader Phase")
        self.assertEqual(risk_target, "Summarize Risk Phase")

    def test_research_manager_can_request_handoff(self):
        next_stage = determine_research_manager_next_stage(
            debate_history="Bull vs Bear " * 500,
            manager_decision="decision",
            compression_notes="",
        )
        self.assertEqual(next_stage, "trader_handoff")

    def test_trader_can_request_handoff(self):
        next_stage = determine_trader_next_stage(
            investment_plan="plan " * 900,
            trader_output="trade",
            compression_notes="",
        )
        self.assertEqual(next_stage, "risk_handoff")

    def test_risk_can_request_handoff(self):
        next_stage = determine_risk_next_stage(
            risk_history="risk debate " * 400,
            latest_argument="argument",
            compression_notes="",
        )
        self.assertEqual(next_stage, "portfolio_handoff")

    def test_existing_compression_notes_skip_repeat_handoff(self):
        self.assertEqual(
            determine_research_manager_next_stage("x" * 10000, "y" * 3000, "memo"),
            "trader",
        )
        self.assertEqual(
            determine_trader_next_stage("x" * 5000, "y" * 3000, "memo"),
            "risk",
        )
        self.assertEqual(
            determine_risk_next_stage("x" * 5000, "y" * 3000, "memo"),
            "portfolio",
        )

    def test_trader_handoff_uses_risk_review_prompt(self):
        llm = self._StubLLM("trader memo")
        handoff = create_phase_handoff_node("trader", "risk", llm)
        state = {
            "investment_plan": "buy on pullback",
            "trader_investment_plan": "enter 20% now, add 10% later",
            "orchestration": {},
        }

        result = handoff(state)

        self.assertEqual(result["orchestration"]["next_stage"], "risk")
        self.assertIn("risk-review memo", llm.last_prompt)

    def test_risk_handoff_uses_portfolio_prompt(self):
        llm = self._StubLLM("risk memo")
        handoff = create_phase_handoff_node("risk", "portfolio", llm)
        state = {
            "risk_debate_state": {
                "history": "Aggressive says size up. Conservative says keep stops tight.",
            },
            "orchestration": {},
        }

        result = handoff(state)

        self.assertEqual(result["orchestration"]["next_stage"], "portfolio")
        self.assertIn("portfolio-manager memo", llm.last_prompt)

    def test_risk_coverage_helper_detects_missing_voice(self):
        risk_state = {
            "current_aggressive_response": "long risk-on case",
            "current_conservative_response": "",
            "current_neutral_response": "balanced case",
        }
        self.assertFalse(has_full_risk_debate_coverage(risk_state))
        self.assertEqual(
            determine_risk_follow_up_speaker(risk_state),
            "Conservative Analyst",
        )

    def test_risk_conditional_logic_extends_debate_until_full_coverage(self):
        logic = ConditionalLogic(max_risk_discuss_rounds=1)
        target = logic.should_continue_risk_analysis(
            {
                "risk_debate_state": {
                    "count": 3,
                    "latest_speaker": "Neutral",
                    "current_aggressive_response": "agg",
                    "current_conservative_response": "",
                    "current_neutral_response": "neu",
                }
            }
        )
        self.assertEqual(target, "Conservative Analyst")

    def test_risk_conditional_logic_finalizes_when_full_coverage_and_limit_reached(self):
        logic = ConditionalLogic(max_risk_discuss_rounds=1)
        target = logic.should_continue_risk_analysis(
            {
                "risk_debate_state": {
                    "count": 3,
                    "latest_speaker": "Neutral",
                    "current_aggressive_response": "agg",
                    "current_conservative_response": "con",
                    "current_neutral_response": "neu",
                }
            }
        )
        self.assertEqual(target, "Finalize Risk Debate")

    def test_speculative_capital_forces_extra_conservative_risk_pass(self):
        logic = ConditionalLogic(
            max_risk_discuss_rounds=1,
            semantic_flow_controls={
                "risk_round_limit": 1,
                "force_risk_review": True,
                "risk_hardening": True,
            },
        )
        target = logic.should_continue_risk_analysis(
            {
                "risk_debate_state": {
                    "count": 3,
                    "latest_speaker": "Neutral",
                    "current_aggressive_response": "agg",
                    "current_conservative_response": "con",
                    "current_neutral_response": "neu",
                }
            }
        )
        self.assertEqual(target, "Conservative Analyst")

    def test_speculative_debate_limit_shortens_bull_bear_cycle(self):
        logic = ConditionalLogic(
            max_debate_rounds=3,
            semantic_flow_controls={"debate_round_limit": 1},
        )
        target = logic.should_continue_debate(
            {
                "investment_debate_state": {
                    "count": 2,
                    "current_response": "Bear Analyst: counter",
                }
            }
        )
        self.assertEqual(target, "Research Manager")

    def test_policy_top_stock_high_quality_gets_extra_research_round(self):
        logic = ConditionalLogic(
            max_debate_rounds=1,
            semantic_flow_controls={"debate_round_limit": 1},
        )
        target = logic.should_continue_debate(
            {
                "route_decision": {
                    "policy_role": "policy_top_stock",
                    "capital_quality": "capital_quality_high",
                    "conflict_tier": "aligned",
                    "semantic_flow_controls": {"debate_round_limit": 1},
                },
                "investment_debate_state": {
                    "count": 2,
                    "current_response": "Bear Analyst: counter",
                },
            }
        )
        self.assertEqual(target, "Bull Researcher")

    def test_multi_concept_overlap_extends_debate_route(self):
        logic = ConditionalLogic(
            max_debate_rounds=1,
            semantic_flow_controls={"debate_round_limit": 1},
        )
        route_reason = logic._debate_route_reason(
            {
                "route_decision": {
                    "policy_role": "policy_top_stock",
                    "capital_quality": "capital_quality_high",
                    "conflict_tier": "moderate",
                    "analyst_focus": ["baseline", "policy_board", "concept_overlap"],
                    "semantic_priority": 5,
                    "semantic_flow_controls": {"debate_round_limit": 1},
                }
            },
            2,
        )
        self.assertEqual(route_reason, "top_stock_high_quality_debate_extension_2")

    def test_heat_quality_gap_and_technical_risk_extend_risk_rounds(self):
        logic = ConditionalLogic(
            max_risk_discuss_rounds=1,
            semantic_flow_controls={"risk_round_limit": 1},
        )
        target = logic.should_continue_risk_analysis(
            {
                "route_decision": {
                    "policy_role": "policy_keyword_fallback",
                    "capital_quality": "capital_quality_mixed",
                    "conflict_tier": "moderate",
                    "analyst_focus": ["baseline", "heat_quality_gap", "technical_risk"],
                    "semantic_priority": -2,
                    "semantic_flow_controls": {"risk_round_limit": 1, "force_risk_review": True, "risk_hardening": True},
                },
                "risk_debate_state": {
                    "count": 3,
                    "latest_speaker": "Neutral",
                    "current_aggressive_response": "agg",
                    "current_conservative_response": "con",
                    "current_neutral_response": "neu",
                },
            }
        )
        self.assertEqual(target, "Aggressive Analyst")

    def test_speculative_top_stock_keeps_hardened_risk_path(self):
        logic = ConditionalLogic(
            max_risk_discuss_rounds=1,
            semantic_flow_controls={
                "risk_round_limit": 1,
                "force_risk_review": True,
                "risk_hardening": True,
            },
        )
        target = logic.should_continue_risk_analysis(
            {
                "route_decision": {
                    "policy_role": "policy_top_stock",
                    "capital_quality": "capital_quality_speculative",
                    "conflict_tier": "severe",
                    "semantic_flow_controls": {
                        "risk_round_limit": 1,
                        "force_risk_review": True,
                        "risk_hardening": True,
                    },
                },
                "risk_debate_state": {
                    "count": 3,
                    "latest_speaker": "Neutral",
                    "current_aggressive_response": "agg",
                    "current_conservative_response": "con",
                    "current_neutral_response": "neu",
                },
            }
        )
        self.assertEqual(target, "Conservative Analyst")

    def test_high_quality_top_stock_can_finalize_risk_sooner_after_coverage(self):
        logic = ConditionalLogic(
            max_risk_discuss_rounds=2,
            semantic_flow_controls={"risk_round_limit": 1},
        )
        target = logic.should_continue_risk_analysis(
            {
                "route_decision": {
                    "policy_role": "policy_top_stock",
                    "capital_quality": "capital_quality_high",
                    "conflict_tier": "aligned",
                    "semantic_flow_controls": {"risk_round_limit": 1},
                },
                "risk_debate_state": {
                    "count": 3,
                    "latest_speaker": "Neutral",
                    "current_aggressive_response": "agg",
                    "current_conservative_response": "con",
                    "current_neutral_response": "neu",
                },
            }
        )
        self.assertEqual(target, "Finalize Risk Debate")

    def test_risk_finalize_node_requests_handoff_when_needed(self):
        node = create_risk_finalize_node()
        state = {
            "risk_debate_state": {
                "history": "risk debate " * 500,
                "current_aggressive_response": "agg",
                "current_conservative_response": "con",
                "current_neutral_response": "neu",
            },
            "orchestration": {
                "compression_notes": "",
            },
        }
        result = node(state)
        self.assertEqual(result["orchestration"]["next_stage"], "portfolio_handoff")
        self.assertTrue(result["orchestration"]["compression_required"])
        self.assertEqual(result["orchestration"]["final_route"], "portfolio_handoff")
        self.assertEqual(
            result["orchestration"]["final_reason"],
            "risk_debate_exceeded_safe_context",
        )

    def test_risk_debate_exit_stage_skips_repeat_handoff_when_notes_exist(self):
        next_stage = determine_risk_debate_exit_stage(
            {
                "history": "risk debate " * 500,
                "current_aggressive_response": "agg",
                "current_conservative_response": "con",
                "current_neutral_response": "neu",
            },
            "existing memo",
        )
        self.assertEqual(next_stage, "portfolio")

    def test_risk_finalize_node_reuses_existing_handoff_reason(self):
        node = create_risk_finalize_node()
        state = {
            "risk_debate_state": {
                "history": "risk debate",
                "current_aggressive_response": "agg",
                "current_conservative_response": "con",
                "current_neutral_response": "neu",
            },
            "orchestration": {
                "compression_notes": "existing memo",
            },
        }
        result = node(state)
        self.assertEqual(result["orchestration"]["next_stage"], "portfolio")
        self.assertEqual(
            result["orchestration"]["final_reason"],
            "existing_risk_handoff_available",
        )

    def test_portfolio_manager_marks_orchestration_completed(self):
        llm = self._StubLLM("<decision>Buy</decision>")

        class _StubMemory:
            def get_memories(self, *_args, **_kwargs):
                return []

        node = create_portfolio_manager(llm, _StubMemory())
        state = {
            "company_of_interest": "600519.SH",
            "market_report": "market",
            "sentiment_report": "sentiment",
            "news_report": "news",
            "fundamentals_report": "fundamentals",
            "investment_plan": "investment plan",
            "trader_investment_plan": "trader plan",
            "risk_debate_state": {
                "history": "risk history",
                "aggressive_history": "agg",
                "conservative_history": "con",
                "neutral_history": "neu",
                "current_aggressive_response": "agg current",
                "current_conservative_response": "con current",
                "current_neutral_response": "neu current",
                "judge_decision": "",
                "latest_speaker": "Neutral",
                "count": 3,
            },
            "orchestration": {
                "final_route": "portfolio_handoff",
                "final_reason": "risk_debate_exceeded_safe_context",
                "compression_notes": "compressed risk memo",
            },
        }
        result = node(state)
        self.assertEqual(result["orchestration"]["stage"], "completed")
        self.assertEqual(result["orchestration"]["phase"], "completed")
        self.assertEqual(result["orchestration"]["next_stage"], "completed")
        self.assertTrue(result["orchestration"]["completed"])
        self.assertEqual(result["orchestration"]["final_route"], "portfolio_handoff")
        self.assertEqual(
            result["orchestration"]["final_reason"],
            "risk_debate_exceeded_safe_context",
        )

    def test_trader_prompt_uses_screener_semantic_routing_guidance(self):
        llm = self._StubLLM("<decision>FINAL TRANSACTION PROPOSAL: **BUY**</decision>")

        class _StubMemory:
            def get_memories(self, *_args, **_kwargs):
                return []

        node = create_trader(llm, _StubMemory())
        state = {
            "company_of_interest": "600519.SH",
            "market_report": "market",
            "sentiment_report": "sentiment",
            "news_report": "news",
            "fundamentals_report": "fundamentals",
            "investment_plan": "investment plan",
            "orchestration": {"compression_notes": ""},
            "semantic_prompt_slots": {
                "schema_name": "screener.semantic_prompt_slots",
                "schema_version": "1.0",
                "policy_role": "policy_top_stock",
                "capital_quality": "capital_quality_speculative",
                "decision_summary": "retained_priority: concept top-stock gained priority",
                "risk_flags": ["speculative_flow_dominant"],
                "trigger_reason": "smart_money_speculative_flow",
                "strategy_sources": ["policy", "smart_money"],
                "policy_multi_concept_overlap_count": 2,
                "capital_heat_quality_gap_score": 31.0,
                "technical_volume_price_divergence_score": 36.0,
            },
        }

        node(state)
        rendered = str(llm.last_prompt)
        self.assertIn("Screener semantic routing guidance", rendered)
        self.assertIn("Semantic execution profile", rendered)
        self.assertIn("policy_role=policy_top_stock", rendered)
        self.assertIn("capital_quality=capital_quality_speculative", rendered)
        self.assertIn("policy_overlap=2", rendered)
        self.assertIn("capital_heat_gap=31.0", rendered)
        result = node(state)
        self.assertIn("execution_profile_evidence_check", result["trader_investment_plan"])

    def test_portfolio_manager_prompt_uses_screener_semantic_routing_guidance(self):
        llm = self._StubLLM("<decision>Buy</decision>")

        class _StubMemory:
            def get_memories(self, *_args, **_kwargs):
                return []

        node = create_portfolio_manager(llm, _StubMemory())
        state = {
            "company_of_interest": "600519.SH",
            "market_report": "market",
            "sentiment_report": "sentiment",
            "news_report": "news",
            "fundamentals_report": "fundamentals",
            "investment_plan": "investment plan",
            "trader_investment_plan": "trader plan",
            "risk_debate_state": {
                "history": "risk history",
                "aggressive_history": "agg",
                "conservative_history": "con",
                "neutral_history": "neu",
                "current_aggressive_response": "agg current",
                "current_conservative_response": "con current",
                "current_neutral_response": "neu current",
                "judge_decision": "",
                "latest_speaker": "Neutral",
                "count": 3,
            },
            "orchestration": {
                "final_route": "portfolio_handoff",
                "final_reason": "risk_debate_exceeded_safe_context",
                "compression_notes": "compressed risk memo",
            },
            "semantic_prompt_slots": {
                "schema_name": "screener.semantic_prompt_slots",
                "schema_version": "1.0",
                "policy_role": "policy_core_member",
                "capital_quality": "capital_quality_high",
                "decision_summary": "retained_priority: high-quality persistent capital flow",
                "risk_flags": [],
                "trigger_reason": "smart_money_persistent_high_quality",
                "strategy_sources": ["policy", "smart_money"],
                "policy_multi_concept_overlap_count": 2,
                "policy_primary_concept_score": 82.0,
            },
        }

        node(state)
        self.assertIn("Screener semantic routing guidance", llm.last_prompt)
        self.assertIn("Semantic execution profile", llm.last_prompt)
        self.assertIn("capital_quality=capital_quality_high", llm.last_prompt)
        self.assertIn("policy_role=policy_core_member", llm.last_prompt)
        self.assertIn("policy_overlap=2", llm.last_prompt)
        result = node(state)
        self.assertIn("execution_profile_evidence_check", result["final_trade_decision"])

    def test_bull_and_bear_researchers_receive_semantic_routing_guidance(self):
        llm = self._StubLLM("argument")

        class _StubMemory:
            def get_memories(self, *_args, **_kwargs):
                return []

        bull = create_bull_researcher(llm, _StubMemory())
        bear = create_bear_researcher(llm, _StubMemory())
        state = {
            "market_report": "market",
            "sentiment_report": "sentiment",
            "news_report": "news",
            "fundamentals_report": "fundamentals",
            "investment_debate_state": {
                "history": "history",
                "bull_history": "",
                "bear_history": "",
                "current_response": "counterparty argument",
                "count": 0,
            },
            "semantic_prompt_slots": {
                "schema_name": "screener.semantic_prompt_slots",
                "schema_version": "1.0",
                "policy_role": "policy_top_stock",
                "capital_quality": "capital_quality_speculative",
                "decision_summary": "retained_priority: concept top-stock gained priority",
                "risk_flags": ["speculative_flow_dominant"],
                "trigger_reason": "smart_money_speculative_flow",
                "strategy_sources": ["policy", "smart_money"],
                "policy_multi_concept_overlap_count": 2,
                "capital_heat_quality_gap_score": 30.0,
            },
        }

        bull(state)
        self.assertIn("Screener semantic routing guidance", llm.last_prompt)
        self.assertIn("Semantic execution profile", llm.last_prompt)
        self.assertIn("policy_role=policy_top_stock", llm.last_prompt)
        self.assertIn("policy_overlap=2", llm.last_prompt)

        bear(state)
        self.assertIn("capital_quality=capital_quality_speculative", llm.last_prompt)
        self.assertIn("capital_heat_gap=30.0", llm.last_prompt)

    def test_risk_debators_receive_semantic_routing_guidance(self):
        llm = self._StubLLM("risk argument")
        aggressive = create_aggressive_debator(llm)
        conservative = create_conservative_debator(llm)
        neutral = create_neutral_debator(llm)
        state = {
            "market_report": "market",
            "sentiment_report": "sentiment",
            "news_report": "news",
            "fundamentals_report": "fundamentals",
            "trader_investment_plan": "buy tactically",
            "risk_debate_state": {
                "history": "risk history",
                "aggressive_history": "",
                "conservative_history": "",
                "neutral_history": "",
                "latest_speaker": "",
                "current_aggressive_response": "",
                "current_conservative_response": "",
                "current_neutral_response": "",
                "judge_decision": "",
                "count": 0,
            },
            "orchestration": {"compression_notes": ""},
            "semantic_prompt_slots": {
                "schema_name": "screener.semantic_prompt_slots",
                "schema_version": "1.0",
                "policy_role": "policy_core_member",
                "capital_quality": "capital_quality_high",
                "decision_summary": "retained_priority: high-quality persistent capital flow",
                "risk_flags": [],
                "trigger_reason": "smart_money_persistent_high_quality",
                "strategy_sources": ["policy", "smart_money"],
                "technical_volume_price_divergence_score": 39.0,
            },
        }

        aggressive(state)
        self.assertIn("Screener semantic routing guidance", llm.last_prompt)
        self.assertIn("Semantic execution profile", llm.last_prompt)
        self.assertIn("capital_quality=capital_quality_high", llm.last_prompt)
        self.assertIn("technical_volume_divergence=39.0", llm.last_prompt)

        conservative(state)
        self.assertIn("policy_role=policy_core_member", llm.last_prompt)

        neutral(state)
        self.assertIn("Semantic slot schema: screener.semantic_prompt_slots v1.0", llm.last_prompt)


if __name__ == "__main__":
    unittest.main()
