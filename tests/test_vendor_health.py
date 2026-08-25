"""R3-2 vendor-health monitor tests. All offline, mocked, tracker reset per test."""

from __future__ import annotations

import pandas as pd
import pytest

from tradingagents.screener.data_access import ScreenerDataAccess
from tradingagents.screener.vendors._guard import TRACKER as health
from tradingagents.screener.vendors._guard import VendorHealth, VendorHealthTracker, vendor_call


@pytest.fixture(autouse=True)
def _reset_health():
    health.reset()
    yield
    health.reset()


# ---------------------------------------------------------------------------
# VendorHealthTracker
# ---------------------------------------------------------------------------


def test_tracker_counts_and_failure_rate():
    t = VendorHealthTracker()
    t.record("a", ok=True, elapsed=0.5)
    t.record("a", ok=True, elapsed=0.3)
    t.record("a", ok=False, elapsed=1.0, error="boom")
    snap = t.snapshot()
    h = snap["a"]
    assert h["calls"] == 3
    assert h["failures"] == 1
    assert h["failure_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert h["avg_seconds"] == pytest.approx(0.6)
    assert h["last_error"] == "boom"


def test_tracker_reset():
    t = VendorHealthTracker()
    t.record("a", ok=True, elapsed=0.1)
    t.reset()
    assert t.snapshot() == {}


def test_tracker_summary_lines():
    t = VendorHealthTracker()
    t.record("x", ok=False, elapsed=0.2, error="conn reset")
    assert any("calls=1 fail=1 rate=100.0%" in line for line in t.summary_lines())


# ---------------------------------------------------------------------------
# vendor_call integration (records into shared TRACKER)
# ---------------------------------------------------------------------------


def test_vendor_call_records_success_and_failure():
    @vendor_call("it.ok")
    def ok():
        return pd.DataFrame({"c": [1.0, 2.0]})

    @vendor_call("it.fail")
    def fail():
        raise RuntimeError("down")

    ok()
    fail()
    snap = health.snapshot()
    assert snap["it.ok"]["calls"] == 1
    assert snap["it.ok"]["failures"] == 0
    assert snap["it.fail"]["calls"] == 1
    assert snap["it.fail"]["failures"] == 1
    assert "RuntimeError" in snap["it.fail"]["last_error"]


def test_vendor_call_empty_result_counts_as_degraded():
    @vendor_call("it.empty")
    def empty():
        return pd.DataFrame()

    empty()
    assert health.snapshot()["it.empty"]["failures"] == 1


def test_vendor_call_classifies_timeout_in_shared_health_contract():
    @vendor_call("it.timeout")
    def timed_out():
        raise TimeoutError("provider request timeout")

    assert timed_out() is None
    assert health.snapshot()["it.timeout"]["last_status"] == "timeout"


# ---------------------------------------------------------------------------
# data_access integration
# ---------------------------------------------------------------------------


def test_data_access_health_and_cache_stats(monkeypatch, silent_da_factory):
    da = silent_da_factory()
    # mock the decorated vendor fn (keep the guard so health records it)
    mock_direct = vendor_call("mocked.direct")(
        lambda *a, **k: pd.DataFrame({"date": ["2026-07-01", "2026-07-02"], "close": [10.0, 11.0]})
    )
    monkeypatch.setattr("tradingagents.screener.vendors.tencent.fetch_hist_direct", mock_direct)

    r1 = da.fetch_hist("sh600519", "2026-07-01", "2026-08-16")
    r2 = da.fetch_hist("sh600519", "2026-07-01", "2026-08-16")  # cache hit
    assert r1 is not None and r2 is not None

    cache = da.get_cache_stats()
    assert cache["hist_cache_hits"] == 1
    assert cache["hist_cache_misses"] == 1
    assert cache["hist_cache_hit_ratio"] == pytest.approx(0.5)

    vh = da.get_vendor_health_snapshot()
    assert vh.get("mocked.direct", {}).get("calls", 0) >= 1

    da.reset_vendor_health()
    assert da.get_vendor_health_snapshot() == {}


def test_repeated_capability_validation_does_not_erase_same_run_health(monkeypatch, silent_da_factory):
    da = silent_da_factory()
    health.record("universe.index", status="ok", elapsed=0.1)
    monkeypatch.setattr(da, "_load_or_run_probes", lambda **_kwargs: {"warnings": []})

    da.validate_interface_assumptions(trade_date="2026-08-24")

    assert da.get_vendor_health_snapshot()["universe.index"]["calls"] == 1


@pytest.fixture()
def silent_da_factory(monkeypatch):
    from tradingagents.screener.vendor_http import VendorHttp

    monkeypatch.setattr(VendorHttp, "sleep_for_vendor", lambda self, v: None)
    return lambda: ScreenerDataAccess({})
