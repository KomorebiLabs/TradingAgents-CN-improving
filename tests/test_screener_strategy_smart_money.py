import unittest

from tradingagents.screener.strategies.smart_money import SmartMoneyStrategy


class SmartMoneyAccessReady:
    def validate_interface_assumptions(self, trade_date=None):
        return {
            "hist_fetch_verified": True,
            "tencent_hist_verified": True,
            "yfinance_hist_verified": False,
            "fund_flow_verified": True,
            "hist_fetch_fallback_vendor": "yfinance",
            "hist_primary_vendor": "tencent",
            "freshness": [],
            "warnings": [],
            "strategy_capabilities": {
                "smart_money": {
                    "status_hint": "ready",
                    "primary_dependencies": {
                        "hist_fetch": "tencent",
                        "fund_flow": "ths",
                        "tick_data": "tencent",
                        "valuation_auxiliary": "baidu",
                        "dragon_tiger_auxiliary": "sina",
                    },
                    "fund_flow_verified": True,
                }
            },
        }

    def fetch_lhb_sina(self, trade_date):
        import pandas as pd

        return pd.DataFrame({"股票代码": ["000300"]})

    def fetch_lhb_stats_sina(self, recent_days="5"):
        import pandas as pd

        return pd.DataFrame({"股票代码": ["000300"], "上榜次数": [3], "净额": [200000000.0]})

    def fetch_lhb_institutional_stats_sina(self, recent_days="5"):
        import pandas as pd

        return pd.DataFrame({"股票代码": ["000300"], "买入次数": [2], "净额": [120000000.0]})

    def fetch_tick_data(self, symbol):
        import pandas as pd

        return pd.DataFrame({"type": ["买盘", "买盘", "卖盘"], "volume": [100, 120, 60]})

    def fetch_vote_baidu(self, symbol="000300"):
        import pandas as pd

        return pd.DataFrame({"热度": [85], "排名": [12]})

    def fetch_valuation_baidu(self):
        import pandas as pd

        return pd.DataFrame({"代码": ["000300"], "市盈率": [25], "市净率": [3.2]})

    def fetch_hist(self, ticker, start_date, end_date, adjust="qfq"):
        import pandas as pd

        return pd.DataFrame(
            {"close": [10 + i * 0.1 for i in range(40)]},
            index=pd.date_range("2026-03-20", periods=40, freq="D"),
        )


class SmartMoneyAccessDegraded(SmartMoneyAccessReady):
    def validate_interface_assumptions(self, trade_date=None):
        payload = super().validate_interface_assumptions(trade_date=trade_date)
        payload["hist_fetch_verified"] = False
        payload["tencent_hist_verified"] = False
        payload["strategy_capabilities"]["smart_money"]["status_hint"] = "degraded"
        payload["strategy_capabilities"]["smart_money"]["fund_flow_verified"] = False
        return payload


