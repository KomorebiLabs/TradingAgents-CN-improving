import unittest

from tradingagents.screener.strategies.policy import PolicyStrategy


class PolicyAccessReady:
    def validate_interface_assumptions(self, trade_date=None):
        return {
            "concept_list_verified": True,
            "concept_primary_vendor": "ths",
            "concept_list_fallback_vendor": "sina",
            "freshness": [],
            "warnings": [],
            "strategy_capabilities": {
                "policy": {
                    "status_hint": "ready",
                    "primary_dependencies": {
                        "concept_list": "ths",
                        "concept_fallback": "sina",
                        "news_auxiliary": "baidu",
                    },
                }
            },
        }

    def fetch_concept_boards(self):
        import pandas as pd

        return pd.DataFrame({"name": ["人工智能", "半导体"], "code": ["A1", "A2"]})

    def fetch_policy_news_baidu(self, trade_date, look_back_days=7, limit=24):
        import pandas as pd

        return pd.DataFrame({"事件": ["中国人工智能政策支持加码", "半导体制造补贴出台"]})

    def fetch_concept_constituents(self, concept_name):
        import pandas as pd

        if concept_name == "人工智能":
            return pd.DataFrame(
                {
                    "代码": ["000300", "000001"],
                    "名称": ["CSI 300 Index Proxy", "Mock A"],
                    "涨跌幅": [4.2, 1.1],
                    "成交额": [800000000.0, 120000000.0],
                    "换手率": [6.5, 2.2],
                }
            )
        return pd.DataFrame(
            {
                "代码": ["000905"],
                "名称": ["CSI 500 Index Proxy"],
                "涨跌幅": [2.0],
                "成交额": [300000000.0],
                "换手率": [3.1],
            }
        )

    def fetch_index_constituents(self, index_code):
        import pandas as pd

        if index_code == "000300":
            return pd.DataFrame({"成分券代码": ["000001", "000300"], "成分券名称": ["平安银行", "CSI 300 Proxy"]})
        if index_code == "000905":
            return pd.DataFrame({"成分券代码": [], "成分券名称": []})
        if index_code == "399006":
            return pd.DataFrame({"成分券代码": [], "成分券名称": []})
        return pd.DataFrame({"成分券代码": [], "成分券名称": []})


class PolicyAccessDegraded(PolicyAccessReady):
    def validate_interface_assumptions(self, trade_date=None):
        payload = super().validate_interface_assumptions(trade_date=trade_date)
        payload["concept_list_verified"] = False
        payload["strategy_capabilities"]["policy"]["status_hint"] = "degraded"
        return payload


