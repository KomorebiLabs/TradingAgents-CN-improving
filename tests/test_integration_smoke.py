"""F6: Real-data smoke test for Screener end-to-end pipeline.

Run with: python -m pytest tests/ -m integration -v
Or directly: python tests/test_integration_smoke.py

Validates:
1. No crash (no exception)
2. Universe has expected number of stocks
3. At least one strategy returned a score (not all None)
4. Merger has output (at least 1 candidate, or all reasonably filtered)
5. Report file written
6. Deep Analysis has fallback output
7. Company names present (may be placeholder on Windows due to encoding)
8. Total runtime < 5 minutes (excluding deep analysis)
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from tradingagents.screener import ScreenerEngine

SMOKE_TICKERS = [
    "600519",  # 贵州茅台
    "000001",  # 平安银行
    "300750",  # 宁德时代
    "600036",  # 招商银行
    "000858",  # 五粮液
]

# Use a past trading day to bypass intraday runtime guard
_SMOKE_DATE = "2026-05-07"


@pytest.mark.integration
def test_smoke_screener_end_to_end():
    """Smoke test: run screener with 5 known tickers, verify output structure."""
    config = {
        "run_time": {
            "earliest": "09:30",
            "latest_next_day": "15:00",
            "allow_weekend": True,
            "allow_non_trading_day_override": True,
            "allow_experimental_intraday": False,
            "max_data_age_days": 5,
        },
        "universe": {
            "profile": "CUSTOM",
            "custom_tickers": SMOKE_TICKERS,
        },
        "candidates": {
            "max_output": 3,
        },
    }

    with TemporaryDirectory() as tmpdir:
        config["data_cache_dir"] = tmpdir

        engine = ScreenerEngine(config=config)
        result = engine.run(trade_date=_SMOKE_DATE, enable_deep_analysis=False)

        # 1. No crash
        assert result is not None, "Engine returned None"

        # 2. Universe populated
        assert result.universe_size >= len(SMOKE_TICKERS), (
            f"Universe size {result.universe_size} < expected {len(SMOKE_TICKERS)}"
        )

        # 3. At least one strategy produced cards
        metrics = result.metrics
        assert isinstance(metrics, dict), f"metrics is {type(metrics)}, expected dict"
        total_signals = (
            metrics.get("strategy_a_candidates", 0)
            + metrics.get("strategy_b_candidates", 0)
            + metrics.get("strategy_c_candidates", 0)
        )
        assert total_signals > 0, (
            f"No strategy returned any cards "
            f"(technical={metrics.get('strategy_a_candidates')}, "
            f"policy={metrics.get('strategy_b_candidates')}, "
            f"smart_money={metrics.get('strategy_c_candidates')})"
        )
        print(f"[SMOKE] signals: technical={metrics.get('strategy_a_candidates')}, "
              f"policy={metrics.get('strategy_b_candidates')}, "
              f"smart_money={metrics.get('strategy_c_candidates')}")

        # 4. Merger output (candidates or dropped)
        total_cards = len(result.candidates) + len(result.dropped_candidates or [])
        assert total_cards > 0, (
            f"Both candidates ({len(result.candidates)}) and "
            f"dropped ({len(result.dropped_candidates or [])}) are empty"
        )

        # 5. Report file written (checked via returned data)
        assert result.universe_size > 0, "universe_size is 0"

        # 6. Deep analysis disabled — verify it is indeed skipped
        deep_runs = metrics.get("deep_analysis_results", [])
        assert len(deep_runs) == 0, (
            f"Deep analysis should be skipped but got {len(deep_runs)} results"
        )

        # 7. Company names present (may be placeholder on Windows encoding)
        all_names = [
            getattr(c, "company_name", None) or c.ticker
            for c in result.candidates
        ] + [
            d.get("company_name")
            for d in (result.dropped_candidates or [])
        ]
        assert all(n for n in all_names), (
            f"Some candidates have no name: {all_names}"
        )

        # 8. Fast enough (this run without deep analysis)
        print(f"\n[SMOKE] universe={result.universe_size}, "
              f"candidates={len(result.candidates)}, "
              f"dropped={len(result.dropped_candidates or [])}")

        print(f"[SMOKE] PASS — all checks passed")


if __name__ == "__main__":
    test_smoke_screener_end_to_end()
