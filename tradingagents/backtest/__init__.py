"""Backtest module (R1): signal-driven equity backtest reusing the screener's
real TechnicalStrategy for stock selection.

    data.py        pool close prices + CSI300 benchmark
    engine.py      pool -> periodic signals -> holdings calendar -> nav
    performance.py equity curve + standard metrics (pure, tested)
    report.py      markdown report + equity-curve plot + csv
    __main__.py    CLI: python -m tradingagents.backtest
"""

from tradingagents.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult, build_pool

__all__ = ["BacktestConfig", "BacktestEngine", "BacktestResult", "build_pool"]