class ScreenerPolicyStrategyTests(unittest.TestCase):
    def test_policy_strategy_ready_when_concept_chain_is_verified(self):
        outcome = PolicyStrategy(PolicyAccessReady(), config={}).run(["000300"], "2026-05-07")
        card = outcome.cards[0]

        self.assertEqual(outcome.status, "ready")
        self.assertTrue(card.data_source_verified)
        self.assertEqual(card.signal_breakdown[0].raw_metrics["concept_primary_vendor"], "ths")
        self.assertEqual(card.signal_breakdown[0].raw_metrics["news_sources_used"], ["baidu"])
        self.assertIn(card.concept_tags[0], {"人工智能", "半导体"})
        self.assertIn("policy_top_stock", card.concept_tags)
        self.assertGreater(card.signal_breakdown[0].raw_metrics["stock_strength_score"], 70)
        self.assertGreaterEqual(card.signal_breakdown[0].raw_metrics["concept_constituent_count"], 1)
        self.assertTrue(card.signal_breakdown[0].raw_metrics["universe_cross_hit"])
        self.assertGreater(card.signal_breakdown[0].raw_metrics["relative_rank_score"], 70)
        self.assertGreater(card.signal_breakdown[0].raw_metrics["board_leadership_score"], 75)
        self.assertEqual(card.signal_breakdown[0].raw_metrics["stock_selection_tag"], "policy_top_stock")
        self.assertTrue(card.signal_breakdown[0].raw_metrics["top_tier_hit"])
        self.assertEqual(card.trigger_reason, "policy_concept_top_pick")
        self.assertEqual(card.signal_breakdown[0].raw_metrics["score_family"], "policy_concept_board_v1")
        self.assertIn("threshold_snapshot", card.signal_breakdown[0].raw_metrics)
        self.assertEqual(card.signal_breakdown[0].raw_metrics["concept_weight_bucket"], "concept_weight_core")
        self.assertIn("concept_weight_core", card.concept_tags)
        self.assertIn("concept_linkage_boundary", card.signal_breakdown[0].raw_metrics)
        self.assertIn("degraded_context", card.signal_breakdown[0].raw_metrics)
        self.assertIn("vendor_trace", card.signal_breakdown[0].raw_metrics)
        self.assertFalse(card.signal_breakdown[0].raw_metrics["degraded_context"]["keyword_mode"])
        self.assertIn("primary_concept_score", card.signal_breakdown[0].raw_metrics)
        self.assertIn("concept_competition_score", card.signal_breakdown[0].raw_metrics)
        self.assertIn("primary_concept_selection_summary", card.signal_breakdown[0].raw_metrics)
        self.assertEqual(
            card.signal_breakdown[0].raw_metrics["concept_linkage_boundary"]["linkage_mode"],
            "verified_constituent_cross_hit",
        )

    def test_policy_strategy_degraded_when_concept_chain_is_unverified(self):
        outcome = PolicyStrategy(PolicyAccessDegraded(), config={}).run(["000300"], "2026-05-07")
        card = outcome.cards[0]

        self.assertEqual(outcome.status, "degraded")
        self.assertFalse(card.data_source_verified)
        self.assertIn("concept_list_unverified", card.signal_breakdown[0].degradation_reason)
        self.assertIn("concept_primary_unavailable", card.risk_flags)
        self.assertNotEqual(card.signal_breakdown[0].raw_metrics["stock_selection_tag"], "")
        self.assertTrue(card.signal_breakdown[0].raw_metrics["degraded_context"]["concept_verified"] is False)
        self.assertEqual(
            card.signal_breakdown[0].raw_metrics["concept_linkage_boundary"]["confidence_tier"],
            "low",
        )

    def test_policy_strategy_marks_tail_member_when_not_top_tier(self):
        class TailMemberAccess(PolicyAccessReady):
            def fetch_concept_constituents(self, concept_name):
                import pandas as pd

                if concept_name == "人工智能":
                    # H6 FIX: use correct column names; ensure enough rows for the test scenario
                    return pd.DataFrame(
                        {
                            "代码": ["000001", "000002", "000003", "000004", "000005", "000300"],
                            "名称": ["A", "B", "C", "D", "E", "CSI 300 Index Proxy"],
                            "涨跌幅": [8.2, 7.1, 6.4, 5.8, 5.2, 1.0],
                            "成交额": [9e8, 8e8, 7e8, 6e8, 5e8, 8e7],
                            "换手率": [9.1, 8.5, 7.8, 6.5, 5.2, 1.5],
                        }
                    )
                return super().fetch_concept_constituents(concept_name)

        # H6 FIX: set max_stocks_per_concept=20 to include all 6 rows including 000300 at rank 6
        outcome = PolicyStrategy(
            TailMemberAccess(),
            config={"strategies": {"policy": {"max_stocks_per_concept": 20}}},
        ).run(["000300"], "2026-05-07")
        card = outcome.cards[0]

        self.assertEqual(card.signal_breakdown[0].raw_metrics["concept_weight_bucket"], "concept_weight_core")
        self.assertIn("non_top_concept_member", card.risk_flags)

    def test_policy_strategy_counts_multi_concept_overlap(self):
        class MultiConceptAccess(PolicyAccessReady):
            def fetch_concept_constituents(self, concept_name):
                import pandas as pd

                if concept_name == "人工智能":
                    return pd.DataFrame(
                        {
                            "代码": ["000300", "000001"],
                            "名称": ["CSI 300 Index Proxy", "A"],
                            "涨跌幅": [5.1, 2.0],
                            "成交额": [900000000.0, 120000000.0],
                            "换手率": [7.0, 2.2],
                        }
                    )
                return pd.DataFrame(
                    {
                        "代码": ["000300", "000905"],
                        "名称": ["CSI 300 Index Proxy", "CSI 500 Index Proxy"],
                        "涨跌幅": [4.8, 2.0],
                        "成交额": [600000000.0, 300000000.0],
                        "换手率": [5.6, 3.1],
                    }
                )

        outcome = PolicyStrategy(MultiConceptAccess(), config={}).run(["000300"], "2026-05-07")
        card = outcome.cards[0]

        self.assertGreaterEqual(card.signal_breakdown[0].raw_metrics["multi_concept_overlap_count"], 2)
        self.assertGreater(card.signal_breakdown[0].raw_metrics["concept_competition_score"], 70)
        self.assertIn("selected as primary concept", card.signal_breakdown[0].raw_metrics["primary_concept_selection_summary"])


