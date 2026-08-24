"""Unified vendor health contract tests."""

from __future__ import annotations

from tradingagents.dataflows.vendor_health import VendorHealthTracker, classify_provider_text


def test_tracker_keeps_status_counts_and_compat_failure_rate():
    tracker = VendorHealthTracker()
    tracker.record("cninfo.official", status="ok", elapsed=0.2)
    tracker.record("cninfo.official", status="blocked", elapsed=0.4, error="HTTP 403")
    tracker.record("tushare.pro", status="auth_error", elapsed=0.1, error="permission denied")

    snapshot = tracker.snapshot()

    assert snapshot["cninfo.official"]["calls"] == 2
    assert snapshot["cninfo.official"]["failures"] == 1
    assert snapshot["cninfo.official"]["status_counts"] == {"blocked": 1, "ok": 1}
    assert snapshot["tushare.pro"]["last_status"] == "auth_error"
    assert "permission denied" in snapshot["tushare.pro"]["last_error"]


def test_tracker_redacts_secrets_from_last_error():
    tracker = VendorHealthTracker()
    tracker.record(
        "tushare.pro",
        status="auth_error",
        elapsed=0.1,
        error="token=super-secret-value",
    )

    error = tracker.snapshot()["tushare.pro"]["last_error"]
    assert "super-secret-value" not in error
    assert "[REDACTED]" in error


def test_provider_text_distinguishes_permission_from_empty():
    assert classify_provider_text("No Tushare Pro permission for income") == "auth_error"
    assert classify_provider_text("No news found") == "empty"
