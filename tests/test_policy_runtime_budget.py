import time

from tradingagents.screener.strategies.policy import _bounded_call
from tradingagents.screener.strategies.policy import PolicyStrategy


def test_bounded_call_returns_without_waiting_for_blocked_vendor():
    started = time.monotonic()

    result, warning = _bounded_call(
        "blocked-vendor",
        lambda: time.sleep(1.0),
        timeout_seconds=0.03,
        default=None,
    )

    assert result is None
    assert "timeout" in warning.lower()
    assert time.monotonic() - started < 0.25


class _BlockedCapabilityProbe:
    def validate_interface_assumptions(self, trade_date):
        time.sleep(1.0)
        return {}

    def fetch_index_constituents(self, _code):
        return None

    def fetch_policy_news_baidu(self, *_args, **_kwargs):
        return None


def test_policy_stage_budget_covers_initial_capability_probe():
    strategy = PolicyStrategy(
        _BlockedCapabilityProbe(),
        {
            "strategies": {
                "policy": {
                    "request_timeout_seconds": 0.03,
                    "stage_timeout_seconds": 0.12,
                    "thresholds": {},
                }
            }
        },
    )
    started = time.monotonic()

    outcome = strategy.run(["600519"], "2026-08-21")

    assert time.monotonic() - started < 0.5
    assert len(outcome.cards) == 1
    assert any(
        "validate_interface_assumptions timeout" in warning
        for warning in outcome.warnings
    )
