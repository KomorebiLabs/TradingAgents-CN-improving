"""Plan4 A6: Minimal contract assertions to prevent key field drift.

These tests lock down the structural contracts that the Screener Phase
must maintain. They are intentionally minimal: 1-2 assertion groups,
not an exhaustive suite.
"""

import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tradingagents.screener.engine import ScreenerEngine
from tradingagents.screener.models import DeepAnalysisResult, ScreeningResult, SignalCard, SignalEvidence
from tradingagents.screener.config import SCREENER_CONFIG, SCREENER_THRESHOLDS
from tradingagents.screener.strategies import PolicyStrategy, SmartMoneyStrategy, TechnicalStrategy


def _build_config_with_threshold(drop_speculative_score_floor: float) -> dict:
    """Build a SCREENER_CONFIG copy with a specific drop_speculative_score_floor value."""
    import copy
    cfg = copy.deepcopy(SCREENER_CONFIG)
    cfg.setdefault("screener_thresholds", {})["drop_speculative_score_floor"] = drop_speculative_score_floor
    return cfg


def _mock_deep_result(ticker: str) -> DeepAnalysisResult:
    """Fabricate a minimal DeepAnalysisResult with known semantic fields."""
    card = SignalCard(
        ticker=ticker,
        raw_code="000001",
        exchange="SZ",
        company_name="TestCorp",
        trade_date="2026-01-01",
        strategy_sources=["technical", "policy", "smart_money"],
        signal_breakdown=[
            SignalEvidence(
                strategy="technical",
                score=80.0,
                reason="test",
                raw_metrics={
                    "threshold_snapshot": {
                        "source": "technical",
                        "signal_consistency_low": 45.0,
                        "thresholds_used": {"signal_consistency_low": 45.0},
                    }
                },
            )
        ],
        trigger_reason="test_trigger",
        initial_confidence=78.0,
        screening_score=80.0,
        evidence_snapshot={
            "threshold_snapshot": {
                "source": "technical",
                "signal_consistency_low": 45.0,
                "thresholds_used": {"signal_consistency_low": 45.0},
            },
        },
    )
    return DeepAnalysisResult(
        signal_card=card,
        success=True,
        final_decision="BUY",
        elapsed_seconds=10.0,
        final_state_summary={
            "analysis_mode": "standard",
            "semantic_trigger_audit": {
                "semantic_trigger_reasons": ["policy_top_stock", "smart_money_persistent"],
            },
            "route_decision": {
                "route_family": "standard",
                "policy_role": "primary",
                "capital_quality": "high",
                "conflict_tier": "aligned",
                "selected_analysts": ["bullish_analyst", "risk_analyst"],
                "analyst_focus": ["earnings", "risk"],
                "debate_rounds": 2,
            },
            "semantic_execution_profile": {
                "route_behavior_tag": "full",
                "response_style": "detailed",
                "conclusion_mode": "thesis_first",
                "evidence_must_include": ["valuation", "risk"],
            },
        },
    )


def _mock_card(ticker: str, raw_code: str, exchange: str, company_name: str) -> SignalCard:
    """Fabricate a minimal SignalCard for merge_signal_cards mock."""
    return SignalCard(
        ticker=ticker,
        raw_code=raw_code,
        exchange=exchange,
        company_name=company_name,
        trade_date="2026-01-01",
        strategy_sources=["technical"],
        signal_breakdown=[
            SignalEvidence(
                strategy="technical",
                score=80.0,
                reason="test",
                raw_metrics={
                    "threshold_snapshot": {
                        "source": "technical",
                        "signal_consistency_low": 45.0,
                        "thresholds_used": {"signal_consistency_low": 45.0},
                    }
                },
            )
        ],
        trigger_reason="test_trigger",
        initial_confidence=78.0,
        screening_score=80.0,
        evidence_snapshot={
            "threshold_snapshot": {
                "source": "technical",
                "signal_consistency_low": 45.0,
                "thresholds_used": {"signal_consistency_low": 45.0},
            },
        },
    )


def _build_mock_engine_run(config=None):
    config = config or {}
    config.setdefault("data_cache_dir", TemporaryDirectory().name)
    return ScreenerEngine(config)


