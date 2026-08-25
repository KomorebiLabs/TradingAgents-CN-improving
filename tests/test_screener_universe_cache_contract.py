import json
from datetime import datetime, timedelta

from tradingagents.screener.universe import (
    UniverseBuildResult,
    load_universe_cache,
    save_universe_cache,
    build_screening_universe,
)
import pandas as pd
import pytest


def _result():
    return UniverseBuildResult(tickers=["600000"], metadata={"profile": "MVP"})


def test_universe_cache_requires_matching_date_and_source_signature(tmp_path):
    cache = tmp_path / "universe.json"
    now = datetime(2026, 8, 24, 17, 0)
    save_universe_cache(
        cache,
        _result(),
        trade_date="2026-08-24",
        source_signature="csindex:000300",
        now=now,
    )

    assert load_universe_cache(
        cache,
        trade_date="2026-08-24",
        source_signature="csindex:000300",
        now=now,
    ) is not None
    assert load_universe_cache(cache, trade_date="2026-08-25", now=now) is None
    assert load_universe_cache(cache, source_signature="csindex:000905", now=now) is None


def test_expired_universe_cache_is_not_returned_as_current(tmp_path):
    cache = tmp_path / "universe.json"
    built_at = datetime(2026, 8, 24, 9, 0)
    save_universe_cache(cache, _result(), ttl_hours=2, now=built_at)

    assert load_universe_cache(cache, now=built_at + timedelta(hours=3)) is None


def test_corrupt_or_legacy_universe_cache_fails_closed(tmp_path):
    cache = tmp_path / "universe.json"
    cache.write_text("{broken", encoding="utf-8")
    assert load_universe_cache(cache) is None

    cache.write_text(json.dumps({"tickers": ["600000"], "metadata": {}}), encoding="utf-8")
    assert load_universe_cache(cache) is None


def test_empty_universe_cache_is_never_treated_as_fresh(tmp_path):
    cache = tmp_path / "universe.json"
    save_universe_cache(
        cache,
        UniverseBuildResult(tickers=[], metadata={"profile": "FOCUSED"}),
        trade_date="2026-08-24",
        source_signature="focused:index:000300",
    )

    assert load_universe_cache(
        cache,
        trade_date="2026-08-24",
        source_signature="focused:index:000300",
    ) is None


def test_focused_index_failure_is_explicit_and_not_cached(tmp_path, monkeypatch):
    class EmptyDataAccess:
        def fetch_index_constituents(self, _code):
            return None

    monkeypatch.setattr(
        "tradingagents.screener.universe.get_screener_cache_dir",
        lambda _config: tmp_path,
    )
    config = {
        "universe": {
            "profile": "FOCUSED",
            "focus_type": "index",
            "focus_value": "000300",
        }
    }

    with pytest.raises(RuntimeError, match="FOCUSED.*000300"):
        build_screening_universe(
            "FOCUSED", config, EmptyDataAccess(), trade_date="2026-08-24"
        )

    assert list(tmp_path.glob("universe_focused_*.json")) == []

def test_universe_builder_does_not_reuse_previous_trade_date_cache(tmp_path, monkeypatch):
    calls = []

    class FakeDataAccess:
        def fetch_index_constituents(self, code):
            calls.append(code)
            return pd.DataFrame({"成分券代码": ["600000"]})

    monkeypatch.setattr(
        "tradingagents.screener.universe.get_screener_cache_dir",
        lambda _config: tmp_path,
    )
    config = {"universe": {"profile": "MVP"}}

    build_screening_universe("MVP", config, FakeDataAccess(), trade_date="2026-08-24")
    build_screening_universe("MVP", config, FakeDataAccess(), trade_date="2026-08-25")

    assert len(calls) == 4
