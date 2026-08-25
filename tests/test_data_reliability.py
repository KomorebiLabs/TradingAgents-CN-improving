"""R3 data-reliability tests: vendor failure visibility, Tencent retry,
runtime adaptive degradation (circuit breaker).  All offline (mocked).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pandas as pd
import pytest

from tradingagents.screener.data_access import ScreenerDataAccess
from tradingagents.screener.vendor_http import DataSourceConfig, VendorHttp
from tradingagents.screener.vendors._guard import vendor_call


def df_ok(rows: int = 5) -> pd.DataFrame:
    return pd.DataFrame(
        {"date": [f"2026-07-{i:02d}" for i in range(1, rows + 1)], "close": [10.0 + i for i in range(rows)]}
    )


# ---------------------------------------------------------------------------
# P1: vendor_call guard
# ---------------------------------------------------------------------------


def test_vendor_call_success_passthrough(caplog):
    calls = []

    @vendor_call("test.ok")
    def fn():
        calls.append(1)
        return df_ok()

    with caplog.at_level(logging.DEBUG):
        result = fn()
    assert len(result) == 5
    assert calls == [1]
    assert "test.ok" in caplog.text


def test_vendor_call_failure_logged_and_none(caplog):
    @vendor_call("test.boom")
    def fn():
        raise RuntimeError("vendor down")

    with caplog.at_level(logging.WARNING):
        result = fn()
    assert result is None
    assert "[vendor:test.boom] raised RuntimeError: vendor down" in caplog.text


def test_vendor_call_empty_result_logged_debug(caplog):
    @vendor_call("test.empty")
    def fn():
        return pd.DataFrame()

    with caplog.at_level(logging.DEBUG):
        assert fn() is not None  # contract: empty frame passes through
    assert "[vendor:test.empty] returned empty/None" in caplog.text


# ---------------------------------------------------------------------------
# P2: Tencent direct retry with backoff
# ---------------------------------------------------------------------------


def test_tencent_direct_retries_then_succeeds(monkeypatch):
    import requests

    calls = {"n": 0}

    def fake_get(url, headers, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.exceptions.ConnectionError("reset")
        return SimpleNamespace(text="OK", raise_for_status=lambda: None)

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr(VendorHttp, "sleep_for_vendor", lambda self, v: None)

    http = VendorHttp(DataSourceConfig(max_retries=2, retry_delay=0.0))
    assert http.tencent_direct("http://x") == "OK"
    assert calls["n"] == 2


def test_tencent_direct_gives_up_logged(monkeypatch, caplog):
    import requests

    def fake_get(url, headers, timeout):
        raise requests.exceptions.ConnectionError("reset")

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr(VendorHttp, "sleep_for_vendor", lambda self, v: None)

    http = VendorHttp(DataSourceConfig(max_retries=1, retry_delay=0.0))
    with caplog.at_level(logging.WARNING):
        assert http.tencent_direct("http://x") is None
    assert "giving up after 2 attempts" in caplog.text


def test_tencent_direct_http_status_never_retried(monkeypatch, caplog):
    """Anti-ban guard: 429/403/5xx must NOT be retried (looks bot-like)."""
    import requests

    calls = {"n": 0}

    class FakeResp:
        status_code = 429

        def raise_for_status(self):
            raise requests.exceptions.HTTPError(
                "429 Client Error", response=SimpleNamespace(status_code=429)
            )

    def fake_get(url, headers, timeout):
        calls["n"] += 1
        return FakeResp()

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr(VendorHttp, "sleep_for_vendor", lambda self, v: None)

    http = VendorHttp(DataSourceConfig(max_retries=3, retry_delay=0.0))
    with caplog.at_level(logging.WARNING):
        assert http.tencent_direct("http://x") is None
    assert calls["n"] == 1  # exactly one attempt — no retry on 429
    assert "anti-ban guard" in caplog.text


# ---------------------------------------------------------------------------
# P3: runtime adaptive degradation (circuit breaker in fetch chains)
# ---------------------------------------------------------------------------


@pytest.fixture()
def silent_da(monkeypatch):
    """ScreenerDataAccess with sleeps disabled and vendors mocked."""
    monkeypatch.setattr(VendorHttp, "sleep_for_vendor", lambda self, v: None)
    da = ScreenerDataAccess({})
    return da


def test_fetch_hist_circuit_breaker_skips_dead_vendors(monkeypatch, silent_da):
    calls = {"direct": 0, "akshare": 0, "sina": 0, "baostock": 0, "yf": 0}
    monkeypatch.setattr(
        "tradingagents.screener.vendors.tencent.fetch_hist_direct",
        lambda *a, **k: (calls.__setitem__("direct", calls["direct"] + 1) or None),
    )
    monkeypatch.setattr(
        "tradingagents.screener.vendors.tencent.fetch_hist_akshare",
        lambda *a, **k: (calls.__setitem__("akshare", calls["akshare"] + 1) or None),
    )
    monkeypatch.setattr(
        "tradingagents.screener.vendors.sina.fetch_hist",
        lambda *a, **k: (calls.__setitem__("sina", calls["sina"] + 1) or None),
    )
    monkeypatch.setattr(
        "tradingagents.screener.vendors.backup.fetch_hist_baostock",
        lambda *a, **k: (calls.__setitem__("baostock", calls["baostock"] + 1) or df_ok()),
    )
    monkeypatch.setattr(
        "tradingagents.screener.vendors.backup.fetch_hist_yfinance",
        lambda *a, **k: (calls.__setitem__("yf", calls["yf"] + 1) or None),
    )

    # warm-up: all fail except baostock (4th source)
    for i in range(3):
        result = silent_da.fetch_hist(f"sh60000{i}", "2026-07-01", "2026-08-16")
        assert result is not None and len(result) == 5

    assert calls["direct"] == 3  # tried 3x then circuit opens
    assert calls["sina"] == 3
    # after circuit opens, later fetches skip dead vendors entirely
    for i in range(3, 6):
        assert silent_da.fetch_hist(f"sh6000{i}", "2026-07-01", "2026-08-16") is not None
    assert calls["direct"] == 3  # no further attempts on dead vendor
    assert calls["sina"] == 3
    assert calls["akshare"] == 3
    assert calls["baostock"] >= 6  # healthy vendor keeps serving
    assert calls["yf"] == 0  # never reached: baostock always succeeds


def test_fetch_hist_success_resets_failure_counter(monkeypatch, silent_da):
    state = {"fail": True}
    monkeypatch.setattr(
        "tradingagents.screener.vendors.tencent.fetch_hist_direct",
        lambda *a, **k: None if state["fail"] else df_ok(),
    )
    monkeypatch.setattr(
        "tradingagents.screener.vendors.backup.fetch_hist_baostock",
        lambda *a, **k: df_ok(),
    )

    # 2 consecutive failures (below threshold) — circuit stays closed
    for i in range(2):
        assert silent_da.fetch_hist(f"sh6005{i}", "2026-07-01", "2026-08-16") is not None
    assert silent_da._vendor_fail_counts["tencent_direct"] == 2
    assert not silent_da._vendor_circuit_open("tencent_direct")

    # a success resets the counter (fresh ticker to bypass the hist cache)
    state["fail"] = False
    assert silent_da.fetch_hist("sh600519", "2026-07-01", "2026-08-16") is not None
    assert silent_da._vendor_fail_counts["tencent_direct"] == 0

    # failures accumulate again from zero
    state["fail"] = True
    for i in range(3, 6):
        silent_da.fetch_hist(f"sh6005{i}", "2026-07-01", "2026-08-16")
    assert silent_da._vendor_circuit_open("tencent_direct")


def test_fund_flow_circuit_breaker_skips_repeatedly_failing_eastmoney(monkeypatch, silent_da):
    calls = {"ths": 0, "eastmoney": 0}

    monkeypatch.setattr(
        "tradingagents.screener.vendors.ths.fetch_fund_flow",
        lambda *args, **kwargs: calls.__setitem__("ths", calls["ths"] + 1),
    )
    monkeypatch.setattr(
        "tradingagents.screener.vendors.misc.fetch_fund_flow_em",
        lambda *args, **kwargs: calls.__setitem__("eastmoney", calls["eastmoney"] + 1),
    )

    for _ in range(6):
        assert silent_da.fetch_fund_flow() is None

    assert calls == {"ths": 3, "eastmoney": 3}
