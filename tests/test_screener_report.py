import unittest

from tradingagents.screener.models import DeepAnalysisResult, ScreeningResult, SignalCard, SignalEvidence
from tradingagents.screener.report import render_markdown_report


class ScreenerReportTests(unittest.TestCase):
    def test_markdown_report_contains_status_and_probe_sections(self):
        candidate = SignalCard(
            ticker="600519.SH",
            raw_code="600519",
            exchange="SH",
            company_name="贵州茅台",
            trade_date="2026-05-07",
            sector_tags=["policy_driven", "capital_quality_high"],
            concept_tags=["人工智能", "policy_top_stock", "capital_quality_high"],
            strategy_sources=["technical", "policy", "smart_money"],
            signal_breakdown=[
                SignalEvidence(
                    strategy="technical",
                    score=78.0,
                    reason="technical signal",
                    raw_metrics={
                        "structure_risk_score": 69.0,
                        "trend_consistency_score": 76.0,
                        "recent_extension_pct": 2.5,
                        "positive_days_ratio_pct": 61.0,
                        "volume_confirmation_score": 73.0,
                        "breakout_quality_score": 69.0,
                        "volume_price_divergence_score": 67.0,
                    },
                ),
                SignalEvidence(
                    strategy="policy",
                    score=82.0,
                    reason="policy signal",
                    raw_metrics={
                        "stock_selection_tag": "policy_top_stock",
                        "relative_rank_score": 88.0,
                        "board_leadership_score": 91.0,
                        "primary_concept_score": 84.0,
                        "concept_competition_score": 81.0,
                        "multi_concept_overlap_count": 2,
                        "primary_concept_selection_summary": "人工智能 selected as primary concept | top_selection=80.0 | heat=74.0 | overlap=2 | rank=1",
                        "concept_linkage_boundary": {
                            "linkage_mode": "verified_constituent_cross_hit",
                            "confidence_tier": "high",
                        },
                    },
                ),
                SignalEvidence(
                    strategy="smart_money",
                    score=80.0,
                    reason="smart money signal",
                    raw_metrics={
                        "multi_day_persistence_score": 77.0,
                        "risk_constraint_score": 70.0,
                        "continuity_score": 72.0,
                        "heat_quality_gap_score": 10.0,
                        "capital_quality_tag": "capital_quality_high",
                        "capital_quality_summary": "high-quality persistent flow | risk=70 | continuity=72 | institutional=75",
                    },
                ),
            ],
            trigger_reason="policy_concept_top_pick",
            initial_confidence=86.0,
            risk_flags=[],
            screening_score=84.0,
            data_source_verified=True,
            evidence_snapshot={
                "policy_selection_tag": "policy_top_stock",
                "capital_quality_tag": "capital_quality_high",
                "capital_quality_summary": "high-quality persistent flow | risk=70 | continuity=72 | institutional=75",
                "technical_structure_summary": "technical_structure: structure_risk=69.0 | consistency=76.0 | extension=2.5 | positive_days=61.0 | flags=none",
                "semantic_decision_summary": "retained_priority: concept top-stock gained priority",
                "semantic_reason_payload": {
                    "decision": "retained",
                    "summary": "retained_priority: concept top-stock gained priority",
                    "policy": {"policy_selection_tag": "policy_top_stock"},
                    "capital": {"capital_quality_tag": "capital_quality_high"},
                },
            },
        )

        result = ScreeningResult(
            run_id="run-report-1",
            mode="EXPERIMENTAL",
            trade_date="2026-05-07",
            started_at="2026-05-07T16:30:00",
            completed_at="2026-05-07T16:31:00",
            universe_size=5,
            universe_metadata={"profile": "EXPERIMENTAL", "cache_key": "experimental_index_union"},
            candidates=[candidate],
            dropped_candidates=[
                {
                    "ticker": "000001.SZ",
                    "company_name": "平安银行",
                    "reasons": ["speculative_capital_flow"],
                    "stage": "hard_filter",
                    "policy_selection_tag": "policy_keyword_fallback",
                    "capital_quality_tag": "capital_quality_speculative",
                    "capital_quality_summary": "speculative high-heat flow | risk=38 | continuity=42 | institutional=48",
                    "technical_structure_summary": "technical_structure: structure_risk=32.0 | consistency=41.0 | extension=9.8 | positive_days=44.0 | flags=trend_structure_extended,lost_ma20_support",
                    "semantic_decision_summary": "dropped_reason: speculative_flow_dominant triggered exclusion",
                    "semantic_reason_payload": {
                        "decision": "dropped",
                        "summary": "dropped_reason: speculative_flow_dominant triggered exclusion",
                        "capital": {"capital_quality_tag": "capital_quality_speculative"},
                    },
                }
            ],
            strategy_status={"technical": "ready", "policy": "ready", "smart_money": "ready"},
            data_issues=[],
            metrics={
                "capability_summary": {
                    "akshare_importable": True,
                    "fund_flow_bulk_verified": True,
                    "concept_list_verified": True,
                    "hist_fetch_verified": True,
                    "tencent_hist_verified": True,
                    "yfinance_hist_verified": False,
                    "fund_flow_fallback_vendor": "None",
                    "concept_list_fallback_vendor": "sina",
                    "hist_fetch_primary_vendor": "tencent",
                    "hist_fetch_secondary_vendor": "sina",
                    "hist_fetch_fallback_vendor": "yfinance",
                    "probed_at": "2026-05-07T16:29:00",
                    "probe_results": {
                        "hist_tencent": {"ok": True, "classification": "verified", "detail": "ok"}
                    },
                    "vendor_baseline": {"history": {"primary": "tencent"}},
                    "strategy_capabilities": {"policy": {"status_hint": "ready"}},
                },
                "retained_semantic_summaries": {
                    "600519.SH": "retained_priority: concept top-stock gained priority"
                },
                "retained_semantic_payloads": {
                    "600519.SH": {"decision": "retained", "summary": "retained_priority: concept top-stock gained priority"}
                },
                "dropped_semantic_summaries": {
                    "000001.SZ": "dropped_reason: speculative_flow_dominant triggered exclusion"
                },
                "dropped_semantic_payloads": {
                    "000001.SZ": {"decision": "dropped", "summary": "dropped_reason: speculative_flow_dominant triggered exclusion"}
                },
                "deep_analysis_results": [],
                "universe_summary": {"profile": "EXPERIMENTAL"},
            },
        )

        markdown = render_markdown_report(result, [])

        self.assertIn("## Strategy Status", markdown)
        self.assertIn("## Strategy Summary", markdown)
        self.assertIn("## Capability Summary", markdown)
        self.assertIn("## Universe Summary", markdown)
        self.assertIn("## Vendor Baseline", markdown)
        self.assertIn("## Strategy Capabilities", markdown)
        self.assertIn("## Probe Results", markdown)
        self.assertIn("## Dropped Candidates", markdown)
        self.assertIn("technical:", markdown)
        self.assertIn("tencent_hist_verified:", markdown)
        self.assertIn("hist_fetch_primary_vendor:", markdown)
        self.assertIn("hist_fetch_secondary_vendor:", markdown)
        self.assertIn("Policy Selection:", markdown)
        self.assertIn("Smart Money Quality:", markdown)
        self.assertIn("Technical Structure:", markdown)
        self.assertIn("Semantic Decision:", markdown)
        self.assertIn("Retention Card:", markdown)
        self.assertIn("policy_reason_card=", markdown)
        self.assertIn("capital_reason_card=", markdown)
        self.assertIn("technical_reason_card=", markdown)
        self.assertIn("semantic_reason_payload=", markdown)
        self.assertIn("Semantic Payload:", markdown)
        self.assertIn("primary_concept=84.0", markdown)
        self.assertIn("competition=81.0", markdown)
        self.assertIn("heat_gap=10.0", markdown)
        self.assertIn("linkage=verified_constituent_cross_hit", markdown)
        self.assertIn("high-quality persistent flow", markdown)
        self.assertIn("speculative high-heat flow", markdown)
        self.assertIn("structure_risk=69.0", markdown)
        self.assertIn("volume_confirmation=73.0", markdown)
        self.assertIn("breakout_quality=69.0", markdown)
        self.assertIn("volume_divergence=67.0", markdown)
        self.assertIn("trend_structure_extended,lost_ma20_support", markdown)

        deep_result = DeepAnalysisResult(
            signal_card=candidate,
            success=True,
            final_decision="DRY_RUN",
            elapsed_seconds=0.01,
            final_state_summary={
                "analysis_mode": "dry_run",
                "semantic_context_summary": "Policy semantic: board top-stock; Capital semantic: speculative capital",
                "semantic_prompt_slots": {
                    "schema_name": "screener.semantic_prompt_slots",
                    "schema_version": "1.0",
                    "policy_role": "policy_top_stock",
                    "policy_concept_conviction_score": 82.0,
                    "capital_quality_stability_index": 44.0,
                    "technical_signal_consistency_index": 39.0,
                },
                "semantic_execution_profile": {
                    "route_behavior_tag": "speculative_hardened_overlap",
                    "memory_n_matches": 1,
                },
                "semantic_trigger_audit": {
                    "semantic_trigger_slots": {
                        "policy_role": "policy_top_stock",
                        "capital_quality": "capital_quality_speculative",
                        "policy_multi_concept_overlap_count": 2,
                    },
                    "semantic_trigger_reasons": [
                        "policy_role=policy_top_stock",
                        "capital_quality=capital_quality_speculative",
                        "analyst_focus:concept_overlap",
                    ],
                },
                "semantic_route_audit_trail": [
                    {
                        "node": "Route Research Phase",
                        "route_reason": "research_direct_path",
                        "semantic_trigger_reasons": ["policy_role=policy_top_stock"],
                    }
                ],
                "route_decision": {
                    "route_family": "semantic_router_v1",
                    "policy_role": "policy_top_stock",
                    "capital_quality": "capital_quality_speculative",
                    "conflict_tier": "severe",
                    "analyst_focus": ["baseline", "policy_board", "risk_capital", "conflict_resolution"],
                    "debate_rounds": "compressed",
                    "debate_risk_weight": "high",
                    "semantic_flow_controls": {"debate_round_limit": 1, "force_risk_review": True},
                    "selected_analysts": ["news", "market", "social", "fundamentals"],
                },
                "graph_config_snapshot": {
                    "semantic_schema_name": "screener.semantic_prompt_slots",
                    "semantic_schema_version": "1.0",
                },
                "fallback_used": False,
            },
        )
        markdown_with_deep = render_markdown_report(result, [deep_result])
        self.assertIn("Semantic Context:", markdown_with_deep)
        self.assertIn("Prompt Slots:", markdown_with_deep)
        self.assertIn("Route Summary:", markdown_with_deep)
        self.assertIn("route_family=semantic_router_v1", markdown_with_deep)
        self.assertIn("Trigger Route Card:", markdown_with_deep)
        self.assertIn("trigger=['policy_role=policy_top_stock'", markdown_with_deep)
        self.assertIn("execution=speculative_hardened_overlap", markdown_with_deep)
        self.assertIn("semantic_route_audit_trail=", markdown_with_deep)
        # Deep analysis route summary uses "- Route Summary:" inline format
        self.assertIn("Route Summary:", markdown_with_deep)
        # A5: semantic_audit_chain section was removed; semantic context fields appear in Deep Analysis
        self.assertIn("policy_concept_conviction_score", markdown_with_deep)
        self.assertIn("capital_quality_stability_index", markdown_with_deep)
        self.assertIn("technical_signal_consistency_index", markdown_with_deep)


if __name__ == "__main__":
    unittest.main()
