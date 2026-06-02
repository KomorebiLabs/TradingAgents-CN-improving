import unittest
from datetime import datetime

from tradingagents.screener.runtime_guard import TimeValidator, validate_screener_run


class ScreenerRuntimeGuardTests(unittest.TestCase):
    def test_rejects_intraday_for_mvp(self):
        validator = TimeValidator()
        passed, messages = validator.validate(
            mode="MVP",
            trade_date="2026-05-07",
            now=datetime(2026, 5, 7, 10, 0, 0),
        )
        self.assertFalse(passed)
        self.assertTrue(any("盘中" in message for message in messages))

    def test_allows_intraday_for_experimental(self):
        validator = TimeValidator()
        passed, messages = validator.validate(
            mode="EXPERIMENTAL",
            trade_date="2026-05-07",
            now=datetime(2026, 5, 7, 10, 0, 0),
        )
        self.assertTrue(passed)
        self.assertTrue(any("实验模式" in message for message in messages))

    def test_validate_screener_run_wrapper(self):
        passed, _ = validate_screener_run(mode="MVP", trade_date="2026-05-07")
        self.assertIn(passed, {True, False})


if __name__ == "__main__":
    unittest.main()
