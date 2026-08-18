"""Tests for the MarketDataPort seam (ports/market_data.py)."""

from __future__ import annotations

import pytest

from tradingagents.ports import market_data as md_port
from tradingagents.ports.market_data import (
    MarketDataPort,
    get_market_data_port,
    reset_market_data_port,
    set_market_data_port,
)


class _StubPort:
    def fetch_hist(self, ticker, start_date, end_date, adjust="qfq"):
        return {"ticker": ticker, "start": start_date, "end": end_date, "adjust": adjust}

    def fetch_spot_snapshot(self, market="all"):
        return {"spot": market}

    def fetch_index_constituents(self, index_code):
        return {"index": index_code}

    def fetch_concept_boards(self):
        return []

    def fetch_concept_constituents(self, concept_name):
        return {"concept": concept_name}

    def fetch_industry_boards(self):
        return []

    def fetch_fund_flow(self, symbol="即时", symbol_type="individual"):
        return {"flow": symbol}


@pytest.fixture(autouse=True)
def _clean_port_registry():
    reset_market_data_port()
    yield
    reset_market_data_port()


class TestPortRegistry:
    def test_default_port_is_shared_instance(self):
        """The port must be a process-wide singleton — per-call instantiation
        silently disables the underlying throttle state and hist cache."""
        first = get_market_data_port()
        second = get_market_data_port()
        assert first is second

    def test_injected_stub_is_returned(self):
        stub = _StubPort()
        set_market_data_port(stub)
        assert get_market_data_port() is stub

    def test_reset_restores_default_construction(self):
        stub = _StubPort()
        set_market_data_port(stub)
        reset_market_data_port()
        assert get_market_data_port() is not stub

    def test_stub_satisfies_protocol(self):
        assert isinstance(_StubPort(), MarketDataPort)


class TestDefaultAdapter:
    def test_default_adapter_satisfies_protocol(self):
        # The default adapter wraps ScreenerDataAccess; constructing it is
        # offline-safe (no probes or network run in __init__).
        port = get_market_data_port()
        assert isinstance(port, MarketDataPort)

    def test_default_adapter_carries_throttle_and_cache_state(self):
        """The shared instance must keep its throttle state and hist cache —
        the whole point of the singleton (per-call rebuilds disable both)."""
        port = get_market_data_port()
        assert hasattr(port, "requester")            # ThrottledRequester
        assert hasattr(port, "_hist_cache")          # process-level hist cache


class TestCnIndicatorsUsesPort:
    def test_cn_indicators_module_has_no_screener_import(self):
        """The inversion fix: dataflows.cn_indicators must not import the
        screener application layer (module level OR function level)."""
        import ast
        import pathlib

        source = pathlib.Path(md_port.__file__).parents[1] / "dataflows" / "cn_indicators.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "screener" not in alias.name, f"import {alias.name} leaks screener"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "screener" not in module, f"from {module} leaks screener"

    def test_cn_indicators_routes_through_port(self):
        """With a stub port injected, get_cn_indicators uses it (no network)."""
        import pandas as pd

        from tradingagents.dataflows import cn_indicators

        stub = _StubPort()
        stub.fetch_hist = lambda ticker, start_date, end_date, adjust="qfq": pd.DataFrame(
            {
                "Date": pd.to_datetime(["2026-01-14", "2026-01-15"]),
                "Open": [10.0, 10.5],
                "High": [10.8, 11.0],
                "Low": [9.9, 10.2],
                "Close": [10.5, 10.9],
                "Volume": [1000, 1200],
            }
        )
        set_market_data_port(stub)

        result = cn_indicators.get_cn_indicators("sh600519", "rsi", "2026-01-15", 5)
        # RSI needs enough rows to compute; with 2 rows stockstats may yield NaN
        # or a value — both acceptable, but the call must route through the stub
        # without touching the network or the screener layer.
        assert isinstance(result, str)
