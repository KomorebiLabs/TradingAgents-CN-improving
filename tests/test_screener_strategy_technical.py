import unittest
import pandas as pd

from tradingagents.screener.strategies.technical import TechnicalStrategy


class FakeAccess:
    def validate_interface_assumptions(self, trade_date=None):
        return {
            "fund_flow_bulk_verified": False,
            "hist_fetch_verified": False,
            "tencent_hist_verified": False,
            "yfinance_hist_verified": True,
            "fund_flow_fallback_vendor": "yfinance",
            "hist_fetch_primary_vendor": "tencent",
            "hist_fetch_secondary_vendor": "tencent",
            "hist_fetch_fallback_vendor": "yfinance",
            "freshness": [],
            "warnings": [],
        }

    def fetch_tencent_hist(self, ticker, start_date, end_date):
        return pd.DataFrame()

    def fetch_yfinance_hist(self, ticker, start_date, end_date):
        return pd.DataFrame(
            {
                "Open": [1.0, 1.1, 1.2],
                "Close": [1.1, 1.2, 1.3],
                "Volume": [100, 120, 180],
            },
            index=pd.to_datetime(["2026-05-05", "2026-05-06", "2026-05-07"]),
        )


class ScreenerTechnicalStrategyTests(unittest.TestCase):
    def test_technical_strategy_attaches_yfinance_hist_fallback(self):
        strategy = TechnicalStrategy(
            data_access=FakeAccess(),
            config={
                "strategies": {
                    "technical": {
                        "lookback_days": 100,
                        "allow_yfinance_fallback": True,
                    }
                }
            },
        )

        outcome = strategy.run(["000300"], "2026-05-07")
        card = outcome.cards[0]

        self.assertEqual(outcome.status, "degraded")
        self.assertIn("using_yfinance_hist_fallback", card.risk_flags)
        self.assertIn("yfinance_hist_data_attached", card.risk_flags)
        self.assertEqual(card.evidence_snapshot["hist_preview"]["rows"], 3)
        self.assertEqual(card.evidence_snapshot["hist_fallback_vendor"], "yfinance")
        self.assertEqual(card.trigger_reason, "technical_momentum_yfinance_fallback")
        self.assertIn("trend_alignment_score", card.signal_breakdown[0].raw_metrics)
        self.assertIn("momentum_score", card.signal_breakdown[0].raw_metrics)
        self.assertIn("trend_consistency_score", card.signal_breakdown[0].raw_metrics)
        self.assertIn("structure_risk_score", card.signal_breakdown[0].raw_metrics)
        self.assertEqual(card.signal_breakdown[0].raw_metrics["score_family"], "technical_hist_trend_v1")
        self.assertIn("degraded_context", card.signal_breakdown[0].raw_metrics)
        self.assertIn("vendor_trace", card.signal_breakdown[0].raw_metrics)
        self.assertFalse(card.signal_breakdown[0].raw_metrics["degraded_context"]["fund_flow_verified"])

    def test_technical_strategy_prefers_tencent_hist_when_available(self):
        class TencentFirstAccess(FakeAccess):
            def validate_interface_assumptions(self, trade_date=None):
                payload = super().validate_interface_assumptions(trade_date=trade_date)
                payload["tencent_hist_verified"] = True
                payload["yfinance_hist_verified"] = True
                return payload

            def fetch_tencent_hist(self, ticker, start_date, end_date):
                return pd.DataFrame(
                    {
                        "Open": [2.0, 2.1],
                        "Close": [2.2, 2.3],
                        "Volume": [220, 260],
                    },
                    index=["2026-05-06", "2026-05-07"],
                )

            def fetch_yfinance_hist(self, ticker, start_date, end_date):
                raise AssertionError("yfinance should not be used when Tencent fallback succeeds")

        strategy = TechnicalStrategy(
            data_access=TencentFirstAccess(),
            config={
                "strategies": {
                    "technical": {
                        "lookback_days": 100,
                        "allow_yfinance_fallback": True,
                    }
                }
            },
        )

        outcome = strategy.run(["000300"], "2026-05-07")
        card = outcome.cards[0]

        self.assertIn("using_tencent_hist_fallback", card.risk_flags)
        self.assertNotIn("using_yfinance_hist_fallback", card.risk_flags)
        self.assertEqual(card.evidence_snapshot["hist_fallback_vendor"], "tencent")
        self.assertEqual(card.trigger_reason, "technical_momentum_tencent_fallback")
        self.assertIn("tencent_hist_fallback", card.concept_tags)
        self.assertEqual(
            card.signal_breakdown[0].raw_metrics["vendor_trace"]["hist_fallback_vendor"],
            "tencent",
        )

    def test_technical_strategy_flags_extended_structure_risk(self):
        class RiskyStructureAccess(FakeAccess):
            def validate_interface_assumptions(self, trade_date=None):
                payload = super().validate_interface_assumptions(trade_date=trade_date)
                payload["tencent_hist_verified"] = True
                payload["fund_flow_bulk_verified"] = True
                return payload

            def fetch_tencent_hist(self, ticker, start_date, end_date):
                return pd.DataFrame(
                    {
                        "Close": [
                            10, 10.5, 11, 10.8, 11.5, 11.0, 12.5, 11.2, 13.5, 11.4,
                            14.5, 11.6, 15.5, 11.8, 16.5, 12.0, 17.5, 12.2, 18.5, 12.4,
                            19.5, 12.6, 20.5, 12.8, 21.5, 13.0, 22.5, 13.2, 23.5, 13.4,
                            24.5, 13.6, 25.5, 13.8, 26.5, 14.0, 27.5, 14.2, 28.5, 18.5,
                        ],
                        "Volume": [
                            100, 105, 110, 120, 130, 140, 150, 160, 170, 180,
                            190, 200, 220, 240, 260, 280, 300, 330, 360, 390,
                            420, 450, 480, 520, 560, 600, 640, 690, 740, 800,
                            860, 930, 1000, 1080, 1160, 1250, 1350, 1460, 1580, 4200,
                        ],
                    },
                    index=pd.date_range("2026-03-29", periods=40, freq="D"),
                )

        strategy = TechnicalStrategy(
            data_access=RiskyStructureAccess(),
            config={"strategies": {"technical": {"lookback_days": 100, "allow_yfinance_fallback": True}}},
        )

        outcome = strategy.run(["000300"], "2026-05-07")
        card = outcome.cards[0]

        self.assertIn("trend_structure_extended", card.risk_flags)
        self.assertLessEqual(card.signal_breakdown[0].raw_metrics["structure_risk_score"], 45)

    def test_technical_strategy_exposes_trend_failure_semantics(self):
        class FailureTrendAccess(FakeAccess):
            def validate_interface_assumptions(self, trade_date=None):
                payload = super().validate_interface_assumptions(trade_date=trade_date)
                payload["tencent_hist_verified"] = True
                payload["fund_flow_bulk_verified"] = True
                return payload

            def fetch_tencent_hist(self, ticker, start_date, end_date):
                return pd.DataFrame(
                    {
                        "Close": [20, 19, 18, 17, 16, 15, 16, 15, 14, 13, 12, 11, 10, 9, 8],
                        "Volume": [300, 290, 280, 270, 260, 250, 240, 220, 200, 180, 160, 150, 140, 130, 120],
                    },
                    index=pd.date_range("2026-04-20", periods=15, freq="D"),
                )

        strategy = TechnicalStrategy(
            data_access=FailureTrendAccess(),
            config={"strategies": {"technical": {"lookback_days": 100, "allow_yfinance_fallback": True}}},
        )

        outcome = strategy.run(["000300"], "2026-05-07")
        card = outcome.cards[0]

        self.assertIn(card.signal_breakdown[0].raw_metrics["trend_grade"], {"recovery", "transition"})
        self.assertIn("trend_failure_streak_high", card.risk_flags)

    def test_technical_strategy_exposes_volume_quality_metrics(self):
        class VolumeAwareAccess(FakeAccess):
            def validate_interface_assumptions(self, trade_date=None):
                payload = super().validate_interface_assumptions(trade_date=trade_date)
                payload["tencent_hist_verified"] = True
                payload["fund_flow_bulk_verified"] = True
                return payload

            def fetch_tencent_hist(self, ticker, start_date, end_date):
                closes = [10 + i * 0.35 for i in range(39)] + [25.0]
                volumes = [100 + i * 10 for i in range(39)] + [3800]
                return pd.DataFrame(
                    {
                        "Close": closes,
                        "Volume": volumes,
                    },
                    index=pd.date_range("2026-03-29", periods=40, freq="D"),
                )

        strategy = TechnicalStrategy(
            data_access=VolumeAwareAccess(),
            config={"strategies": {"technical": {"lookback_days": 100, "allow_yfinance_fallback": True}}},
        )

        outcome = strategy.run(["000300"], "2026-05-07")
        card = outcome.cards[0]

        self.assertIn("volume_confirmation_score", card.signal_breakdown[0].raw_metrics)
        self.assertIn("breakout_quality_score", card.signal_breakdown[0].raw_metrics)
        self.assertIn("volume_price_divergence_score", card.signal_breakdown[0].raw_metrics)
        self.assertIn("signal_consistency_index", card.signal_breakdown[0].raw_metrics)
        self.assertIn("threshold_snapshot", card.signal_breakdown[0].raw_metrics)
        self.assertGreater(card.signal_breakdown[0].raw_metrics["volume_spike_ratio"], 1.8)
        self.assertIn("volume_exhaustion_risk", card.risk_flags)


if __name__ == "__main__":
    unittest.main()