class PolicyStrategyApiCallOptimizationTests(unittest.TestCase):
    """P0 boundary tests for H6: concept constituent fetching is O(m) not O(n*m)."""

    def test_concept_budget_cap_respected(self):
        """H6 FIX: selected_concepts should be capped by max_concepts config."""

        class FakeDA:
            call_count = 0

            def validate_interface_assumptions(self, trade_date=None):
                return {
                    "concept_list_verified": True,
                    "strategy_capabilities": {
                        "policy": {
                            "status_hint": "ready",
                            "primary_dependencies": {
                                "concept_list": "ths",
                                "concept_fallback": "sina",
                                "news_auxiliary": "baidu",
                            },
                        }
                    },
                    "warnings": [],
                    "freshness": [],
                }

            def fetch_concept_boards(self):
                import pandas as pd

                # Return 10 concept names but max_concepts=3 should cap at 3
                return pd.DataFrame(
                    {"name": [f"concept_{i}" for i in range(10)], "code": [f"C{i}" for i in range(10)]}
                )

            def fetch_policy_news_baidu(self, *a, **kw):
                import pandas as pd

                return pd.DataFrame({"事件": ["test event"]})

            def fetch_concept_constituents(self, concept_name):
                import pandas as pd

                FakeDA.call_count += 1
                return pd.DataFrame({"代码": ["000001"], "名称": ["A"], "涨跌幅": [1.0], "成交额": [1e8], "换手率": [1.0]})

        FakeDA.call_count = 0
        # H6: max_concepts=3 limits API calls to 3 concept boards
        outcome = PolicyStrategy(
            FakeDA(), config={"strategies": {"policy": {"max_concepts": 3, "max_stocks_per_concept": 5}}}
        ).run(["000001"], "2026-05-07")

        # With 3 concepts capped, we expect at most 3 fetch_concept_constituents calls
        self.assertLessEqual(FakeDA.call_count, 3)

    def test_universe_loop_has_no_api_calls(self):
        """H6 FIX: universe loop must NOT call fetch_concept_constituents (only pre-fetched data)."""

        class SpyDA:
            constituent_calls = 0

            def validate_interface_assumptions(self, trade_date=None):
                return {
                    "concept_list_verified": True,
                    "strategy_capabilities": {
                        "policy": {
                            "status_hint": "ready",
                            "primary_dependencies": {
                                "concept_list": "ths",
                                "concept_fallback": "sina",
                                "news_auxiliary": "baidu",
                            },
                        }
                    },
                    "warnings": [],
                    "freshness": [],
                }

            def fetch_concept_boards(self):
                import pandas as pd

                # Return 2 concepts; both should appear in news so both are selected
                return pd.DataFrame({"name": ["人工智能", "半导体"], "code": ["A1", "A2"]})

            def fetch_policy_news_baidu(self, *a, **kw):
                import pandas as pd

                # Both concept names appear in news so both are selected → 2 constituent calls
                return pd.DataFrame({"事件": ["中国人工智能政策支持，半导体行业利好"]})

            def fetch_concept_constituents(self, concept_name):
                SpyDA.constituent_calls += 1
                import pandas as pd

                return pd.DataFrame({"代码": ["000001"], "名称": ["A"], "涨跌幅": [1.0], "成交额": [1e8], "换手率": [1.0]})

        SpyDA.constituent_calls = 0
        # Run with a large universe (100 stocks)
        outcome = PolicyStrategy(SpyDA(), config={}).run([f"{i:06d}" for i in range(100)], "2026-05-07")
        # H6: constituent_calls should equal number of selected concepts (2), NOT 100
        # If this fails, it means fetch_concept_constituents is being called per-stock (O(n*m))
        self.assertEqual(SpyDA.constituent_calls, 2, "Universe loop must not call fetch_concept_constituents")


if __name__ == "__main__":
    unittest.main()
