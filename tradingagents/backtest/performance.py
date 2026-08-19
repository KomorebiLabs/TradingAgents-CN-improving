"""Performance analytics for the backtest engine (R1).

Pure functions over normalized equity curves — easy to test offline.
All returns are per-period; yearly aggregation assumes ``periods_per_year``
(default 252 trading days).

Metrics: total_return, annualized_return, annualized_vol, sharpe (risk-free 0),
max_drawdown, win_rate, benchmark-relative excess return.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def compute_performance(
    nav: pd.Series,
    benchmark: Optional[pd.Series] = None,
    risk_free: float = 0.0,
    periods_per_year: int = 252,
) -> Dict[str, Any]:
    """Compute standard performance metrics from a long-only nav (starts at 1)."""
    nav = nav.dropna()
    if len(nav) < 2:
        empty: Dict[str, Any] = {
            "total_return": 0.0,
            "annualized_return": 0.0,
            "annualized_vol": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "excess_return": 0.0,
            "periods": 0,
        }
        return empty

    returns = nav.pct_change().dropna()
    start = float(nav.iloc[0])
    end = float(nav.iloc[-1])
    n = len(nav)

    total_return = end / start - 1.0
    annualized_return = (end / start) ** (periods_per_year / n) - 1.0 if start > 0 else 0.0
    annualized_vol = float(returns.std(ddof=1) * math.sqrt(periods_per_year))
    rf_per_period = risk_free / periods_per_year
    vol = returns.std(ddof=1)
    sharpe = float((returns.mean() - rf_per_period) / vol * math.sqrt(periods_per_year)) if vol > 0 else 0.0
    drawdown = nav / nav.cummax() - 1.0
    max_drawdown = float(abs(drawdown.min()))
    win_rate = float((returns > 0).mean())

    out: Dict[str, Any] = {
        "total_return": round(total_return, 4),
        "annualized_return": round(annualized_return, 4),
        "annualized_vol": round(annualized_vol, 4),
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(max_drawdown, 4),
        "win_rate": round(win_rate, 4),
        "excess_return": 0.0,
        "periods": n,
    }

    if benchmark is not None:
        bench = benchmark.reindex(nav.index).ffill().dropna()
        if len(bench) >= 2:
            out["excess_return"] = round(float(end / start - bench.iloc[-1] / bench.iloc[0]), 4)

    return out


def equity_curve_from_holdings(
    close: pd.DataFrame,
    holdings: Dict[str, List[str]],
    weights: Optional[Dict[str, Dict[str, float]]] = None,
) -> pd.Series:
    """Daily equity curve of a signal-driven equal-weight book.

    ``close``: date-indexed prices (tickers as columns).
    ``holdings``: {signal_date "YYYY-MM-DD": [tickers]} — between signal dates
      the previous selection is held; on a signal date weights reset to equal
      1/n (or the supplied per-signal weights).
    Tickers without a price on a day are excluded that day and remaining
    weights renormalized. Long-only; trading costs NOT modelled (documented).
    """
    dates = close.index
    r = close.pct_change(fill_method=None)

    weights = weights or {}
    active_weights: Dict[str, float] = {}
    nav: List[float] = []
    prev_nav = 1.0

    for date in dates:
        key = str(date.date()) if hasattr(date, "date") else str(date)[:10]
        if key in holdings:
            held = [t for t in holdings[key] if t in close.columns and pd.notna(close.loc[date, t])]
            if held:
                w_map = weights.get(key)
                active_weights = {t: (w_map.get(t, 1.0 / len(held)) if w_map else 1.0 / len(held)) for t in held}
            else:
                active_weights = {}

        if active_weights:
            # drop tickers with no valid return today, renormalize remaining weights
            valid = {t: w for t, w in active_weights.items() if pd.notna(r.loc[date, t])}
            if valid:
                s = sum(valid.values())
                valid = {t: w / s for t, w in valid.items()}
                day_ret = sum(valid[t] * r.loc[date, t] for t in valid)
                if np.isfinite(day_ret):
                    prev_nav *= 1.0 + day_ret
        nav.append(prev_nav)

    out = pd.Series(nav, index=dates, dtype=float)
    out.name = "strategy"
    out.iloc[0] = 1.0  # first day day_ret is NaN -> stays 1.0
    return out
