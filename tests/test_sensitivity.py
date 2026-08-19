"""R9 sensitivity tests — offline: mock engine.run outcomes."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from tradingagents.backtest.engine import BacktestResult
from tradingagents.backtest.sensitivity import (
    DEFAULT_SPECS,
    SensitivityRunner,
    build_strategy_config,
)


def test_build_strategy_config_sets_threshold_key():
    cfg = build_strategy_config("momentum_weight", 0.15)
    assert cfg["strategies"]["technical"]["thresholds"]["momentum_weight"] == 0.15


def test_default_specs_cover_baselines():
    names = [s.param for s in DEFAULT_SPECS]
    assert "trend_alignment_weight" in names
    assert "momentum_weight" in names
    assert "hist_rows_minimum" in names
    for spec in DEFAULT_SPECS:
        assert spec.baseline in spec.values  # grid always contains baseline


def test_run_all_collects_rows_and_report(monkeypatch):
    from tradingagents.backtest import sensitivity

    def make_result(strategy_config):
        param = strategy_config["strategies"]["technical"]["thresholds"]
        (_, v), = param.items()
        return BacktestResult(
            config=None,
            pool=[],
            close=pd.DataFrame(),
            holdings={},
            nav=pd.Series([1.0, 1.1]),
            benchmark=None,
            performance={
                "total_return": 0.05 + 0.01 * v,
                "sharpe": 0.8,
                "max_drawdown": 0.12,
                "excess_return": 0.02,
                "periods": 100,
            },
            run_id="t",
        )

    class FakeEngine:
        def __init__(self, da, config):
            self.da = da
            self.config = config

        def run(self, pool=None, strategy_config=None):
            return make_result(strategy_config)

    monkeypatch.setattr(sensitivity, "BacktestEngine", FakeEngine)
    monkeypatch.setattr(sensitivity, "build_pool", lambda *a, **k: ["sh600519"])

    runner = object.__new__(SensitivityRunner)
    runner.da = None
    runner.bt_config = SimpleNamespace(
        start_date="2025-08-01", end_date="2026-06-30",
        pool_size=12, top_k=4, rebalance_days=20, index_symbol="000300", seed=42,
    )
    runner.specs = DEFAULT_SPECS

    rows = runner.run_all()
    assert len(rows) == sum(len(s.values) for s in DEFAULT_SPECS)

    md = runner.report(rows)
    assert "# Parameter Sensitivity Report" in md
    assert "trend_alignment_weight" in md
    assert "Sharpe" in md
    assert "robust" in md  # interpretation text


def test_report_includes_baseline_delta():
    rows = [
        {"param": "momentum_weight", "value": 0.18, "baseline": 0.18, "delta_pct": 0.0,
         "total_return": 0.10, "sharpe": 1.0, "max_drawdown": 0.1, "excess_return": 0.0},
        {"param": "momentum_weight", "value": 0.23, "baseline": 0.18, "delta_pct": 28.0,
         "total_return": 0.12, "sharpe": 1.1, "max_drawdown": 0.11, "excess_return": 0.02},
    ]
    runner = object.__new__(SensitivityRunner)
    runner.bt_config = SimpleNamespace(pool_size=12, start_date="2025-08-01", end_date="2026-06-30")
    md = runner.report(rows)
    assert "0.18 (+0%)" in md
    assert "0.23 (+28%)" in md