class ScreenerContractTests(unittest.TestCase):
    """A6 contract assertions for Screener Phase."""

    def test_semantic_home_chain_contract(self):
        """Assert semantic_home_chain has correct 4-key structure for each ticker."""
        engine = _build_mock_engine_run()
        deep_results = [_mock_deep_result("000001.SZ"), _mock_deep_result("600000.SH")]

        with patch("tradingagents.screener.engine.validate_screener_run", return_value=(True, [])), \
             patch("tradingagents.screener.engine.build_screening_universe") as mock_universe, \
             patch("tradingagents.screener.engine.merge_signal_cards") as mock_merge, \
             patch("tradingagents.screener.engine.write_run_artifacts", return_value={}), \
             patch("tradingagents.screener.engine.check_data_consistency", return_value=[]), \
             patch("tradingagents.screener.deep_analyzer.DeepAnalyzer") as mock_da_class:
            mock_universe.return_value = type("Universe", (), {
                "tickers": ["000001"],
                "metadata": {"mode": "MVP", "profile": "MVP", "cache_key": "test", "constituent_expansion_ready": False},
            })()
            mock_da_instance = type("DA", (), {
                "validate_interface_assumptions": lambda self, trade_date=None: {
                    "request_stats": {"total_requests": 0, "failed_requests": 0},
                    "warnings": [],
                },
                "analyze_top_candidates": lambda self, cards, trade_date: deep_results,
            })()
            mock_da_class.return_value = mock_da_instance
            mock_data_access = type("DAccess", (), {
                "validate_interface_assumptions": lambda self, trade_date=None: {
                    "request_stats": {"total_requests": 0, "failed_requests": 0},
                    "warnings": [],
                },
            })()

            # Return a non-empty merged list so enable_deep_analysis path is taken.
            mock_merge.return_value = (
                [_mock_card("000001.SZ", "000001", "SZ", "TestCorp")],
                [],
            )

            # Patch _build_data_access so the engine uses our mock (for NameResolver).
            with patch.object(engine, "_build_data_access", return_value=mock_data_access):
                result = engine.run(enable_deep_analysis=True, persist_outputs=False)

            chain = result.metrics.get("semantic_home_chain", {})
            self.assertIsInstance(chain, dict, "semantic_home_chain must be a dict")
            self.assertGreater(len(chain), 0, "semantic_home_chain must not be empty when deep analysis ran")

            for ticker, payload in chain.items():
                with self.subTest(ticker=ticker):
                    self.assertIsInstance(payload, dict, f"{ticker}: payload must be a dict")
                    self.assertIn("trigger", payload, f"{ticker}: missing 'trigger' key")
                    self.assertIn("route", payload, f"{ticker}: missing 'route' key")
                    self.assertIn("execution", payload, f"{ticker}: missing 'execution' key")
                    self.assertIn("decision", payload, f"{ticker}: missing 'decision' key")
                    self.assertIsInstance(payload["trigger"], list, f"{ticker}: trigger must be a list")
                    self.assertIsInstance(payload["route"], dict, f"{ticker}: route must be a dict")
                    self.assertIsInstance(payload["execution"], dict, f"{ticker}: execution must be a dict")
                    # route should contain key routing fields
                    self.assertIn("route_family", payload["route"])
                    self.assertIn("policy_role", payload["route"])
                    self.assertIn("capital_quality", payload["route"])

    def test_semantic_audit_chain_removed(self):
        """Assert legacy alias semantic_audit_chain is not written into metrics."""
        from unittest.mock import MagicMock

        engine = _build_mock_engine_run()
        deep_results = [_mock_deep_result("000001.SZ")]

        # Create mock outcomes for all strategies
        mock_technical_outcome = MagicMock()
        mock_technical_outcome.cards = []
        mock_technical_outcome.status = "ready"

        mock_policy_outcome = MagicMock()
        mock_policy_outcome.cards = []
        mock_policy_outcome.status = "ready"

        mock_smart_money_outcome = MagicMock()
        mock_smart_money_outcome.cards = []
        mock_smart_money_outcome.status = "ready"

        with patch("tradingagents.screener.engine.validate_screener_run", return_value=(True, [])), \
             patch("tradingagents.screener.engine.build_screening_universe") as mock_universe, \
             patch("tradingagents.screener.engine.merge_signal_cards", return_value=([], [])), \
             patch("tradingagents.screener.engine.write_run_artifacts", return_value={}), \
             patch("tradingagents.screener.engine.check_data_consistency", return_value=[]), \
             patch.object(TechnicalStrategy, "run", return_value=mock_technical_outcome), \
             patch.object(PolicyStrategy, "run", return_value=mock_policy_outcome), \
             patch.object(SmartMoneyStrategy, "run", return_value=mock_smart_money_outcome):
            mock_universe.return_value = type("Universe", (), {
                "tickers": ["000001"],
                "metadata": {"mode": "MVP", "profile": "MVP", "cache_key": "test", "constituent_expansion_ready": False},
            })()
            mock_da = type("DA", (), {
                "validate_interface_assumptions": lambda self, trade_date=None: {
                    "request_stats": {"total_requests": 0, "failed_requests": 0},
                    "warnings": [],
                },
            })()

            result = engine.run(enable_deep_analysis=False, persist_outputs=False)
            self.assertNotIn(
                "semantic_audit_chain",
                result.metrics,
                "semantic_audit_chain is a legacy alias and must not appear in metrics"
            )

    def test_threshold_snapshot_in_output(self):
        """Assert all strategy thresholds appear in engine metrics and card evidence_snapshot."""
        with patch("tradingagents.screener.engine.validate_screener_run", return_value=(True, [])), \
             patch("tradingagents.screener.engine.build_screening_universe") as mock_universe, \
             patch("tradingagents.screener.engine.merge_signal_cards") as mock_merge, \
             patch("tradingagents.screener.engine.write_run_artifacts", return_value={}), \
             patch("tradingagents.screener.engine.check_data_consistency", return_value=[]):
            mock_universe.return_value = type("Universe", (), {
                "tickers": ["000001"],
                "metadata": {"mode": "MVP", "profile": "MVP", "cache_key": "test", "constituent_expansion_ready": False},
            })()
            mock_merge.return_value = ([], [])
            mock_data_access = type("DAccess", (), {
                "validate_interface_assumptions": lambda self, trade_date=None: {
                    "request_stats": {"total_requests": 0, "failed_requests": 0},
                    "warnings": [],
                },
            })()
            engine = _build_mock_engine_run()
            with patch.object(engine, "_build_data_access", return_value=mock_data_access):
                result = engine.run(enable_deep_analysis=False, persist_outputs=False)

            # ScreenerMetrics should contain threshold_snapshot
            ts = result.metrics.get("threshold_snapshot", {})
            self.assertIsInstance(ts, dict, "threshold_snapshot must be a dict")
            self.assertIn("strategies", ts, "threshold_snapshot.strategies must exist")
            self.assertIsInstance(ts["strategies"], dict, "threshold_snapshot.strategies must be a dict")

            # Each strategy should have its threshold_snapshot
            for strategy_name in ("technical", "policy", "smart_money"):
                strat_ts = ts["strategies"].get(strategy_name, {})
                self.assertIn("source", strat_ts, f"{strategy_name}: threshold_snapshot must have 'source'")

    def test_merger_threshold_snapshot_in_evidence(self):
        """Assert merger produces merger_threshold_snapshot in merged card evidence."""
        from tradingagents.screener.merger import merge_signal_cards
        from tradingagents.screener.models import SignalCard, SignalEvidence

        card = SignalCard(
            ticker="000001.SZ",
            raw_code="000001",
            exchange="SZ",
            company_name="TestCorp",
            trade_date="2026-01-01",
            strategy_sources=["technical", "policy"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=80.0,
                    reason="test",
                    raw_metrics={
                        "threshold_snapshot": {
                            "source": "technical",
                            "signal_consistency_low": 45.0,
                        }
                    },
                )
            ],
            trigger_reason="test",
            initial_confidence=78.0,
            screening_score=80.0,
            evidence_snapshot={
                "threshold_snapshot": {
                    "source": "technical",
                    "signal_consistency_low": 45.0,
                },
            },
        )

        retained, dropped = merge_signal_cards([card], mode="MVP", config=SCREENER_CONFIG)
        self.assertEqual(len(retained), 1, "Should retain one card")
        merger_ts = retained[0].evidence_snapshot.get("merger_threshold_snapshot", {})
        self.assertIsInstance(merger_ts, dict, "merger_threshold_snapshot must exist in merged card evidence")
        self.assertIn("merger_thresholds", merger_ts, "merger_threshold_snapshot must contain merger_thresholds")
        self.assertIn("conflict_priority_overrides", merger_ts, "merger_threshold_snapshot must contain conflict_priority_overrides")

    def test_conflict_priority_from_config_not_hardcoded(self):
        """Assert conflict_priority values come from SCREENER_CONFIG, not hardcoded."""
        from tradingagents.screener.merger import DEFAULT_CONFLICT_PRIORITY

        # Check that DEFAULT_CONFLICT_PRIORITY is not empty (was derived from SCREENER_CONFIG)
        self.assertGreater(len(DEFAULT_CONFLICT_PRIORITY), 0, "DEFAULT_CONFLICT_PRIORITY must be derived from SCREENER_CONFIG")
        # Check a known config value
        self.assertEqual(
            DEFAULT_CONFLICT_PRIORITY.get("aligned_spread_max"),
            SCREENER_CONFIG.get("conflict_priority", {}).get("aligned_spread_max"),
            "aligned_spread_max must match SCREENER_CONFIG"
        )

    def test_screener_metrics_contains_required_fields(self):
        """Assert ScreenerMetrics model has all required A5 fields after engine run."""
        from tradingagents.screener.models import ScreenerMetrics

        # Verify the model has the new fields (A5 expansion)
        model_fields = ScreenerMetrics.model_fields
        self.assertIn("threshold_snapshot", model_fields, "ScreenerMetrics must have threshold_snapshot field")
        self.assertIn("conflict_priority_snapshot", model_fields, "ScreenerMetrics must have conflict_priority_snapshot field")
        self.assertIn("merger_threshold_snapshot", model_fields, "ScreenerMetrics must have merger_threshold_snapshot field")
        self.assertIn("effective_config_used", model_fields, "ScreenerMetrics must have effective_config_used field")

    def test_no_duplicate_semantic_chain_in_metrics(self):
        """Assert metrics does not contain redundant aliases for semantic_home_chain."""
        with patch("tradingagents.screener.engine.validate_screener_run", return_value=(True, [])), \
             patch("tradingagents.screener.engine.build_screening_universe") as mock_universe, \
             patch("tradingagents.screener.engine.merge_signal_cards") as mock_merge, \
             patch("tradingagents.screener.engine.write_run_artifacts", return_value={}), \
             patch("tradingagents.screener.engine.check_data_consistency", return_value=[]):
            mock_universe.return_value = type("Universe", (), {
                "tickers": ["000001"],
                "metadata": {"mode": "MVP", "profile": "MVP", "cache_key": "test", "constituent_expansion_ready": False},
            })()
            mock_merge.return_value = ([], [])
            mock_data_access = type("DAccess", (), {
                "validate_interface_assumptions": lambda self, trade_date=None: {
                    "request_stats": {"total_requests": 0, "failed_requests": 0},
                    "warnings": [],
                },
            })()
            engine = _build_mock_engine_run()
            with patch.object(engine, "_build_data_access", return_value=mock_data_access):
                result = engine.run(enable_deep_analysis=False, persist_outputs=False)
            metrics_keys = list(result.metrics.keys())

            # These are the redundant aliases that should NOT exist (A5 cleanup)
            redundant_aliases = [
                "retained_semantic_summaries",
                "retained_semantic_payloads",
                "dropped_semantic_summaries",
                "dropped_semantic_payloads",
                "deep_route_summaries",
                "semantic_trigger_audit_summary",
                "semantic_execution_profile_summary",
            ]
            for alias in redundant_aliases:
                self.assertNotIn(
                    alias,
                    metrics_keys,
                    f"'{alias}' is a redundant alias and must not appear in metrics"
                )

    def test_merger_threshold_snapshot_reflects_config_not_hardcoded(self):
        """A6: Assert merger uses SCREENER_THRESHOLDS values, not hardcoded.

        Verifies that SCREENER_THRESHOLDS values are consistent with SCREENER_CONFIG["screener_thresholds"],
        and that the merger_threshold_snapshot includes these values for audit traceability.
        """
        from tradingagents.screener.merger import merge_signal_cards
        from tradingagents.screener.models import SignalCard, SignalEvidence

        # A card with no risk flags (clean retention path)
        card = SignalCard(
            ticker="000001.SZ",
            raw_code="000001",
            exchange="SZ",
            company_name="TestCorp",
            trade_date="2026-01-01",
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=80.0,
                    reason="test",
                    raw_metrics={
                        "signal_consistency_index": 55.0,
                        "threshold_snapshot": {"source": "technical", "signal_consistency_low": 45.0},
                    },
                ),
                SignalEvidence(
                    strategy="policy",
                    score=75.0,
                    reason="test",
                    raw_metrics={
                        "concept_conviction_score": 65.0,
                        "threshold_snapshot": {"source": "policy", "concept_conviction_low": 52.0},
                    },
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=70.0,
                    reason="test",
                    raw_metrics={
                        "quality_stability_index": 55.0,
                        "threshold_snapshot": {"source": "smart_money", "quality_stability_low": 48.0},
                    },
                ),
            ],
            trigger_reason="test",
            initial_confidence=80.0,
            screening_score=80.0,
            evidence_snapshot={},
            concept_tags=["policy_top_stock"],
            sector_tags=["capital_flow"],
            risk_flags=[],
        )

        retained, dropped = merge_signal_cards([card], mode="MVP", config=SCREENER_CONFIG)
        self.assertEqual(len(retained), 1)

        merger_ts = retained[0].evidence_snapshot.get("merger_threshold_snapshot", {})
        screener_thresholds_used = merger_ts.get("screener_thresholds", {})

        # Verify merger receives these threshold values (not hardcoded)
        self.assertEqual(
            screener_thresholds_used.get("drop_speculative_score_floor"),
            SCREENER_THRESHOLDS.get("drop_speculative_score_floor"),
            "drop_speculative_score_floor in screener_thresholds must match SCREENER_THRESHOLDS"
        )
        self.assertEqual(
            screener_thresholds_used.get("near_limit_down_pct"),
            SCREENER_THRESHOLDS.get("near_limit_down_pct"),
            "near_limit_down_pct in screener_thresholds must match SCREENER_THRESHOLDS"
        )
        self.assertEqual(
            screener_thresholds_used.get("low_turnover_rate"),
            SCREENER_THRESHOLDS.get("low_turnover_rate"),
            "low_turnover_rate in screener_thresholds must match SCREENER_THRESHOLDS"
        )
        self.assertEqual(
            screener_thresholds_used.get("low_float_market_cap_billion"),
            SCREENER_THRESHOLDS.get("low_float_market_cap_billion"),
            "low_float_market_cap_billion in screener_thresholds must match SCREENER_THRESHOLDS"
        )

    def test_merger_decision_changes_when_drop_speculative_threshold_changes(self):
        """A6: Assert _should_drop_card is sensitive to drop_speculative_score_floor parameter.

        Verifies that changing drop_speculative_score_floor in thresholds
        directly changes the should-drop decision for a card near the boundary.
        This locks down that threshold parameters are wired, not hardcoded.
        """
        from tradingagents.screener.merger import _should_drop_card, DEFAULT_CONFLICT_PRIORITY
        from tradingagents.screener.models import SignalCard, SignalEvidence

        # Card hits technical_structure_risk path:
        #   structure_risk_score=30 (<=35) AND trend_consistency_score=40 (<=45)
        #   policy=keyword_fallback (policy_strength=1) -> triggers technical_structure_risk
        #   screening_score=76.0 -> between 75.0 and 78.0 thresholds
        card = SignalCard(
            ticker="000001.SZ",
            raw_code="000001",
            exchange="SZ",
            company_name="TestCorp",
            trade_date="2026-01-01",
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=76.0,
                    reason="test",
                    raw_metrics={
                        "signal_consistency_index": 55.0,
                        "structure_risk_score": 30.0,
                        "trend_consistency_score": 40.0,
                        "structure_risk_band": "high",
                    },
                ),
                SignalEvidence(
                    strategy="policy",
                    score=75.0,
                    reason="test",
                    raw_metrics={
                        "policy_selection_tag": "policy_keyword_fallback",
                        "primary_concept_score": 55.0,
                        "concept_competition_score": 30.0,
                    },
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=75.0,
                    reason="test",
                    raw_metrics={
                        "capital_quality_tag": "persistent",
                        "quality_stability_index": 65.0,
                    },
                ),
            ],
            trigger_reason="test",
            initial_confidence=80.0,
            screening_score=76.0,
            evidence_snapshot={},
            concept_tags=["policy_keyword_fallback", "capital_quality_persistent"],
            sector_tags=["technology"],
            risk_flags=[],
        )

        # Threshold 75.0: score 76.0 >= 75.0 -> NOT dropped
        th_low = {"drop_speculative_score_floor": 75.0}
        dropped_low, reasons_low = _should_drop_card(card, th_low, DEFAULT_CONFLICT_PRIORITY)
        self.assertFalse(dropped_low, f"With threshold 75.0, card score 76.0 should NOT be dropped. Reasons: {reasons_low}")

        # Threshold 78.0: score 76.0 < 78.0 -> DROPPED (technical_structure_risk path)
        th_high = {"drop_speculative_score_floor": 78.0}
        dropped_high, reasons_high = _should_drop_card(card, th_high, DEFAULT_CONFLICT_PRIORITY)
        self.assertTrue(dropped_high, f"With threshold 78.0, card score 76.0 SHOULD be dropped. Reasons: {reasons_high}")
        self.assertIn("technical_structure_risk", reasons_high)
