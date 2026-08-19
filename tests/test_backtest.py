"""Backtest module tests (R1). All offline: synthetic data, mocked vendors."""

from __future__ import annotations

import pandas as pd
import pytest

from tradingagents.backtest.engine import BacktestConfig, BacktestResult, build_pool
from tradingagents.backtest.performance import compute_performance, equity_curve_from_holdings
from tradingagents.backtest.report import build_markdown


def _dates(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2026-01-05", periods=n, freq="B")


# ---------------------------------------------------------------------------
# performance math
# ---------------------------------------------------------------------------


def test_performance_total_return():
    nav = pd.Series([1.0, 1.1, 1.1, 1.21], index=_dates(4))
    p = compute_performance(nav)
    assert p["total_return"] == pytest.approx(0.21)
    assert p["periods"] == 4
    assert p["excess_return"] == 0.0


def test_performance_max_drawdown():
    nav = pd.Series([1.0, 2.0, 1.0, 2.0], index=_dates(4))
    p = compute_performance(nav)
    assert p["max_drawdown"] == pytest.approx(0.50)
    # win_rate: returns [1.0, -0.5, 1.0] -> 2/3 (rounded to 4dp)
    assert p["win_rate"] == pytest.approx(2 / 3, abs=1e-3)


def test_performance_flat_curve_sharpe_zero():
    nav = pd.Series([1.0, 1.0, 1.0, 1.0], index=_dates(4))
    p = compute_performance(nav)
    assert p["sharpe"] == 0.0
    assert p["annualized_vol"] == 0.0


def test_performance_excess_vs_benchmark():
    nav = pd.Series([1.0, 1.2], index=_dates(2))
    bench = pd.Series([1.0, 1.1], index=_dates(2))
    p = compute_performance(nav, benchmark=bench)
    assert p["excess_return"] == pytest.approx(0.1 - 0.0)  # 20% - 10%


def test_performance_short_series_returns_zeros():
    p = compute_performance(pd.Series([1.0], index=_dates(1)))
    assert p["total_return"] == 0.0


# ---------------------------------------------------------------------------
# equity curve math (equal weight, signal switches, missing prices)
# ---------------------------------------------------------------------------


def test_equity_curve_equal_weight_two_stocks():
    dates = _dates(3)
    close = pd.DataFrame(
        {
            "sh600001": [100.0, 110.0, 121.0],
            "sh600002": [100.0, 110.0, 110.0],
        },
        index=dates,
    )
    # signal on day 0: hold both equal weight; day1: 10% each; day2: A +10%, B flat
    nav = equity_curve_from_holdings(close, {"2026-01-05": ["sh600001", "sh600002"]})
    assert nav.iloc[0] == pytest.approx(1.0)
    assert nav.iloc[1] == pytest.approx(1.10)  # (1.10+1.10)/2 / 1
    # day2: A 121/110 = +10%, B 110/110=0  -> weighted +5% -> 1.10*1.05
    assert nav.iloc[2] == pytest.approx(1.10 * 1.05)


def test_equity_curve_signal_switch_reweights():
    dates = _dates(4)
    close = pd.DataFrame(
        {
            "a": [100.0, 110.0, 120.0, 120.0],  # keeps rising
            "b": [100.0, 90.0, 80.0, 80.0],     # keeps falling
        },
        index=dates,
    )
    holdings = {
        "2026-01-05": ["a", "b"],   # day1: a +10%, b -10% -> flat
        "2026-01-08": ["a"],        # day4: switch to a only, reweight 100%
    }
    nav = equity_curve_from_holdings(close, holdings)
    assert nav.iloc[1] == pytest.approx(1.0)                      # (1.1 + 0.9)/2
    # day3 (before switch): a +9.09%, b -11.11%, equal weight
    expected_day3 = 1.0 * (0.5 * (120 / 110) + 0.5 * (80 / 90))
    assert nav.iloc[2] == pytest.approx(expected_day3)
    # day4 (switch to a only, a flat): value unchanged
    assert nav.iloc[3] == pytest.approx(expected_day3)


def test_equity_curve_missing_price_skipped():
    dates = _dates(3)
    close = pd.DataFrame(
        {"a": [100.0, 100.0, 110.0], "b": [100.0, float("nan"), 110.0]},
        index=dates,
    )
    holdings = {"2026-01-05": ["a", "b"]}
    nav = equity_curve_from_holdings(close, holdings)
    # day1: a flat contributes 0 (b missing, renorm) -> nav 1.0
    assert nav.iloc[1] == pytest.approx(1.0)
    # day2: both +10% -> 1.10
    assert nav.iloc[2] == pytest.approx(1.10)


# ---------------------------------------------------------------------------
# pool building (deterministic, mocked)
# ---------------------------------------------------------------------------


def test_build_pool_deterministic_and_prefixed(monkeypatch):
    import pandas as pd

    fake_df = pd.DataFrame({"成分券代码": ["600519", "000001", "300750", "601318", "000858"]})
    monkeypatch.setattr(
        "tradingagents.screener.vendors.sina.fetch_index_cons_weight",
        lambda http, code: fake_df,
    )
    from tradingagents.screener.data_access import ScreenerDataAccess

    da = ScreenerDataAccess({})
    pool1 = build_pool(da, pool_size=3)
    pool2 = build_pool(da, pool_size=3)
    assert pool1 == pool2  # deterministic (same seed)
    assert all(t.startswith(("sh", "sz")) for t in pool1)
    assert len(pool1) == 3


def test_build_pool_empty_raises(monkeypatch):
    import pandas as pd

    monkeypatch.setattr(
        "tradingagents.screener.vendors.sina.fetch_index_cons_weight",
        lambda http, code: pd.DataFrame(),
    )
    from tradingagents.screener.data_access import ScreenerDataAccess

    with pytest.raises(RuntimeError):
        build_pool(ScreenerDataAccess({}), pool_size=5)


# ---------------------------------------------------------------------------
# report generation
# ---------------------------------------------------------------------------


def test_report_markdown_includes_metrics():
    nav = pd.Series([1.0, 1.1, 1.2], index=_dates(3))
    result = BacktestResult(
        config=BacktestConfig(start_date="2026-01-05", end_date="2026-01-09"),
        pool=["sh600519"],
        close=pd.DataFrame(index=_dates(3)),
        holdings={"2026-01-05": ["sh600519"]},
        nav=nav,
        benchmark=None,
        performance=compute_performance(nav),
        signal_log=[{"date": "2026-01-05", "top": ["sh600519"]}],
        run_id="test_run",
    )
    md = build_markdown(result)
    assert "# Backtest Report" in md
    assert "Total Return" in md
    assert "Strategy |" in md
    assert "2026-01-05" in md
    assert "technical factor" in md  # honest limitation documented
