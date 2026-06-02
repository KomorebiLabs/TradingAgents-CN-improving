"""Tests for memory_manager.py."""
import json
import tempfile
from datetime import date, timedelta

import pytest

from tradingagents.agents.utils.memory_manager import (
    save_conclusion_summary,
    load_historical_conclusion,
    _get_memory_path,
    _sanitize_ticker,
    DEFAULT_TTL_DAYS,
)


class TestSanitizeTicker:
    def test_no_change_for_normal_ticker(self):
        assert _sanitize_ticker("300750") == "300750"
        assert _sanitize_ticker("AAPL") == "AAPL"

    def test_removes_path_separators(self):
        assert _sanitize_ticker("TSLA/USD") == "TSLA_USD"
        assert _sanitize_ticker("a/b\\c") == "a_b_c"


class TestGetMemoryPath:
    def test_path_contains_ticker_and_date(self, tmp_path):
        path = _get_memory_path("300750", "2026-05-20", memory_dir=tmp_path)
        assert "300750" in path.name
        assert "2026-05-20" in path.name
        assert path.suffix == ".json"

    def test_path_in_specified_dir(self, tmp_path):
        path = _get_memory_path("TEST", "2026-05-20", memory_dir=tmp_path)
        assert path.parent == tmp_path

    def test_creates_dir_if_missing(self, tmp_path):
        subdir = tmp_path / "nested"
        path = _get_memory_path("T", "2026-05-20", memory_dir=subdir)
        assert subdir.exists()


class TestSaveAndLoad:
    def test_save_and_load_roundtrip(self, tmp_path):
        ticker = "300750"
        trade_date = "2026-05-20"
        summary = {"ticker": ticker, "trade_date": trade_date, "summary": "test"}

        path = save_conclusion_summary(ticker, trade_date, summary, memory_dir=tmp_path)
        assert path.exists()

        loaded = load_historical_conclusion(ticker, memory_dir=tmp_path)
        assert loaded is not None
        assert loaded["ticker"] == ticker
        assert loaded["summary"] == "test"

    def test_complex_summary_roundtrip(self, tmp_path):
        ticker = "600519"
        trade_date = "2026-05-18"
        summary = {
            "ticker": ticker,
            "trade_date": trade_date,
            "summary": "政策驱动，突破有效",
            "dimensions": {"policy": 0.82, "technical": 0.75, "smart_money": 0.68},
            "final_decision": "买入",
            "confidence": "高",
            "key_reasons": ["突破信号确认", "主力资金流入"],
            "risks": ["量价背离风险"],
        }

        save_conclusion_summary(ticker, trade_date, summary, memory_dir=tmp_path)
        loaded = load_historical_conclusion(ticker, memory_dir=tmp_path)

        assert loaded is not None
        assert loaded["confidence"] == "高"
        assert loaded["dimensions"]["policy"] == 0.82
        assert len(loaded["key_reasons"]) == 2


class TestTTL:
    def test_expired_ttl_returns_none(self, tmp_path):
        ticker = "300750"
        old_date = (date.today() - timedelta(days=10)).isoformat()
        summary = {"ticker": ticker, "trade_date": old_date, "summary": "stale"}

        save_conclusion_summary(ticker, old_date, summary, memory_dir=tmp_path)
        result = load_historical_conclusion(ticker, memory_dir=tmp_path, ttl_days=7)
        assert result is None

    def test_within_ttl_returns_entry(self, tmp_path):
        ticker = "300750"
        recent_date = (date.today() - timedelta(days=3)).isoformat()
        summary = {"ticker": ticker, "trade_date": recent_date, "summary": "fresh"}

        save_conclusion_summary(ticker, recent_date, summary, memory_dir=tmp_path)
        result = load_historical_conclusion(ticker, memory_dir=tmp_path, ttl_days=7)
        assert result is not None
        assert result["summary"] == "fresh"

    def test_boundary_exactly_ttl_days(self, tmp_path):
        ticker = "300750"
        boundary_date = (date.today() - timedelta(days=7)).isoformat()
        summary = {"ticker": ticker, "trade_date": boundary_date, "summary": "boundary"}

        save_conclusion_summary(ticker, boundary_date, summary, memory_dir=tmp_path)
        result = load_historical_conclusion(ticker, memory_dir=tmp_path, ttl_days=7)
        assert result is not None

    def test_one_day_over_ttl(self, tmp_path):
        ticker = "300750"
        over_date = (date.today() - timedelta(days=8)).isoformat()
        summary = {"ticker": ticker, "trade_date": over_date, "summary": "over"}

        save_conclusion_summary(ticker, over_date, summary, memory_dir=tmp_path)
        result = load_historical_conclusion(ticker, memory_dir=tmp_path, ttl_days=7)
        assert result is None


class TestMultipleEntries:
    def test_most_recent_wins_when_multiple(self, tmp_path):
        ticker = "300750"
        older = (date.today() - timedelta(days=2)).isoformat()
        newer = (date.today() - timedelta(days=1)).isoformat()

        save_conclusion_summary(ticker, older, {"ticker": ticker, "trade_date": older, "summary": "old"}, memory_dir=tmp_path)
        save_conclusion_summary(ticker, newer, {"ticker": ticker, "trade_date": newer, "summary": "newer"}, memory_dir=tmp_path)

        result = load_historical_conclusion(ticker, memory_dir=tmp_path)
        assert result is not None
        assert result["summary"] == "newer"


class TestTickerIsolation:
    def test_different_ticker_no_cross_contamination(self, tmp_path):
        save_conclusion_summary(
            "300750", "2026-05-20", {"ticker": "300750"}, memory_dir=tmp_path
        )
        result = load_historical_conclusion("600519", memory_dir=tmp_path)
        assert result is None

    def test_same_ticker_different_dates(self, tmp_path):
        ticker = "300750"
        date1 = (date.today() - timedelta(days=1)).isoformat()
        date2 = (date.today() - timedelta(days=2)).isoformat()

        save_conclusion_summary(ticker, date1, {"ticker": ticker, "trade_date": date1, "summary": "d1"}, memory_dir=tmp_path)
        save_conclusion_summary(ticker, date2, {"ticker": ticker, "trade_date": date2, "summary": "d2"}, memory_dir=tmp_path)

        result = load_historical_conclusion(ticker, memory_dir=tmp_path)
        assert result["summary"] == "d1"


class TestNonexistentMemory:
    def test_empty_dir_returns_none(self, tmp_path):
        result = load_historical_conclusion("NEVER_EXISTED", memory_dir=tmp_path)
        assert result is None

    def test_nonexistent_dir_returns_none(self, tmp_path):
        result = load_historical_conclusion("SOME_TICKER", memory_dir=tmp_path / "does_not_exist")
        assert result is None
