import unittest

from tradingagents.screener.merger import merge_signal_cards
from tradingagents.screener.models import SignalCard, SignalEvidence
from tradingagents.screener.config import SCREENER_CONFIG


def make_card(ticker: str, strategy: str, score: float, sector: str) -> SignalCard:
    return SignalCard(
        ticker=ticker,
        raw_code=ticker.split(".")[0],
        exchange=ticker.split(".")[1],
        company_name=ticker,
        trade_date="2026-05-07",
        sector_tags=[sector],
        strategy_sources=[strategy],
        signal_breakdown=[
            SignalEvidence(
                strategy=strategy,  # type: ignore[arg-type]
                score=score,
                reason=f"{strategy} signal",
            )
        ],
        trigger_reason=f"{strategy}_trigger",
        initial_confidence=min(score, 100.0),
        screening_score=score,
    )


class ScreenerMergerTests(unittest.TestCase):
    def test_merge_same_ticker_combines_sources(self):
        cards = [
            make_card("600519.SH", "technical", 80.0, "broad_market"),
            make_card("600519.SH", "policy", 70.0, "broad_market"),
        ]

        merged, dropped = merge_signal_cards(cards, mode="MVP")
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(dropped), 0)
        self.assertEqual(sorted(merged[0].strategy_sources), ["policy", "technical"])
        self.assertEqual(merged[0].screening_rank, 1)

    def test_same_sector_limit_applies(self):
        cards = [
            make_card("600519.SH", "technical", 80.0, "broad_market"),
            make_card("000001.SZ", "technical", 79.0, "broad_market"),
            make_card("000002.SZ", "technical", 78.0, "broad_market"),
        ]

        merged, dropped = merge_signal_cards(cards, mode="EXTENDED")
        self.assertEqual(len(merged), 2)
        self.assertEqual(len(dropped), 1)
        self.assertIn("same_sector_limit", dropped[0]["reasons"])

    def test_hard_filters_drop_st_and_limit_down(self):
        st_card = make_card("600519.SH", "technical", 80.0, "broad_market")
        st_card.company_name = "*ST Test"

        limit_down_card = make_card("000001.SZ", "technical", 79.0, "bank")
        limit_down_card.signal_breakdown[0].raw_metrics = {"change_pct": -10.0}

        merged, dropped = merge_signal_cards([st_card, limit_down_card], mode="MVP")

        self.assertEqual(len(merged), 0)
        self.assertEqual(len(dropped), 2)
        all_reasons = [reason for item in dropped for reason in item["reasons"]]
        self.assertIn("st_flagged", all_reasons)
        self.assertIn("near_limit_down", all_reasons)

    def test_policy_top_stock_semantics_improve_priority_under_sector_limit(self):
        top_stock = make_card("600519.SH", "policy", 75.0, "policy_driven")
        top_stock.concept_tags = ["人工智能", "policy_top_stock"]
        top_stock.signal_breakdown[0].raw_metrics = {
            "stock_selection_tag": "policy_top_stock",
            "board_leadership_score": 90.0,
            "relative_rank_score": 88.0,
        }

        normal_peer = make_card("000001.SZ", "policy", 76.0, "policy_driven")
        normal_peer.concept_tags = ["人工智能", "policy_core_member"]
        normal_peer.signal_breakdown[0].raw_metrics = {
            "stock_selection_tag": "policy_core_member",
            "board_leadership_score": 68.0,
            "relative_rank_score": 62.0,
        }

        another_sector = make_card("000002.SZ", "technical", 72.0, "broad_market")

        merged, dropped = merge_signal_cards(
            [top_stock, normal_peer, another_sector],
            mode="MVP",
            config={"candidates": {"same_sector_limit": 1, "max_output": 3}, "thresholds": {}},
        )

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].ticker, "600519.SH")
        self.assertTrue(any("same_sector_limit" in item["reasons"] for item in dropped))

    def test_speculative_capital_quality_can_be_dropped(self):
        speculative = make_card("600519.SH", "smart_money", 74.0, "capital_flow")
        speculative.concept_tags = ["smart_money_enhanced", "capital_quality_speculative", "policy_keyword_fallback"]
        speculative.sector_tags = ["capital_flow", "capital_quality_speculative"]
        speculative.initial_confidence = 66.0
        speculative.signal_breakdown[0].raw_metrics = {
            "capital_quality_tag": "capital_quality_speculative",
            "capital_quality_summary": "speculative high-heat flow | risk=38 | continuity=42 | institutional=48",
        }

        merged, dropped = merge_signal_cards(
            [speculative],
            mode="MVP",
            config={"candidates": {"same_sector_limit": 2, "max_output": 3}, "thresholds": {}},
        )

        self.assertEqual(len(merged), 0)
        self.assertEqual(len(dropped), 1)
        self.assertIn("speculative_capital_flow", dropped[0]["reasons"])
        self.assertIn("speculative high-heat flow", dropped[0]["capital_quality_summary"])

    def test_technical_structure_risk_reduces_priority_and_can_drop(self):
        strong = make_card("600519.SH", "technical", 80.0, "broad_market")
        strong.signal_breakdown[0].raw_metrics = {
            "structure_risk_score": 72.0,
            "trend_consistency_score": 74.0,
            "recent_extension_pct": 3.2,
            "positive_days_ratio_pct": 60.0,
            "volume_confirmation_score": 72.0,
            "breakout_quality_score": 70.0,
            "volume_price_divergence_score": 68.0,
            "close_above_ma20": True,
            "close_above_ma60": True,
        }

        weak = make_card("000001.SZ", "technical", 77.0, "bank")
        weak.signal_breakdown[0].raw_metrics = {
            "structure_risk_score": 32.0,
            "trend_consistency_score": 40.0,
            "recent_extension_pct": 10.5,
            "positive_days_ratio_pct": 41.0,
            "volume_confirmation_score": 42.0,
            "breakout_quality_score": 44.0,
            "volume_price_divergence_score": 38.0,
            "volume_spike_ratio": 2.1,
            "close_above_ma20": False,
            "close_above_ma60": False,
        }
        weak.risk_flags = ["trend_structure_extended", "trend_consistency_weak", "lost_ma20_support", "volume_exhaustion_risk", "price_volume_divergence"]

        merged, dropped = merge_signal_cards(
            [strong, weak],
            mode="MVP",
            config={"candidates": {"same_sector_limit": 2, "max_output": 3}, "thresholds": {}},
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].ticker, "600519.SH")
        self.assertEqual(len(dropped), 1)
        self.assertEqual(dropped[0]["ticker"], "000001.SZ")
        self.assertIn("technical_structure_risk", dropped[0]["reasons"])
        self.assertIn("structure_risk=32.0", dropped[0]["technical_structure_summary"])
        self.assertIn("volume_divergence=38.0", dropped[0]["technical_structure_summary"])

    def test_strong_policy_cannot_fully_override_severe_technical_and_speculative_conflict(self):
        top_policy_but_broken = SignalCard(
            ticker="600519.SH",
            raw_code="600519",
            exchange="SH",
            company_name="600519.SH",
            trade_date="2026-05-07",
            sector_tags=["policy_driven"],
            concept_tags=["人工智能", "policy_top_stock", "capital_quality_speculative"],
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=72.0,
                    reason="technical",
                    raw_metrics={
                        "structure_risk_score": 33.0,
                        "trend_consistency_score": 39.0,
                        "recent_extension_pct": 11.2,
                        "positive_days_ratio_pct": 43.0,
                        "close_above_ma20": False,
                        "close_above_ma60": False,
                    },
                ),
                SignalEvidence(
                    strategy="policy",
                    score=88.0,
                    reason="policy",
                    raw_metrics={"stock_selection_tag": "policy_top_stock"},
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=70.0,
                    reason="smart money",
                    raw_metrics={
                        "capital_quality_tag": "capital_quality_speculative",
                        "capital_quality_summary": "speculative high-heat flow",
                    },
                ),
            ],
            trigger_reason="conflict_case",
            initial_confidence=76.0,
            screening_score=79.0,
            risk_flags=["trend_structure_extended", "trend_consistency_weak", "lost_ma20_support"],
        )

        merged, dropped = merge_signal_cards(
            [top_policy_but_broken],
            mode="MVP",
            config={"candidates": {"same_sector_limit": 2, "max_output": 3}, "thresholds": {}},
        )

        self.assertEqual(len(merged), 0)
        self.assertEqual(len(dropped), 1)
        self.assertIn("conflict_policy_capital_vs_technical", dropped[0]["reasons"])
        self.assertEqual(dropped[0]["conflict_resolution"], "policy_vs_technical")
        self.assertIn("strong semantic conflict resolved against weak structure", dropped[0]["semantic_decision_summary"])

    def test_strong_technical_but_weak_policy_fallback_loses_to_core_semantic_candidate(self):
        weak_semantic = SignalCard(
            ticker="000001.SZ",
            raw_code="000001",
            exchange="SZ",
            company_name="000001.SZ",
            trade_date="2026-05-07",
            sector_tags=["新能源"],
            concept_tags=["新能源", "policy_keyword_fallback", "capital_quality_mixed"],
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=86.0,
                    reason="technical",
                    raw_metrics={
                        "structure_risk_score": 70.0,
                        "trend_consistency_score": 73.0,
                        "recent_extension_pct": 2.8,
                        "positive_days_ratio_pct": 61.0,
                        "close_above_ma20": True,
                        "close_above_ma60": True,
                    },
                ),
                SignalEvidence(
                    strategy="policy",
                    score=60.0,
                    reason="policy",
                    raw_metrics={"stock_selection_tag": "policy_keyword_fallback"},
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=62.0,
                    reason="smart money",
                    raw_metrics={
                        "capital_quality_tag": "capital_quality_mixed",
                        "capital_quality_summary": "mixed capital-quality profile",
                    },
                ),
            ],
            trigger_reason="weak_semantic",
            initial_confidence=80.0,
            screening_score=82.0,
        )

        core_semantic = SignalCard(
            ticker="000002.SZ",
            raw_code="000002",
            exchange="SZ",
            company_name="000002.SZ",
            trade_date="2026-05-07",
            sector_tags=["新能源"],
            concept_tags=["新能源", "policy_core_member", "capital_quality_persistent"],
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=78.0,
                    reason="technical",
                    raw_metrics={
                        "structure_risk_score": 64.0,
                        "trend_consistency_score": 66.0,
                        "recent_extension_pct": 3.0,
                        "positive_days_ratio_pct": 58.0,
                        "close_above_ma20": True,
                        "close_above_ma60": True,
                    },
                ),
                SignalEvidence(
                    strategy="policy",
                    score=80.0,
                    reason="policy",
                    raw_metrics={"stock_selection_tag": "policy_core_member"},
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=76.0,
                    reason="smart money",
                    raw_metrics={
                        "capital_quality_tag": "capital_quality_persistent",
                        "capital_quality_summary": "persistent multi-day capital flow",
                    },
                ),
            ],
            trigger_reason="core_semantic",
            initial_confidence=79.0,
            screening_score=79.0,
        )

        merged, dropped = merge_signal_cards(
            [weak_semantic, core_semantic],
            mode="MVP",
            config={"candidates": {"same_sector_limit": 1, "max_output": 3}, "thresholds": {}},
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].ticker, "000002.SZ")
        self.assertEqual(len(dropped), 1)
        self.assertEqual(dropped[0]["ticker"], "000001.SZ")
        self.assertIn("same_sector_limit", dropped[0]["reasons"])
        self.assertIn("weaker concept fallback candidate removed by diversification", dropped[0]["semantic_decision_summary"])

    def test_cross_strategy_alignment_bonus_beats_higher_but_divergent_raw_score(self):
        aligned = SignalCard(
            ticker="600519.SH",
            raw_code="600519",
            exchange="SH",
            company_name="600519.SH",
            trade_date="2026-05-07",
            sector_tags=["白酒"],
            concept_tags=["白酒", "policy_core_member", "capital_quality_high"],
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=79.0,
                    reason="technical",
                    raw_metrics={
                        "structure_risk_score": 71.0,
                        "trend_consistency_score": 74.0,
                        "recent_extension_pct": 2.4,
                        "positive_days_ratio_pct": 60.0,
                        "close_above_ma20": True,
                        "close_above_ma60": True,
                    },
                ),
                SignalEvidence(
                    strategy="policy",
                    score=81.0,
                    reason="policy",
                    raw_metrics={"stock_selection_tag": "policy_core_member"},
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=80.0,
                    reason="smart money",
                    raw_metrics={
                        "capital_quality_tag": "capital_quality_high",
                        "capital_quality_summary": "high-quality persistent capital flow",
                    },
                ),
            ],
            trigger_reason="aligned_case",
            initial_confidence=80.0,
            screening_score=80.0,
        )

        divergent = SignalCard(
            ticker="000001.SZ",
            raw_code="000001",
            exchange="SZ",
            company_name="000001.SZ",
            trade_date="2026-05-07",
            sector_tags=["银行"],
            concept_tags=["银行", "policy_keyword_fallback", "capital_quality_mixed"],
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=90.0,
                    reason="technical",
                    raw_metrics={
                        "structure_risk_score": 70.0,
                        "trend_consistency_score": 75.0,
                        "recent_extension_pct": 2.0,
                        "positive_days_ratio_pct": 61.0,
                        "close_above_ma20": True,
                        "close_above_ma60": True,
                    },
                ),
                SignalEvidence(
                    strategy="policy",
                    score=62.0,
                    reason="policy",
                    raw_metrics={"stock_selection_tag": "policy_keyword_fallback"},
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=64.0,
                    reason="smart money",
                    raw_metrics={
                        "capital_quality_tag": "capital_quality_mixed",
                        "capital_quality_summary": "mixed capital-quality profile",
                    },
                ),
            ],
            trigger_reason="divergent_case",
            initial_confidence=82.0,
            screening_score=82.0,
        )

        merged, dropped = merge_signal_cards(
            [aligned, divergent],
            mode="MVP",
            config={"candidates": {"same_sector_limit": 2, "max_output": 3}, "thresholds": {}},
        )

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].ticker, "600519.SH")
        self.assertEqual(merged[0].evidence_snapshot["cross_strategy_conflict"]["tier"], "aligned")
        self.assertIn("cross_strategy_conflict: tier=aligned", merged[0].evidence_snapshot["semantic_decision_summary"])
        self.assertEqual(merged[0].evidence_snapshot["conflict_resolution_rule"], "semantic_consensus_priority")
        self.assertGreater(merged[0].evidence_snapshot["conflict_priority_bias"], 0)
        self.assertEqual(merged[1].evidence_snapshot["cross_strategy_conflict"]["tier"], "severe")

    def test_cross_strategy_conflict_is_written_into_drop_summary(self):
        conflict_card = SignalCard(
            ticker="300001.SZ",
            raw_code="300001",
            exchange="SZ",
            company_name="300001.SZ",
            trade_date="2026-05-07",
            sector_tags=["成长"],
            concept_tags=["成长", "policy_top_stock", "capital_quality_speculative"],
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=58.0,
                    reason="technical",
                    raw_metrics={
                        "structure_risk_score": 31.0,
                        "trend_consistency_score": 38.0,
                        "recent_extension_pct": 12.0,
                        "positive_days_ratio_pct": 40.0,
                        "close_above_ma20": False,
                        "close_above_ma60": False,
                    },
                ),
                SignalEvidence(
                    strategy="policy",
                    score=88.0,
                    reason="policy",
                    raw_metrics={"stock_selection_tag": "policy_top_stock"},
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=74.0,
                    reason="smart money",
                    raw_metrics={
                        "capital_quality_tag": "capital_quality_speculative",
                        "capital_quality_summary": "speculative high-heat flow",
                    },
                ),
            ],
            trigger_reason="drop_conflict_case",
            initial_confidence=70.0,
            screening_score=76.0,
            risk_flags=["trend_structure_extended", "trend_consistency_weak", "lost_ma20_support"],
        )

        merged, dropped = merge_signal_cards(
            [conflict_card],
            mode="MVP",
            config={"candidates": {"same_sector_limit": 2, "max_output": 3}, "thresholds": {}},
        )

        self.assertEqual(len(merged), 0)
        self.assertEqual(len(dropped), 1)
        self.assertIn("cross_strategy_conflict: tier=severe", dropped[0]["semantic_decision_summary"])
        self.assertEqual(dropped[0]["conflict_resolution"], "policy_vs_technical")
        self.assertEqual(dropped[0]["conflict_resolution_rule"], "technical_veto_overrides_semantic")
        self.assertLess(dropped[0]["conflict_priority_bias"], 0)

    def test_weak_policy_under_technical_stress_is_explicitly_discounted(self):
        weak_policy_stress = SignalCard(
            ticker="300123.SZ",
            raw_code="300123",
            exchange="SZ",
            company_name="300123.SZ",
            trade_date="2026-05-07",
            sector_tags=["成长"],
            concept_tags=["成长", "policy_keyword_fallback", "capital_quality_mixed"],
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=73.0,
                    reason="technical",
                    raw_metrics={
                        "structure_risk_score": 34.0,
                        "trend_consistency_score": 39.0,
                        "recent_extension_pct": 9.0,
                        "positive_days_ratio_pct": 42.0,
                        "close_above_ma20": False,
                        "close_above_ma60": False,
                    },
                ),
                SignalEvidence(
                    strategy="policy",
                    score=61.0,
                    reason="policy",
                    raw_metrics={"stock_selection_tag": "policy_keyword_fallback"},
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=63.0,
                    reason="smart money",
                    raw_metrics={
                        "capital_quality_tag": "capital_quality_mixed",
                        "capital_quality_summary": "mixed capital-quality profile",
                    },
                ),
            ],
            trigger_reason="weak_policy_stress",
            initial_confidence=71.0,
            screening_score=75.0,
            risk_flags=["trend_structure_extended", "trend_consistency_weak", "lost_ma20_support"],
        )

        merged, dropped = merge_signal_cards(
            [weak_policy_stress],
            mode="MVP",
            config={"candidates": {"same_sector_limit": 2, "max_output": 3}, "thresholds": {}},
        )

        self.assertEqual(len(merged), 0)
        self.assertEqual(len(dropped), 1)
        self.assertIn("weak_policy_under_technical_stress", dropped[0]["reasons"])
        self.assertEqual(dropped[0]["conflict_resolution_rule"], "weak_policy_discount_under_technical_stress")

    def test_heat_quality_gap_exclusion_is_written_into_drop_reason(self):
        heated = SignalCard(
            ticker="300555.SZ",
            raw_code="300555",
            exchange="SZ",
            company_name="300555.SZ",
            trade_date="2026-05-07",
            sector_tags=["成长"],
            concept_tags=["成长", "policy_keyword_fallback", "capital_quality_speculative"],
            strategy_sources=["policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="policy",
                    score=62.0,
                    reason="policy",
                    raw_metrics={"stock_selection_tag": "policy_keyword_fallback"},
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=71.0,
                    reason="smart money",
                    raw_metrics={
                        "capital_quality_tag": "capital_quality_speculative",
                        "capital_quality_summary": "speculative high-heat flow | risk=40 | continuity=45 | institutional=43 | heat_gap=31",
                        "heat_quality_gap_score": 31.0,
                    },
                ),
            ],
            trigger_reason="heat_gap_case",
            initial_confidence=69.0,
            screening_score=75.0,
        )

        merged, dropped = merge_signal_cards(
            [heated],
            mode="MVP",
            config={"candidates": {"same_sector_limit": 2, "max_output": 3}, "thresholds": {}},
        )

        self.assertEqual(len(merged), 0)
        self.assertEqual(len(dropped), 1)
        self.assertIn("heat_quality_gap_exclusion", dropped[0]["reasons"])
        self.assertIn("heat outran quality and continuity", dropped[0]["semantic_decision_summary"])

    def test_conflict_priority_config_changes_bias_and_tier_thresholds(self):
        card = SignalCard(
            ticker="600519.SH",
            raw_code="600519",
            exchange="SH",
            company_name="600519.SH",
            trade_date="2026-05-07",
            sector_tags=["policy_driven"],
            concept_tags=["人工智能", "policy_top_stock", "capital_quality_speculative"],
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=72.0,
                    reason="technical",
                    raw_metrics={
                        "structure_risk_score": 33.0,
                        "trend_consistency_score": 39.0,
                        "recent_extension_pct": 11.2,
                        "positive_days_ratio_pct": 43.0,
                        "close_above_ma20": False,
                        "close_above_ma60": False,
                    },
                ),
                SignalEvidence(
                    strategy="policy",
                    score=88.0,
                    reason="policy",
                    raw_metrics={"stock_selection_tag": "policy_top_stock"},
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=70.0,
                    reason="smart money",
                    raw_metrics={
                        "capital_quality_tag": "capital_quality_speculative",
                        "capital_quality_summary": "speculative high-heat flow",
                    },
                ),
            ],
            trigger_reason="conflict_case",
            initial_confidence=76.0,
            screening_score=79.0,
            risk_flags=["trend_structure_extended", "trend_consistency_weak", "lost_ma20_support"],
        )

        config = {
            **SCREENER_CONFIG,
            "conflict_priority": {
                **SCREENER_CONFIG["conflict_priority"],
                "technical_veto_bias": -8,
                "technical_veto_min_severity": 3,
                "aligned_spread_max": 5.0,
            },
        }
        merged, dropped = merge_signal_cards([card], mode="MVP", config=config)

        self.assertEqual(len(merged), 0)
        self.assertEqual(len(dropped), 1)
        self.assertEqual(dropped[0]["conflict_resolution_rule"], "technical_veto_overrides_semantic")
        self.assertEqual(dropped[0]["conflict_priority_bias"], -8)

    def test_threshold_override_changes_semantic_threshold_triggers(self):
        technical = make_card("600519.SH", "technical", 79.0, "broad_market")
        technical.signal_breakdown[0].raw_metrics = {
            "signal_consistency_index": 44.0,
            "threshold_snapshot": {"signal_consistency_low": 45.0},
        }
        technical.risk_flags = ["signal_consistency_low"]

        policy = make_card("600519.SH", "policy", 76.0, "policy_driven")
        policy.concept_tags = ["新能源", "policy_core_member"]
        policy.signal_breakdown[0].raw_metrics = {
            "primary_concept_score": 72.0,
            "concept_competition_score": 66.0,
            "multi_concept_overlap_count": 1,
            "threshold_snapshot": {"concept_conviction_low": 52.0},
        }
        policy.risk_flags = ["concept_conviction_low"]

        smart_money = make_card("600519.SH", "smart_money", 77.0, "capital_flow")
        smart_money.concept_tags = ["smart_money_enhanced", "capital_quality_mixed"]
        smart_money.sector_tags = ["capital_flow", "capital_quality_mixed"]
        smart_money.signal_breakdown[0].raw_metrics = {
            "quality_stability_index": 47.0,
            "threshold_snapshot": {"quality_stability_low": 48.0},
        }
        smart_money.risk_flags = ["quality_stability_low"]

        merged, dropped = merge_signal_cards(
            [technical, policy, smart_money],
            mode="MVP",
            config={"candidates": {"same_sector_limit": 2, "max_output": 3}, "thresholds": {}},
        )

        self.assertEqual(len(merged), 1)
        payload = merged[0].evidence_snapshot["semantic_reason_payload"]
        self.assertIn("threshold_triggers", payload["technical"])
        self.assertIn("signal_consistency_low", payload["technical"]["threshold_triggers"])
        self.assertIn("concept_conviction_low", payload["policy"]["threshold_triggers"])
        self.assertIn("quality_stability_low", payload["capital"]["threshold_triggers"])
        self.assertEqual(payload["technical"]["threshold_snapshot"]["signal_consistency_low"], 45.0)
        self.assertEqual(payload["policy"]["threshold_snapshot"]["concept_conviction_low"], 52.0)
        self.assertEqual(payload["capital"]["threshold_snapshot"]["quality_stability_low"], 48.0)

    def test_threshold_override_config_does_not_drift_semantic_payload_shape(self):
        card = SignalCard(
            ticker="600519.SH",
            raw_code="600519",
            exchange="SH",
            company_name="600519.SH",
            trade_date="2026-05-07",
            sector_tags=["policy_driven"],
            concept_tags=["人工智能", "policy_core_member", "capital_quality_high"],
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=81.0,
                    reason="technical",
                    raw_metrics={
                        "signal_consistency_index": 47.0,
                        "threshold_snapshot": {"signal_consistency_low": 42.0},
                    },
                ),
                SignalEvidence(
                    strategy="policy",
                    score=83.0,
                    reason="policy",
                    raw_metrics={
                        "primary_concept_score": 79.0,
                        "concept_competition_score": 75.0,
                        "multi_concept_overlap_count": 2,
                        "threshold_snapshot": {"concept_conviction_low": 50.0},
                    },
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=84.0,
                    reason="smart money",
                    raw_metrics={
                        "quality_stability_index": 59.0,
                        "threshold_snapshot": {"quality_stability_low": 46.0},
                    },
                ),
            ],
            trigger_reason="shape_case",
            initial_confidence=82.0,
            screening_score=83.0,
            risk_flags=["signal_consistency_low", "concept_conviction_low", "quality_stability_low"],
        )

        merged, dropped = merge_signal_cards(
            [card],
            mode="MVP",
            config={
                "candidates": {"same_sector_limit": 2, "max_output": 3},
                "thresholds": {},
                "conflict_priority": {
                    "aligned_spread_max": 4.0,
                    "technical_veto_bias": -6,
                    "severe_conflict_bias": -3,
                },
            },
        )

        self.assertEqual(len(merged), 1)
        payload = merged[0].evidence_snapshot["semantic_reason_payload"]
        self.assertEqual(
            sorted(payload.keys()),
            sorted(
                [
                    "decision",
                    "summary",
                    "reasons",
                    "semantic_priority",
                    "policy",
                    "capital",
                    "technical",
                    "cross_strategy_conflict",
                    "conflict_resolution",
                    "conflict_resolution_rule",
                    "conflict_priority_bias",
                ]
            ),
        )
        self.assertIn("threshold_snapshot", payload["policy"])
        self.assertIn("threshold_snapshot", payload["capital"])
        self.assertIn("threshold_snapshot", payload["technical"])
        self.assertIn("threshold_triggers", payload["policy"])
        self.assertIn("threshold_triggers", payload["capital"])
        self.assertIn("threshold_triggers", payload["technical"])


if __name__ == "__main__":
    unittest.main()


def test_st_flagged_when_name_is_placeholder():
    """B-4.1: ST detection must work even when company_name is a placeholder."""
    from tradingagents.screener.merger import _is_st_name
    from tradingagents.screener.models import SignalCard, SignalEvidence

    card = SignalCard(
        ticker="000001.SZ",
        raw_code="000001",
        exchange="SZ",
        company_name="Proxy 000001",  # placeholder, no ST info
        trade_date="2026-01-01",
        sector_tags=["ST_candidate"],  # ST info here
        concept_tags=[],
        strategy_sources=["technical"],
        signal_breakdown=[],
        trigger_reason="test",
        screening_score=80.0,
        initial_confidence=80.0,
        data_source_verified=False,
    )
    assert _is_st_name(card) is True, "ST must be detected from sector_tags even when name is placeholder"
