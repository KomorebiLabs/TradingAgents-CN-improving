"""Regression tests for real-data vendor fallback and symbol normalization."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("600519", "600519.SS"),
        ("600519.SH", "600519.SS"),
        ("000001.SZ", "000001.SZ"),
        ("AAPL", "AAPL"),
    ],
)
def test_normalize_yfinance_symbol_for_cn_equities(symbol, expected):
    from tradingagents.dataflows.stockstats_utils import normalize_yfinance_symbol

    assert normalize_yfinance_symbol(symbol) == expected
