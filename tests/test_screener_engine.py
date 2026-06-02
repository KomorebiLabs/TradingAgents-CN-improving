import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tradingagents.screener.engine import ScreenerEngine
from tradingagents.screener.models import DeepAnalysisResult, SignalCard, SignalEvidence


class ScreenerEngineTests(unittest.TestCase):
    def test_engine_passes_config_to_universe_builder(self):
        with TemporaryDirectory() as temp_dir:
            config = {
                "data_cache_dir": temp_dir,
                "universe": {
                    "profile": "MVP",
                    "mode_profile_map": {
                        "MVP": "MVP",
                        "EXTENDED": "EXTENDED",
                        "EXPERIMENTAL": "EXPERIMENTAL",
                    },
                },
            }

            with patch("tradingagents.screener.engine.validate_screener_run", return_value=(True, [])), \
                patch("tradingagents.screener.engine.build_screening_universe") as mock_universe, \
                patch("tradingagents.screener.engine.merge_signal_cards", return_value=([], [])), \
                patch("tradingagents.screener.engine.write_run_artifacts"), \
                patch("tradingagents.screener.engine.check_data_consistency", return_value=[]):
                mock_data_access = type("DataAccess", (), {})()
                mock_data_access.validate_interface_assumptions = lambda trade_date=None: {
                    "request_stats": {"total_requests": 0, "failed_requests": 0},
                    "warnings": [],
                }
                mock_universe.return_value = type(
                    "Universe",
                    (),
                    {
                        "tickers": ["000300"],
                        "metadata": {
                            "mode": "EXPERIMENTAL",
                            "profile": "EXPERIMENTAL",
                            "cache_key": "experimental_index_union",
                            "constituent_expansion_ready": True,
                        },
                    },
                )()

                strategy_outcome = type("Outcome", (), {"cards": [], "status": "ready", "warnings": []})()
                strategy_stub = type("Strategy", (), {"run": lambda self, universe, trade_date: strategy_outcome})()
                analyzer_stub = type("Analyzer", (), {"analyze_top_candidates": lambda self, cards, trade_date: []})()

                engine = ScreenerEngine(config=config)
                with patch.object(engine, "_build_data_access", return_value=mock_data_access), \
                    patch.object(engine, "_build_strategies", return_value=(strategy_stub, strategy_stub, strategy_stub)), \
                    patch.object(engine, "_build_deep_analyzer", return_value=analyzer_stub):
                    result = engine.run(
                        mode="EXPERIMENTAL",
                        trade_date="2026-05-07",
                        enable_deep_analysis=True,
                        persist_outputs=False,
                    )

            self.assertEqual(result.mode, "EXPERIMENTAL")
            mock_universe.assert_called_once()
            _, universe_kwargs = mock_universe.call_args
            self.assertEqual(universe_kwargs["mode"], "EXPERIMENTAL")
            self.assertEqual(universe_kwargs["config"], config)
            self.assertEqual(result.universe_metadata["profile"], "EXPERIMENTAL")
            self.assertEqual(result.universe_metadata["cache_key"], "experimental_index_union")

    def test_engine_builds_runtime_config_from_screener_config(self):
        engine = ScreenerEngine(
            config={
                "run_time": {
                    "earliest": "17:00",
                    "latest_next_day": "08:30",
                    "allow_weekend": True,
                    "allow_non_trading_day_override": True,
                    "allow_experimental_intraday": False,
                    "max_data_age_days": 5,
                }
            }
        )

        runtime_config = engine._build_runtime_config()

        self.assertEqual(runtime_config.earliest_run_time, "17:00")
        self.assertEqual(runtime_config.latest_next_day, "08:30")
        self.assertTrue(runtime_config.allow_weekend)
        self.assertTrue(runtime_config.allow_non_trading_day_override)
        self.assertFalse(runtime_config.allow_experimental_intraday)
        self.assertEqual(runtime_config.max_data_age_days, 5)

    def test_engine_exposes_semantic_sorting_and_structure_explanations(self):
        strong = SignalCard(
            ticker="600519.SH",
            raw_code="600519",
            exchange="SH",
            company_name="贵州茅台",
            trade_date="2026-05-07",
            sector_tags=["policy_driven"],
            concept_tags=["人工智能", "policy_top_stock"],
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=80.0,
                    reason="technical",
                    raw_metrics={
                        "structure_risk_score": 72.0,
                        "trend_consistency_score": 75.0,
                        "recent_extension_pct": 3.0,
                        "positive_days_ratio_pct": 62.0,
                        "close_above_ma20": True,
                        "close_above_ma60": True,
                    },
                ),
                SignalEvidence(
                    strategy="policy",
                    score=84.0,
                    reason="policy",
                    raw_metrics={
                        "stock_selection_tag": "policy_top_stock",
                        "relative_rank_score": 91.0,
                        "board_leadership_score": 89.0,
                        "concept_linkage_boundary": {
                            "linkage_mode": "verified_constituent_cross_hit",
                            "confidence_tier": "high",
                        },
                    },
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=79.0,
                    reason="smart money",
                    raw_metrics={
                        "capital_quality_tag": "capital_quality_high",
                        "capital_quality_summary": "high-quality persistent flow",
                    },
                ),
            ],
            trigger_reason="policy_concept_top_pick",
            initial_confidence=87.0,
            screening_score=85.0,
            evidence_snapshot={
                "semantic_decision_summary": (
                    "retained_priority: concept top-stock gained priority; "
                    "technical_structure: structure_risk=72.0 | consistency=75.0 | extension=3.0 | "
                    "positive_days=62.0 | flags=none"
                ),
                "technical_structure_summary": (
                    "technical_structure: structure_risk=72.0 | consistency=75.0 | extension=3.0 | "
                    "positive_days=62.0 | flags=none"
                ),
                "semantic_reason_payload": {
                    "decision": "retained",
                    "summary": "retained_priority: concept top-stock gained priority",
                    "policy": {"policy_selection_tag": "policy_top_stock"},
                },
            },
        )

        weak = SignalCard(
            ticker="000001.SZ",
            raw_code="000001",
            exchange="SZ",
            company_name="平安银行",
            trade_date="2026-05-07",
            sector_tags=["capital_flow"],
            concept_tags=["政策模糊"],
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=68.0,
                    reason="technical",
                    raw_metrics={
                        "structure_risk_score": 31.0,
                        "trend_consistency_score": 39.0,
                        "recent_extension_pct": 11.0,
                        "positive_days_ratio_pct": 42.0,
                        "close_above_ma20": False,
                        "close_above_ma60": False,
                    },
                ),
                SignalEvidence(
                    strategy="policy",
                    score=66.0,
                    reason="policy",
                    raw_metrics={
                        "stock_selection_tag": "policy_keyword_fallback",
                        "relative_rank_score": 54.0,
                        "board_leadership_score": 49.0,
                    },
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=64.0,
                    reason="smart money",
                    raw_metrics={
                        "capital_quality_tag": "capital_quality_speculative",
                        "capital_quality_summary": "speculative flow",
                    },
                ),
            ],
            trigger_reason="policy_keyword_fallback",
            initial_confidence=64.0,
            screening_score=67.0,
            evidence_snapshot={
                "technical_structure_summary": (
                    "technical_structure: structure_risk=31.0 | consistency=39.0 | extension=11.0 | "
                    "positive_days=42.0 | flags=trend_structure_extended,trend_consistency_weak,lost_ma20_support"
                ),
                "semantic_reason_payload": {
                    "decision": "dropped",
                    "summary": "dropped_reason: weak technical structure risk",
                    "technical": {"structure_risk_score": 31.0},
                },
            },
        )

        dropped_item = weak.model_dump()
        dropped_item.update(
            {
                "reasons": ["technical_structure_risk"],
                "stage": "hard_filter",
                "policy_selection_tag": "policy_keyword_fallback",
                "capital_quality_tag": "capital_quality_speculative",
                "capital_quality_summary": "speculative flow",
                "technical_structure_summary": weak.evidence_snapshot["technical_structure_summary"],
                "semantic_decision_summary": "dropped_reason: weak technical structure risk",
                "semantic_reason_payload": weak.evidence_snapshot["semantic_reason_payload"],
            }
        )

        engine = ScreenerEngine(config={"candidates": {"same_sector_limit": 2, "max_output": 3}, "thresholds": {}})

        with patch("tradingagents.screener.engine.validate_screener_run", return_value=(True, [])), \
            patch("tradingagents.screener.engine.build_screening_universe") as mock_universe, \
            patch("tradingagents.screener.engine.merge_signal_cards", return_value=([strong], [dropped_item])) as mock_merge, \
            patch("tradingagents.screener.engine.write_run_artifacts"), \
            patch("tradingagents.screener.engine.check_data_consistency", return_value=[]):
            mock_data_access = type("DataAccess", (), {})()
            mock_data_access.validate_interface_assumptions = lambda trade_date=None: {
                "request_stats": {"total_requests": 0, "failed_requests": 0},
                "warnings": [],
            }
            mock_universe.return_value = type(
                "Universe",
                (),
                {
                    "tickers": ["600519", "000001"],
                    "metadata": {"profile": "EXPERIMENTAL", "cache_key": "experimental_index_union"},
                },
            )()

            strategy_outcome = type("Outcome", (), {"cards": [strong, weak], "status": "ready", "warnings": []})()
            strategy_stub = type("Strategy", (), {"run": lambda self, universe, trade_date: strategy_outcome})()
            analyzer_stub = type(
                "Analyzer",
                (),
                {
                    "analyze_top_candidates": lambda self, cards, trade_date: [
                        DeepAnalysisResult(
                            signal_card=strong,
                            success=True,
                            final_decision="DRY_RUN",
                            elapsed_seconds=0.01,
                            final_state_summary={
                                "analysis_mode": "dry_run",
                                "route_decision": {
                                    "route_family": "semantic_router_v1",
                                    "policy_role": "policy_top_stock",
                                    "capital_quality": "capital_quality_high",
                                    "selected_analysts": ["news", "market", "social", "fundamentals"],
                                    "semantic_flow_controls": {"debate_round_limit": 2},
                                },
                                "semantic_trigger_audit": {
                                    "semantic_trigger_reasons": ["policy_role=policy_top_stock"],
                                },
                                "semantic_execution_profile": {
                                    "route_behavior_tag": "top_stock_priority",
                                    "response_style": "thesis_first",
                                    "conclusion_mode": "leader_continuation_vs_failure",
                                    "evidence_must_include": ["concept_conviction_validation"],
                                },
                                "fallback_used": False,
                                "fallback_reason": "",
                            },
                        )
                    ]
                },
            )()

            with patch.object(engine, "_build_data_access", return_value=mock_data_access), \
                patch.object(engine, "_build_strategies", return_value=(strategy_stub, strategy_stub, strategy_stub)), \
                patch.object(engine, "_build_deep_analyzer", return_value=analyzer_stub):
                result = engine.run(
                    mode="EXPERIMENTAL",
                    trade_date="2026-05-07",
                    enable_deep_analysis=True,
                    persist_outputs=False,
                )

        self.assertEqual(result.metrics["final_candidates"], 1)
        # A5: retained semantic summaries/payloads are in card.evidence_snapshot, not metrics
        # A5: semantic_home_chain is the single source of truth for the homepage
        self.assertIn("semantic_home_chain", result.metrics)
        self.assertEqual(
            result.metrics["semantic_home_chain"]["600519.SH"]["route"]["route_family"],
            "semantic_router_v1",
        )
        # A6 contract guard: semantic_home_chain must keep stable typed structure
        home_chain_item = result.metrics["semantic_home_chain"]["600519.SH"]
        self.assertIsInstance(home_chain_item["trigger"], list)
        self.assertIsInstance(home_chain_item["route"], dict)
        self.assertIsInstance(home_chain_item["execution"], dict)
        self.assertIsInstance(home_chain_item["decision"], str)
        # A5: verify new threshold snapshot fields are populated
        self.assertIn("threshold_snapshot", result.metrics)
        self.assertIn("conflict_priority_snapshot", result.metrics)
        self.assertIn("merger_threshold_snapshot", result.metrics)
        self.assertIn("effective_config_used", result.metrics)
        # Dropped candidates are in result.dropped_candidates, not metrics
        self.assertGreater(len(result.dropped_candidates), 0)
        mock_merge.assert_called_once()

    def test_stage_a_audit_in_metrics(self):
        """P5-6: Verify Stage A audit info is present in metrics."""
        with TemporaryDirectory() as temp_dir:
            config = {
                "data_cache_dir": temp_dir,
                "universe": {"profile": "MVP"},
            }

            with patch("tradingagents.screener.engine.validate_screener_run", return_value=(True, [])), \
                patch("tradingagents.screener.engine.build_screening_universe") as mock_universe, \
                patch("tradingagents.screener.engine.merge_signal_cards", return_value=([], [])), \
                patch("tradingagents.screener.engine.write_run_artifacts"), \
                patch("tradingagents.screener.engine.check_data_consistency", return_value=[]):
                mock_data_access = type("DataAccess", (), {})()
                mock_data_access.validate_interface_assumptions = lambda trade_date=None: {
                    "request_stats": {"total_requests": 0, "failed_requests": 0},
                    "warnings": [],
                }
                # Mock fetch_hist to return valid data
                mock_hist = type("Hist", (), {"empty": False, "__len__": lambda self: 50})()
                mock_data_access.fetch_hist = lambda ticker, start, end, adjust=None: mock_hist

                mock_universe.return_value = type(
                    "Universe",
                    (),
                    {
                        "tickers": ["000001", "600519"],
                        "metadata": {"mode": "MVP", "profile": "MVP"},
                    },
                )()

                strategy_outcome = type("Outcome", (), {"cards": [], "status": "ready", "warnings": []})()
                strategy_stub = type("Strategy", (), {"run": lambda self, universe, trade_date: strategy_outcome})()
                analyzer_stub = type("Analyzer", (), {"analyze_top_candidates": lambda self, cards, trade_date: []})()

                engine = ScreenerEngine(config=config)
                with patch.object(engine, "_build_data_access", return_value=mock_data_access), \
                    patch.object(engine, "_build_strategies", return_value=(strategy_stub, strategy_stub, strategy_stub)), \
                    patch.object(engine, "_build_deep_analyzer", return_value=analyzer_stub):
                    result = engine.run(
                        mode="MVP",
                        trade_date="2026-05-07",
                        enable_deep_analysis=False,
                        persist_outputs=False,
                    )

            # P5-6: Verify Stage A audit structure
            stagea_audit = result.metrics.get("effective_config_used", {}).get("stagea_audit")
            self.assertIsNotNone(stagea_audit, "Stage A audit should be present")
            self.assertIn("stagea_input_count", stagea_audit)
            self.assertIn("stagea_pass_count", stagea_audit)
            self.assertIn("stagea_drop_count", stagea_audit)
            self.assertIn("stagea_drop_breakdown", stagea_audit)
            self.assertIn("stageb_input_count", stagea_audit)
            self.assertTrue(stagea_audit.get("stagea_enabled"))

            # P5-6: Verify stagea_pass_count >= stageb_input_count
            self.assertGreaterEqual(stagea_audit["stagea_pass_count"], stagea_audit["stageb_input_count"])

    def test_stage_a_filters_stocks(self):
        """P5-6: Verify Stage A audit information is correctly populated."""
        import pandas as pd
        with TemporaryDirectory() as temp_dir:
            config = {
                "data_cache_dir": temp_dir,
                "universe": {"profile": "CUSTOM"},
            }

            with patch("tradingagents.screener.engine.validate_screener_run", return_value=(True, [])), \
                patch("tradingagents.screener.engine.build_screening_universe") as mock_universe, \
                patch("tradingagents.screener.engine.merge_signal_cards", return_value=([], [])), \
                patch("tradingagents.screener.engine.write_run_artifacts"), \
                patch("tradingagents.screener.engine.check_data_consistency", return_value=[]):
                mock_data_access = type("DataAccess", (), {})()
                mock_data_access.validate_interface_assumptions = lambda trade_date=None: {
                    "request_stats": {"total_requests": 0, "failed_requests": 0},
                    "warnings": [],
                }
                # Mock DataFrame - all stocks have valid history
                mock_hist = pd.DataFrame({
                    "turnover": [5.0, 6.0, 7.0, 8.0, 9.0],
                    "pct_change": [1.0, 2.0, 0.5, -1.0, 1.5],
                })
                mock_data_access.fetch_hist = lambda ticker, start, end, adjust=None: mock_hist

                mock_universe.return_value = type(
                    "Universe",
                    (),
                    {
                        "tickers": ["000001", "600519", "300750"],
                        "metadata": {"mode": "CUSTOM", "profile": "CUSTOM"},
                    },
                )()

                strategy_outcome = type("Outcome", (), {"cards": [], "status": "ready", "warnings": []})()
                strategy_stub = type("Strategy", (), {"run": lambda self, universe, trade_date: strategy_outcome})()
                analyzer_stub = type("Analyzer", (), {"analyze_top_candidates": lambda self, cards, trade_date: []})()

                engine = ScreenerEngine(config=config)
                with patch.object(engine, "_build_data_access", return_value=mock_data_access), \
                    patch.object(engine, "_build_strategies", return_value=(strategy_stub, strategy_stub, strategy_stub)), \
                    patch.object(engine, "_build_deep_analyzer", return_value=analyzer_stub):
                    result = engine.run(
                        mode="CUSTOM",
                        trade_date="2026-05-07",
                        enable_deep_analysis=False,
                        persist_outputs=False,
                    )

            # P5-6: Verify Stage A audit structure and consistency
            stagea_audit = result.metrics.get("effective_config_used", {}).get("stagea_audit")
            self.assertIsNotNone(stagea_audit)
            # Input should equal universe size
            self.assertEqual(stagea_audit["stagea_input_count"], 3)
            # Pass + Drop should equal Input
            self.assertEqual(
                stagea_audit["stagea_pass_count"] + stagea_audit["stagea_drop_count"],
                stagea_audit["stagea_input_count"]
            )
            # Stage B input should equal Stage A pass count
            self.assertEqual(stagea_audit["stageb_input_count"], stagea_audit["stagea_pass_count"])


if __name__ == "__main__":
    unittest.main()
