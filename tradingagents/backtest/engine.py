"""Signal-driven backtest engine (R1).

Pipeline:
  1. build a stock pool (CSI300 constituents, capped at ``pool_size``);
  2. fetch history once per ticker (project's own ScreenerDataAccess);
  3. on each rebalance date run the SCREENER's real TechnicalStrategy over the
     pool and pick top_k by screening_score  ->  holdings calendar;
  4. compute the equal-weight equity curve and standard performance vs CSI300.

Reusing TechnicalStrategy means the backtest validates the project's ACTUAL
stock-selection logic (technical factor), not an ad-hoc proxy. Policy /
Smart-Money factors are NOT backtestable: they need point-in-time concept /
fund-flow snapshots that free vendors do not provide historically
(document limitation in the report).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from tradingagents.backtest.data import fetch_benchmark, fetch_close_prices
from tradingagents.backtest.performance import compute_performance, equity_curve_from_holdings
from tradingagents.screener.data_access import ScreenerDataAccess
from tradingagents.screener.strategies.technical import TechnicalStrategy

__all__ = ["BacktestConfig", "BacktestEngine", "BacktestResult", "build_pool"]


@dataclass
class BacktestConfig:
    start_date: str = "2025-07-01"
    end_date: str = "2026-06-30"
    pool_size: int = 80          # cap on CSI300 constituents screened
    top_k: int = 5               # stocks held each rebalance
    rebalance_days: int = 20     # ~monthly
    index_symbol: str = "000300"  # CSI300 constituents as the pool universe
    seed: Optional[int] = 42     # deterministic pool slice


@dataclass
class BacktestResult:
    config: BacktestConfig
    pool: List[str]
    close: pd.DataFrame
    holdings: Dict[str, List[str]]
    nav: pd.Series
    benchmark: Optional[pd.Series]
    performance: Dict[str, Any]
    signal_log: List[Dict[str, Any]] = field(default_factory=list)
    run_id: str = ""


def build_pool(
    data_access: ScreenerDataAccess,
    index_symbol: str = "000300",
    pool_size: int = 80,
    seed: Optional[int] = 42,
) -> List[str]:
    """Deterministic CSI300 constituent slice (codes -> sh/sz-prefixed)."""
    from tradingagents.screener import vendors

    http = data_access._http()
    df = vendors.sina.fetch_index_cons_weight(http, index_symbol)
    codes: List[str] = []
    if df is not None and not getattr(df, "empty", True):
        for col in ("成分券代码", "code", "证券代码", "品种代码"):
            if col in df.columns:
                codes = [str(c).zfill(6) for c in df[col].dropna() if str(c).strip().isdigit()]
                break
    if not codes:
        raise RuntimeError(f"Index constituents unavailable for {index_symbol} (pool empty)")
    import numpy as np

    from tradingagents.screener.universe import guess_exchange_suffix

    rng = np.random.RandomState(seed)
    picked = rng.choice(sorted(codes), size=min(pool_size, len(codes)), replace=False).tolist()
    # use sh600519 / sz000001 prefix form — the format fetch_hist / TechnicalStrategy expect
    return [f"{guess_exchange_suffix(c).lower()}{c}" for c in picked]


class BacktestEngine:
    """Orchestrates one backtest run."""

    def __init__(self, data_access: ScreenerDataAccess, config: Optional[BacktestConfig] = None):
        self.da = data_access
        self.config = config or BacktestConfig()

    @staticmethod
    def signal_dates(close: pd.DataFrame, rebalance_days: int) -> List[pd.Timestamp]:
        """Rebalance dates: every ``rebalance_days`` trading days from window start."""
        idx = list(close.index)
        return idx[:: max(1, rebalance_days)]

    @staticmethod
    def select_topk(
        da: ScreenerDataAccess,
        pool: List[str],
        signal_date: pd.Timestamp,
        top_k: int,
        strategy_config: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Run the real TechnicalStrategy over the pool at a date; return top_k tickers.

        ``strategy_config`` (optional) feeds TechnicalStrategy — enables
        parameterized backtests (R9 sensitivity analysis).
        """
        date_str = signal_date.strftime("%Y-%m-%d")
        outcome = TechnicalStrategy(da, strategy_config or {}).run(pool, date_str)
        cards = outcome.cards if hasattr(outcome, "cards") else []
        scored = sorted(
            (c for c in cards if c.screening_score is not None),
            key=lambda c: c.screening_score,
            reverse=True,
        )
        return [c.ticker for c in scored[:top_k]]

    def run(self, pool: Optional[List[str]] = None, strategy_config: Optional[Dict[str, Any]] = None) -> BacktestResult:
        cfg = self.config
        pool = pool or build_pool(self.da, cfg.index_symbol, cfg.pool_size, cfg.seed)

        close = fetch_close_prices(self.da, pool, cfg.start_date, cfg.end_date)
        if close.empty:
            raise RuntimeError("No price data fetched for pool — check data access / date window")

        dates = self.signal_dates(close, cfg.rebalance_days)
        holdings: Dict[str, List[str]] = {}
        signal_log: List[Dict[str, Any]] = []
        for d in dates:
            picked = self.select_topk(self.da, pool, d, cfg.top_k, strategy_config)
            holdings[d.strftime("%Y-%m-%d")] = picked
            signal_log.append({"date": d.strftime("%Y-%m-%d"), "top": picked})

        nav = equity_curve_from_holdings(close, holdings)
        benchmark = None
        try:
            benchmark = fetch_benchmark(cfg.start_date, cfg.end_date)
        except Exception:
            benchmark = None  # benchmark optional; performance without excess still valid

        perf = compute_performance(nav, benchmark)
        return BacktestResult(
            config=cfg,
            pool=pool,
            close=close,
            holdings=holdings,
            nav=nav,
            benchmark=benchmark,
            performance=perf,
            signal_log=signal_log,
            run_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
        )