class ScreenerSmartMoneyStrategyTests(unittest.TestCase):
    def test_smart_money_strategy_ready_on_tencent_hist_path(self):
        outcome = SmartMoneyStrategy(SmartMoneyAccessReady(), config={"fallbacks": {"enable_yfinance_backup": True}}).run(
            ["000300"],
            "2026-05-07",
        )
        card = outcome.cards[0]

        self.assertEqual(outcome.status, "ready")
        self.assertTrue(card.data_source_verified)
        self.assertEqual(card.signal_breakdown[0].raw_metrics["hist_primary_vendor"], "tencent")
        self.assertEqual(card.signal_breakdown[0].raw_metrics["tick_primary_vendor"], "tencent")
        self.assertNotIn("fund_flow_enhancement_unavailable", card.risk_flags)
        self.assertIn("momentum_score", card.signal_breakdown[0].raw_metrics)
        self.assertIn("joint_quality_score", card.signal_breakdown[0].raw_metrics)
        self.assertIn("continuity_score", card.signal_breakdown[0].raw_metrics)
        self.assertIn("tick_persistence_score", card.signal_breakdown[0].raw_metrics)
        self.assertIn("multi_day_persistence_score", card.signal_breakdown[0].raw_metrics)
        self.assertIn("risk_constraint_score", card.signal_breakdown[0].raw_metrics)
        self.assertIn("capital_quality_tag", card.signal_breakdown[0].raw_metrics)
        self.assertIn("capital_quality_band", card.signal_breakdown[0].raw_metrics)
        self.assertIn("continuity_grade", card.signal_breakdown[0].raw_metrics)
        self.assertIn("heat_quality_gap_score", card.signal_breakdown[0].raw_metrics)
        self.assertGreater(card.signal_breakdown[0].raw_metrics["institutional_score"], 60)
        self.assertGreater(card.signal_breakdown[0].raw_metrics["continuity_score"], 60)
        self.assertIn(card.signal_breakdown[0].raw_metrics["capital_quality_tag"], card.concept_tags)
        self.assertIn(card.signal_breakdown[0].raw_metrics["capital_quality_band"], card.concept_tags)
        self.assertEqual(card.signal_breakdown[0].raw_metrics["capital_quality_tag"], "capital_quality_high")
        self.assertEqual(card.signal_breakdown[0].raw_metrics["capital_quality_band"], "capital_band_blue_chip")
        self.assertEqual(card.trigger_reason, "smart_money_persistent_high_quality")
        self.assertEqual(card.signal_breakdown[0].raw_metrics["score_family"], "smart_money_capital_quality_v1")
        self.assertIn("threshold_snapshot", card.signal_breakdown[0].raw_metrics)
        self.assertIn("capital_quality_weight", card.signal_breakdown[0].raw_metrics)
        self.assertIn("capital_quality_summary", card.signal_breakdown[0].raw_metrics)
        self.assertIn("degraded_context", card.signal_breakdown[0].raw_metrics)
        self.assertIn("vendor_trace", card.signal_breakdown[0].raw_metrics)
        self.assertTrue(card.signal_breakdown[0].raw_metrics["degraded_context"]["effective_hist_available"])
        self.assertGreater(card.signal_breakdown[0].raw_metrics["capital_quality_weight"], 0)

    def test_smart_money_strategy_degraded_without_hist_chain(self):
        outcome = SmartMoneyStrategy(SmartMoneyAccessDegraded(), config={"fallbacks": {"enable_yfinance_backup": True}}).run(
            ["000300"],
            "2026-05-07",
        )
        card = outcome.cards[0]

        self.assertEqual(outcome.status, "degraded")
        self.assertFalse(card.data_source_verified)
        self.assertEqual(card.signal_breakdown[0].degradation_reason, "hist_fetch_unverified")
        self.assertIn("hist_primary_unavailable", card.risk_flags)
        self.assertIn("fund_flow_enhancement_unavailable", card.risk_flags)
        self.assertFalse(card.signal_breakdown[0].raw_metrics["degraded_context"]["effective_hist_available"])


class SmartMoneyAccessSpeculative(SmartMoneyAccessReady):
    def fetch_lhb_stats_sina(self, recent_days="5"):
        import pandas as pd

        return pd.DataFrame({"股票代码": ["000300"], "上榜次数": [1], "净额": [-10000000.0]})

    def fetch_lhb_institutional_stats_sina(self, recent_days="5"):
        import pandas as pd

        return pd.DataFrame({"股票代码": ["000300"], "买入次数": [0], "净额": [-5000000.0]})

    def fetch_tick_data(self, symbol):
        import pandas as pd

        return pd.DataFrame({"type": ["买盘", "买盘", "买盘", "卖盘"], "volume": [300, 260, 220, 30]})

    def fetch_vote_baidu(self, symbol="000300"):
        import pandas as pd

        return pd.DataFrame({"热度": [95], "排名": [2]})

    def fetch_valuation_baidu(self):
        import pandas as pd

        return pd.DataFrame({"代码": ["000300"], "市盈率": [120], "市净率": [12]})

    def fetch_hist(self, ticker, start_date, end_date, adjust="qfq"):
        import pandas as pd

        closes = [10, 12, 9, 14, 8, 15, 9, 16, 10, 17, 11, 18, 12, 19, 13, 20, 14, 21, 15, 22, 16, 23, 17, 24, 18, 25, 19, 26, 20, 27, 21, 28, 22, 29, 23, 30, 24, 31, 25, 32]
        return pd.DataFrame({"close": closes}, index=pd.date_range("2026-03-20", periods=len(closes), freq="D"))

    def fetch_lhb_sina(self, trade_date):
        import pandas as pd

        return pd.DataFrame({"股票代码": ["000300"], "成交额": [50000000.0]})


