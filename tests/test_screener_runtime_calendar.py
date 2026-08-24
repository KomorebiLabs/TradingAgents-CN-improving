from datetime import datetime

from tradingagents.screener.runtime_guard import RuntimeTimeConfig, TimeValidator


def test_historical_non_trading_day_is_rejected_by_calendar():
    validator = TimeValidator(
        RuntimeTimeConfig(),
        trading_day_checker=lambda _day: False,
    )

    passed, warnings = validator.validate(
        mode="MVP",
        trade_date="2026-02-17",
        now=datetime(2026, 2, 20, 18, 0),
    )

    assert passed is False
    assert any("非交易日" in warning for warning in warnings)


def test_full_mode_cannot_silently_run_intraday():
    validator = TimeValidator(
        RuntimeTimeConfig(),
        trading_day_checker=lambda _day: True,
    )

    passed, warnings = validator.validate(
        mode="FULL",
        trade_date="2026-08-24",
        now=datetime(2026, 8, 24, 10, 30),
    )

    assert passed is False
    assert any("盘中" in warning for warning in warnings)
