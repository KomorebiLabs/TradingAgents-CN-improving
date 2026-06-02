import unittest
from unittest.mock import patch
import importlib.util
from pathlib import Path

from tradingagents.screener.deep_analyzer import DeepAnalyzer
from tradingagents.screener.models import SignalCard, SignalEvidence


class ScreenerDeepAnalyzerTests(unittest.TestCase):
    def test_dry_run_returns_success(self):
        # H3 FIX: explicitly disable real analysis to test dry-run path
        analyzer = DeepAnalyzer(config={"enable_real_deep_analysis": False})
        card = SignalCard(
            ticker="600519.SH",
            raw_code="600519",
            exchange="SH",
            company_name="贵州茅台",
            trade_date="2026-05-07",
            concept_tags=["人工智能", "policy_top_stock", "capital_quality_speculative"],
            strategy_sources=["technical"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="policy",
                    score=80.0,
                    reason="policy semantic",
                    raw_metrics={"stock_selection_tag": "policy_top_stock"},
                )
            ],
            trigger_reason="technical_trigger",
            initial_confidence=85.0,
            screening_score=82.0,
            evidence_snapshot={
                "policy_selection_tag": "policy_top_stock",
                "capital_quality_tag": "capital_quality_speculative",
                "semantic_decision_summary": "retained_priority: concept top-stock gained priority",
                "semantic_reason_payload": {
                    "decision": "retained",
                    "summary": "retained_priority: concept top-stock gained priority",
                    "semantic_priority": 4,
                    "reasons": [],
                    "policy": {
                        "policy_strength": 3,
                        "primary_concept_score": 84.0,
                        "concept_competition_score": 81.0,
                        "multi_concept_overlap_count": 2,
                        "primary_concept_selection_summary": "人工智能 selected as primary concept",
                    },
                    "capital": {
                        "heat_quality_gap_score": 28.0,
                        "capital_quality_weight": -5.5,
                        "risk_constraint_score": 42.0,
                        "continuity_score": 46.0,
                    },
                    "technical": {
                        "structure_risk_score": 39.0,
                        "trend_consistency_score": 43.0,
                        "recent_extension_pct": 9.5,
                        "volume_confirmation_score": 41.0,
                        "breakout_quality_score": 44.0,
                        "volume_price_divergence_score": 38.0,
                    },
                },
            },
            risk_flags=["volume_exhaustion_risk", "price_volume_divergence"],
        )

        result = analyzer.analyze(card, "2026-05-07")
        self.assertTrue(result.success)
        self.assertIn("DRY_RUN", result.final_decision or "")
        self.assertIn("Semantic context:", result.final_decision or "")
        self.assertEqual(result.final_state_summary["analysis_mode"], "dry_run")
        self.assertIn("board top-stock", result.final_state_summary["semantic_context_summary"])
        self.assertIn("speculative capital", result.final_state_summary["semantic_context_summary"])
        self.assertIn("semantic_prompt_slots", result.final_state_summary)
        self.assertEqual(
            result.final_state_summary["semantic_prompt_slots"]["schema_name"],
            "screener.semantic_prompt_slots",
        )
        self.assertEqual(
            result.final_state_summary["semantic_prompt_slots"]["schema_version"],
            "1.0",
        )
        self.assertEqual(
            result.final_state_summary["semantic_prompt_slots"]["policy_role"],
            "policy_top_stock",
        )
        self.assertEqual(
            result.final_state_summary["semantic_prompt_slots"]["capital_quality"],
            "capital_quality_speculative",
        )
        self.assertEqual(result.final_state_summary["semantic_prompt_slots"]["policy_primary_concept_score"], 84.0)
        self.assertEqual(result.final_state_summary["semantic_prompt_slots"]["capital_heat_quality_gap_score"], 28.0)
        self.assertEqual(result.final_state_summary["semantic_prompt_slots"]["technical_volume_price_divergence_score"], 38.0)
        self.assertEqual(result.final_state_summary["semantic_prompt_slots"]["semantic_priority"], 4)
        self.assertIn("policy_concept_conviction_score", result.final_state_summary["semantic_prompt_slots"])
        self.assertIn("capital_quality_stability_index", result.final_state_summary["semantic_prompt_slots"])
        self.assertIn("technical_signal_consistency_index", result.final_state_summary["semantic_prompt_slots"])
        self.assertIn("route_decision", result.final_state_summary)
        self.assertEqual(result.final_state_summary["analysis_mode"], "dry_run")
        self.assertEqual(result.final_state_summary["fallback_used"], False)
        self.assertEqual(result.final_state_summary["graph_config_snapshot"], {})
        self.assertIn("selected_analysts", result.final_state_summary["route_decision"])
        self.assertIn("semantic_flow_controls", result.final_state_summary["route_decision"])
        self.assertEqual(result.final_state_summary["route_decision"]["route_family"], "semantic_router_v1")
        self.assertEqual(
            result.final_state_summary["route_decision"]["semantic_flow_controls"]["analysis_priority"],
            "policy_leadership",
        )
        self.assertEqual(
            result.final_state_summary["route_decision"]["semantic_flow_controls"]["prompt_slot_mode"],
            "structured_semantic_payload",
        )
        self.assertIn("concept_overlap", result.final_state_summary["route_decision"]["analyst_focus"])
        self.assertIn("heat_quality_gap", result.final_state_summary["route_decision"]["analyst_focus"])

    def test_dry_run_with_real_analysis_enabled_records_fallback_reason(self):
        analyzer = DeepAnalyzer(config={"enable_real_deep_analysis": True})
        card = SignalCard(
            ticker="000001.SZ",
            raw_code="000001",
            exchange="SZ",
            company_name="平安银行",
            trade_date="2026-05-07",
            concept_tags=["政策模糊", "policy_keyword_fallback"],
            strategy_sources=["technical", "policy"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=72.0,
                    reason="technical",
                )
            ],
            trigger_reason="technical_trigger",
            initial_confidence=70.0,
            screening_score=68.0,
            evidence_snapshot={
                "policy_selection_tag": "policy_keyword_fallback",
                "capital_quality_tag": "capital_quality_speculative",
                "semantic_decision_summary": "dropped_reason: weak technical structure risk",
                "technical_structure_summary": "technical_structure: structure_risk=32.0 | consistency=39.0 | extension=11.0 | positive_days=42.0 | flags=trend_structure_extended,lost_ma20_support",
                "semantic_reason_payload": {
                    "decision": "dropped",
                    "summary": "dropped_reason: weak technical structure risk",
                    "semantic_priority": -4,
                    "reasons": ["technical_structure_risk"],
                    "policy": {"policy_strength": 0, "multi_concept_overlap_count": 0},
                    "capital": {"heat_quality_gap_score": 31.0, "risk_constraint_score": 38.0, "continuity_score": 40.0},
                    "technical": {
                        "structure_risk_score": 32.0,
                        "trend_consistency_score": 39.0,
                        "recent_extension_pct": 11.0,
                        "volume_confirmation_score": 40.0,
                        "breakout_quality_score": 43.0,
                        "volume_price_divergence_score": 37.0,
                    },
                },
                "cross_strategy_conflict": {"tier": "severe", "spread": 28.0, "dominant_strategy": "technical", "weakest_strategy": "policy"},
                "conflict_resolution": "policy_vs_technical",
            },
            risk_flags=["trend_structure_extended", "lost_ma20_support", "price_volume_divergence"],
        )

        with patch("tradingagents.screener.deep_analyzer.build_graph_config", return_value={"config_key": "x"}), \
            patch("tradingagents.screener.deep_analyzer.TradingAgentsGraph", side_effect=RuntimeError("graph unavailable")):
            result = analyzer.analyze(card, "2026-05-07")

        self.assertTrue(result.success)
        self.assertEqual(result.final_state_summary["analysis_mode"], "dry_run")
        self.assertTrue(result.final_state_summary["fallback_used"])
        self.assertIn("graph unavailable", result.final_state_summary["fallback_reason"])
        self.assertIn("route_decision", result.final_state_summary)
        self.assertEqual(result.final_state_summary["route_decision"]["debate_rounds"], "compressed")
        self.assertEqual(result.final_state_summary["route_decision"]["debate_risk_weight"], "high")
        self.assertEqual(result.final_state_summary["route_decision"]["selected_analysts"], ["market", "news", "fundamentals", "social"])
        self.assertTrue(result.final_state_summary["route_decision"]["semantic_flow_controls"]["force_risk_review"])
        self.assertEqual(result.final_state_summary["route_decision"]["analyst_focus"][-1], "technical_risk")
        self.assertIn("semantic_prompt_slots", result.final_state_summary)
        self.assertEqual(result.final_state_summary["semantic_prompt_slots"]["capital_heat_quality_gap_score"], 31.0)
        self.assertEqual(result.final_state_summary["route_decision"]["semantic_priority"], -4)
        self.assertIn("evidence_must_include", result.final_state_summary["semantic_execution_profile"])
        self.assertIn("response_style", result.final_state_summary["semantic_execution_profile"])

    def test_route_decision_reflects_policy_and_capital_focus(self):
        # H3 FIX: explicitly disable real analysis for route_decision tests
        analyzer = DeepAnalyzer(config={"enable_real_deep_analysis": False})
        card = SignalCard(
            ticker="600519.SH",
            raw_code="600519",
            exchange="SH",
            company_name="贵州茅台",
            trade_date="2026-05-07",
            concept_tags=["人工智能", "policy_top_stock", "capital_quality_high"],
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(strategy="technical", score=80.0, reason="technical"),
                SignalEvidence(strategy="policy", score=84.0, reason="policy"),
                SignalEvidence(strategy="smart_money", score=79.0, reason="smart money"),
            ],
            trigger_reason="policy_concept_top_pick",
            initial_confidence=87.0,
            screening_score=85.0,
            evidence_snapshot={
                "policy_selection_tag": "policy_top_stock",
                "capital_quality_tag": "capital_quality_high",
                "semantic_decision_summary": "retained_priority: concept top-stock gained priority",
                "technical_structure_summary": "technical_structure: structure_risk=72.0 | consistency=75.0 | extension=3.0 | positive_days=62.0 | flags=none",
                "semantic_reason_payload": {
                    "decision": "retained",
                    "summary": "retained_priority: concept top-stock gained priority",
                    "semantic_priority": 6,
                    "reasons": [],
                    "policy": {
                        "policy_strength": 3,
                        "primary_concept_score": 86.0,
                        "concept_competition_score": 83.0,
                        "multi_concept_overlap_count": 2,
                    },
                    "capital": {"heat_quality_gap_score": 8.0, "risk_constraint_score": 72.0, "continuity_score": 70.0},
                    "technical": {
                        "structure_risk_score": 72.0,
                        "trend_consistency_score": 75.0,
                        "recent_extension_pct": 3.0,
                        "volume_confirmation_score": 74.0,
                        "breakout_quality_score": 71.0,
                        "volume_price_divergence_score": 69.0,
                    },
                },
                "cross_strategy_conflict": {"tier": "aligned", "spread": 4.0, "dominant_strategy": "policy", "weakest_strategy": "technical"},
                "conflict_resolution": "none",
            },
        )

        semantic_context = analyzer._build_semantic_context(card)
        route_decision = analyzer._build_route_decision(card, semantic_context)

        self.assertEqual(route_decision["policy_role"], "policy_top_stock")
        self.assertIn("policy_board", route_decision["analyst_focus"])
        self.assertIn("capital_confirmation", route_decision["analyst_focus"])
        self.assertEqual(route_decision["debate_rounds"], "standard")
        self.assertEqual(route_decision["debate_risk_weight"], "normal")
        self.assertEqual(route_decision["conflict_tier"], "aligned")
        self.assertEqual(route_decision["selected_analysts"], ["news", "market", "social", "fundamentals"])
        self.assertEqual(route_decision["semantic_flow_controls"]["analysis_priority"], "policy_leadership")
        self.assertEqual(route_decision["semantic_priority"], 6)
        self.assertIn("concept_overlap", route_decision["analyst_focus"])
        self.assertEqual(semantic_context["prompt_slots"]["schema_name"], "screener.semantic_prompt_slots")

    def test_core_member_route_reduces_analyst_pipeline(self):
        # H3 FIX: explicitly disable real analysis for route_decision tests
        analyzer = DeepAnalyzer(config={"enable_real_deep_analysis": False})
        card = SignalCard(
            ticker="000002.SZ",
            raw_code="000002",
            exchange="SZ",
            company_name="000002.SZ",
            trade_date="2026-05-07",
            concept_tags=["新能源", "policy_core_member", "capital_quality_high"],
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(strategy="technical", score=76.0, reason="technical"),
                SignalEvidence(strategy="policy", score=80.0, reason="policy"),
                SignalEvidence(strategy="smart_money", score=77.0, reason="smart money"),
            ],
            trigger_reason="policy_core_case",
            initial_confidence=81.0,
            screening_score=79.0,
            evidence_snapshot={
                "policy_selection_tag": "policy_core_member",
                "capital_quality_tag": "capital_quality_high",
                "semantic_decision_summary": "retained_priority: concept core member kept as strong board constituent",
                "technical_structure_summary": "technical_structure: structure_risk=66.0 | consistency=68.0 | extension=2.0 | positive_days=59.0 | flags=none",
                "semantic_reason_payload": {
                    "decision": "retained",
                    "summary": "retained_priority: concept core member kept as strong board constituent",
                    "semantic_priority": 4,
                    "reasons": [],
                    "policy": {"policy_strength": 2, "multi_concept_overlap_count": 1},
                    "capital": {"heat_quality_gap_score": 6.0},
                    "technical": {"structure_risk_score": 66.0},
                },
                "cross_strategy_conflict": {"tier": "moderate", "spread": 8.0, "dominant_strategy": "policy", "weakest_strategy": "technical"},
                "conflict_resolution": "none",
            },
        )

        semantic_context = analyzer._build_semantic_context(card)
        route_decision = analyzer._build_route_decision(card, semantic_context)

        self.assertEqual(route_decision["selected_analysts"], ["news", "market", "fundamentals"])
        self.assertEqual(route_decision["semantic_flow_controls"]["analysis_priority"], "policy_supporting_member")

    def test_route_summary_can_be_reflected_into_graph_state(self):
        reflection_path = Path(__file__).resolve().parents[1] / "tradingagents" / "graph" / "reflection.py"
        spec = importlib.util.spec_from_file_location("reflection_module_for_test", reflection_path)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        Reflector = module.Reflector

        reflector = Reflector(quick_thinking_llm=type("LLM", (), {"invoke": lambda self, messages: type("R", (), {"content": "ok"})()})())
        current_state = {
            "orchestration": {
                "event_trail": [
                    {
                        "node": "market",
                        "phase": "analysis",
                        "compression_triggered": False,
                        "semantic_trigger_audit": {
                            "semantic_trigger_slots": {
                                "policy_role": "policy_top_stock",
                                "capital_quality": "capital_quality_high",
                            },
                            "semantic_trigger_reasons": [
                                "policy_role=policy_top_stock",
                                "capital_quality=capital_quality_high",
                                "analyst_focus:concept_overlap",
                            ],
                            "semantic_priority": 5,
                            "route_decision_snapshot": {
                                "route_family": "semantic_router_v1",
                                "policy_role": "policy_top_stock",
                            },
                        },
                    }
                ],
                "final_route": "direct",
                "final_reason": "semantic routing",
                "route_decision": {
                    "route_family": "semantic_router_v1",
                    "policy_role": "policy_top_stock",
                    "capital_quality": "capital_quality_high",
                    "debate_rounds": "standard",
                    "debate_risk_weight": "normal",
                    "selected_analysts": ["news", "market"],
                    "semantic_flow_controls": {"analysis_priority": "policy_leadership"},
                },
            },
            "ticker_info": {"ticker": "600519.SH", "segment": "consumer"},
        }

        summary = reflector.get_route_summary(current_state)
        self.assertEqual(summary["route_family"], "semantic_router_v1")
        self.assertEqual(summary["policy_role"], "policy_top_stock")
        self.assertEqual(summary["capital_quality"], "capital_quality_high")
        self.assertEqual(summary["selected_analysts"], ["news", "market"])
        self.assertIn("policy_role=policy_top_stock", summary["semantic_trigger_reasons"])
        self.assertEqual(summary["semantic_route_audit_trail"][0]["node"], "market")
        self.assertIn(
            "analyst_focus:concept_overlap",
            summary["semantic_route_audit_trail"][0]["semantic_trigger_reasons"],
        )


