import unittest

from tradingagents.screener.models import DataFreshness, SignalCard, SignalEvidence


class ScreenerModelTests(unittest.TestCase):
    def test_signal_card_serializes(self):
        freshness = DataFreshness(
            source="akshare",
            trade_date="2026-05-07",
            fetched_at="2026-05-07T10:00:00",
            status="fresh",
        )
        evidence = SignalEvidence(
            strategy="technical",
            score=80.0,
            reason="Strong momentum",
            freshness=[freshness],
        )
        card = SignalCard(
            ticker="600519.SH",
            raw_code="600519",
            exchange="SH",
            company_name="贵州茅台",
            trade_date="2026-05-07",
            strategy_sources=["technical"],
            signal_breakdown=[evidence],
            trigger_reason="technical resonance",
            initial_confidence=85.0,
            screening_score=82.0,
        )

        payload = card.model_dump()
        self.assertEqual(payload["ticker"], "600519.SH")
        self.assertEqual(payload["signal_breakdown"][0]["strategy"], "technical")

    def test_signal_card_rejects_out_of_range_scores(self):
        with self.assertRaises(ValueError):
            SignalCard(
                ticker="600519.SH",
                raw_code="600519",
                exchange="SH",
                company_name="贵州茅台",
                trade_date="2026-05-07",
                trigger_reason="invalid",
                initial_confidence=101.0,
                screening_score=80.0,
            )


if __name__ == "__main__":
    unittest.main()
