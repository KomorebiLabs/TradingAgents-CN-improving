"""Offline contracts for tool-to-vendor argument forwarding."""

from __future__ import annotations

import pytest

import tradingagents.default_config as default_config
from tradingagents.agents.utils import news_data_tools, technical_indicators_tools
from tradingagents.dataflows import interface
from tradingagents.dataflows.config import set_config


@pytest.fixture(autouse=True)
def _reset_config():
    set_config(default_config.DEFAULT_CONFIG.copy())
    yield
    set_config(default_config.DEFAULT_CONFIG.copy())


def test_indicator_tool_route_preserves_cutoff_arguments(monkeypatch):
    captured = {}

    def fake_indicator(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return "indicator-result"

    monkeypatch.setattr(interface, "_load_attr", lambda _module, _attr: fake_indicator)
    set_config(
        {
            **default_config.DEFAULT_CONFIG,
            "tool_vendors": {"get_indicators": "tencent_finance"},
        }
    )

    result = interface.route_to_vendor(
        "get_indicators", "sh600519", "rsi", "2026-08-20", 30
    )

    assert result == "indicator-result"
    assert captured["args"] == ("sh600519", "rsi", "2026-08-20", 30)
    assert captured["kwargs"] == {}


def test_news_tool_route_preserves_start_and_end_dates(monkeypatch):
    captured = {}

    def fake_news(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return "news-result"

    monkeypatch.setattr(interface, "_load_attr", lambda _module, _attr: fake_news)
    set_config(
        {
            **default_config.DEFAULT_CONFIG,
            "tool_vendors": {"get_news": "ths_data"},
        }
    )

    result = interface.route_to_vendor(
        "get_news", "600519", "2026-08-01", "2026-08-20"
    )

    # A6: news text passes through the untrusted-content wrapper
    # (salted delimiters + injection filter) — raw payload preserved inside.
    assert "news-result" in result
    assert "UNTRUSTED_DATA_" in result
    assert captured["args"] == ("600519", "2026-08-01", "2026-08-20")
    assert captured["kwargs"] == {}


def test_indicator_tool_wrapper_forwards_cutoff_to_router(monkeypatch):
    captured = {}

    def fake_route(method, *args, **kwargs):
        captured["method"] = method
        captured["args"] = args
        captured["kwargs"] = kwargs
        return "wrapped-indicator-result"

    monkeypatch.setattr(technical_indicators_tools, "route_to_vendor", fake_route)

    result = technical_indicators_tools.get_indicators.invoke(
        {
            "symbol": "sh600519",
            "indicator": "rsi",
            "curr_date": "2026-08-20",
            "look_back_days": 30,
        }
    )

    assert result == "wrapped-indicator-result"
    assert captured == {
        "method": "get_indicators",
        "args": ("sh600519", "rsi", "2026-08-20", 30),
        "kwargs": {},
    }


def test_news_tool_wrapper_forwards_date_range_to_router(monkeypatch):
    captured = {}

    def fake_route(method, *args, **kwargs):
        captured["method"] = method
        captured["args"] = args
        captured["kwargs"] = kwargs
        return "wrapped-news-result"

    monkeypatch.setattr(news_data_tools, "_get_rag_middleware", lambda: None)
    monkeypatch.setattr(news_data_tools, "route_to_vendor", fake_route)

    result = news_data_tools.get_news.invoke(
        {
            "ticker": "600519",
            "start_date": "2026-08-01",
            "end_date": "2026-08-20",
        }
    )

    assert result == "wrapped-news-result"
    assert captured == {
        "method": "get_news",
        "args": ("600519", "2026-08-01", "2026-08-20"),
        "kwargs": {},
    }