class ScreenerSmartMoneyStrategyRiskTests(unittest.TestCase):
    def test_smart_money_strategy_marks_speculative_flow_when_heat_and_quality_diverge(self):
        outcome = SmartMoneyStrategy(SmartMoneyAccessSpeculative(), config={"fallbacks": {"enable_yfinance_backup": True}}).run(
            ["000300"],
            "2026-05-07",
        )
        card = outcome.cards[0]

        self.assertEqual(card.signal_breakdown[0].raw_metrics["capital_quality_tag"], "capital_quality_speculative")
        self.assertEqual(card.trigger_reason, "smart_money_speculative_flow")
        self.assertIn("speculative_flow_dominant", card.risk_flags)
        self.assertIn("continuity_fragile", card.risk_flags)
        self.assertIn("overheated_valuation_mismatch", card.risk_flags)
        self.assertIn("heat_quality_gap_wide", card.risk_flags)
        self.assertLess(card.signal_breakdown[0].raw_metrics["risk_constraint_score"], 50)
        self.assertEqual(card.signal_breakdown[0].raw_metrics["capital_quality_band"], "capital_band_speculative")
        self.assertEqual(
            card.signal_breakdown[0].raw_metrics["degraded_context"]["capital_quality_tag"],
            "capital_quality_speculative",
        )
        self.assertLess(card.signal_breakdown[0].raw_metrics["capital_quality_weight"], 0)
        self.assertGreater(card.signal_breakdown[0].raw_metrics["heat_quality_gap_score"], 20)


class ValuationAccessNoMatch(SmartMoneyAccessReady):
    """H2 P0: DataFrame has no matching stock code -- must return None, not iloc[0]."""

    def fetch_valuation_baidu(self):
        import pandas as pd

        return pd.DataFrame({"代码": ["999999"], "市盈率": [25], "市净率": [3.2]})


class ValuationAccessNone(SmartMoneyAccessReady):
    """H2 P0: valuation fetch returns None -- must return None gracefully."""

    def fetch_valuation_baidu(self):
        return None


class ValuationAccessEmpty(SmartMoneyAccessReady):
    """H2 P0: valuation fetch returns empty DataFrame -- must return None gracefully."""

    def fetch_valuation_baidu(self):
        import pandas as pd

        return pd.DataFrame()


class ScreenerSmartMoneyValuationTests(unittest.TestCase):
    """P0 boundary tests for H2: valuation fallback must NOT do iloc[0] on wrong stock."""

    def test_valuation_not_found_returns_none_not_wrong_stock(self):
        """H2 FIX: when stock not in valuation_df, downstream must NOT get wrong stock data."""
        outcome = SmartMoneyStrategy(
            ValuationAccessNoMatch(), config={"fallbacks": {"enable_yfinance_backup": True}}
        ).run(["000300"], "2026-05-07")
        card = outcome.cards[0]
        # degraded_context must track that valuation was NOT available
        self.assertFalse(card.signal_breakdown[0].raw_metrics["degraded_context"]["valuation_available"])
        # No crash -- score is computed with neutral 55.0 fallback
        self.assertIsNotNone(card.screening_score)
        self.assertGreater(card.screening_score, 0)

    def test_valuation_none_returns_none_not_crash(self):
        """H2 FIX: when valuation fetch returns None, must not crash."""
        outcome = SmartMoneyStrategy(
            ValuationAccessNone(), config={"fallbacks": {"enable_yfinance_backup": True}}
        ).run(["000300"], "2026-05-07")
        card = outcome.cards[0]
        self.assertFalse(card.signal_breakdown[0].raw_metrics["degraded_context"]["valuation_available"])
        self.assertIsNotNone(card.screening_score)
        self.assertGreater(card.screening_score, 0)

    def test_valuation_empty_returns_none_not_crash(self):
        """H2 FIX: when valuation fetch returns empty DataFrame, must not crash."""
        outcome = SmartMoneyStrategy(
            ValuationAccessEmpty(), config={"fallbacks": {"enable_yfinance_backup": True}}
        ).run(["000300"], "2026-05-07")
        card = outcome.cards[0]
        self.assertFalse(card.signal_breakdown[0].raw_metrics["degraded_context"]["valuation_available"])
        self.assertIsNotNone(card.screening_score)
        self.assertGreater(card.screening_score, 0)

    def test_valuation_found_returns_score(self):
        """H2: when stock IS in valuation_df, returns a valid score (not None)."""
        outcome = SmartMoneyStrategy(
            SmartMoneyAccessReady(), config={"fallbacks": {"enable_yfinance_backup": True}}
        ).run(["000300"], "2026-05-07")
        card = outcome.cards[0]
        self.assertTrue(card.signal_breakdown[0].raw_metrics["degraded_context"]["valuation_available"])
        self.assertIn("valuation_score", card.signal_breakdown[0].raw_metrics)
        # PE=25 is in [0,35) range -> score = 55+20=75
        self.assertGreaterEqual(card.signal_breakdown[0].raw_metrics["valuation_score"], 70)


if __name__ == "__main__":
    unittest.main()