class DeepAnalyzerEnableFlagTests(unittest.TestCase):
    """P0 tests for H3: enable_real_deep_analysis flag resolution priority."""

    def test_default_enables_real_analysis(self):
        """H3 FIX: default (no config) should enable real analysis."""
        analyzer = DeepAnalyzer(config={})
        self.assertTrue(analyzer._enable_real_analysis)

    def test_config_false_disables_real_analysis(self):
        """H3 FIX: config=False should disable real analysis."""
        analyzer = DeepAnalyzer(config={"enable_real_deep_analysis": False})
        self.assertFalse(analyzer._enable_real_analysis)

    def test_config_true_enables_real_analysis(self):
        """H3 FIX: config=True should enable real analysis."""
        analyzer = DeepAnalyzer(config={"enable_real_deep_analysis": True})
        self.assertTrue(analyzer._enable_real_analysis)

    def test_env_var_true_enables_real_analysis(self):
        """H3 FIX: env var TRADINGAGENTS_DEEP_ANALYSIS_ENABLED=true enables real analysis."""
        import os
        original = os.environ.get("TRADINGAGENTS_DEEP_ANALYSIS_ENABLED")
        try:
            os.environ["TRADINGAGENTS_DEEP_ANALYSIS_ENABLED"] = "true"
            analyzer = DeepAnalyzer(config={})
            self.assertTrue(analyzer._enable_real_analysis)
        finally:
            if original is not None:
                os.environ["TRADINGAGENTS_DEEP_ANALYSIS_ENABLED"] = original
            else:
                os.environ.pop("TRADINGAGENTS_DEEP_ANALYSIS_ENABLED", None)

    def test_env_var_false_disables_real_analysis(self):
        """H3 FIX: env var TRADINGAGENTS_DEEP_ANALYSIS_ENABLED=false disables real analysis."""
        import os
        original = os.environ.get("TRADINGAGENTS_DEEP_ANALYSIS_ENABLED")
        try:
            os.environ["TRADINGAGENTS_DEEP_ANALYSIS_ENABLED"] = "false"
            analyzer = DeepAnalyzer(config={})
            self.assertFalse(analyzer._enable_real_analysis)
        finally:
            if original is not None:
                os.environ["TRADINGAGENTS_DEEP_ANALYSIS_ENABLED"] = original
            else:
                os.environ.pop("TRADINGAGENTS_DEEP_ANALYSIS_ENABLED", None)

    def test_config_overrides_env_var(self):
        """H3 FIX: config=True should override env var=False."""
        import os
        original = os.environ.get("TRADINGAGENTS_DEEP_ANALYSIS_ENABLED")
        try:
            os.environ["TRADINGAGENTS_DEEP_ANALYSIS_ENABLED"] = "false"
            analyzer = DeepAnalyzer(config={"enable_real_deep_analysis": True})
            self.assertTrue(analyzer._enable_real_analysis)
        finally:
            if original is not None:
                os.environ["TRADINGAGENTS_DEEP_ANALYSIS_ENABLED"] = original
            else:
                os.environ.pop("TRADINGAGENTS_DEEP_ANALYSIS_ENABLED", None)


if __name__ == "__main__":
    unittest.main()
