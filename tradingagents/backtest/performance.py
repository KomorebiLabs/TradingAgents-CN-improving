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
    execution_lag_days: int = 1,
    execution_costs: Optional[Dict[str, float]] = None,
    execution_volume: Optional[pd.DataFrame] = None,
    execution_log: Optional[List[Dict[str, Any]]] = None,
) -> pd.Series:
    """Daily equity curve of a signal-driven equal-weight book.

    ``close``: date-indexed prices (tickers as columns).
    ``holdings``: {signal_date "YYYY-MM-DD": [tickers]}. Signals are produced
      after the signal-date close and become positions after the close of the
      next trading session by default, so returns begin one interval later.
    Tickers without a price on a day are excluded from that day's return.
    Optional execution costs are deducted when the target book is filled.
    Limit-up buys and limit-down sells are left unfilled and recorded.
    """
    dates = close.index
    r = close.pct_change(fill_method=None)

    weights = weights or {}
    active_weights: Dict[str, float] = {}
    scheduled_weights: Dict[int, tuple[str, Dict[str, float], int]] = {}
    nav: List[float] = []
    prev_nav = 1.0
    costs = execution_costs or {}
    commission = float(costs.get("commission_rate", 0.0))
    stamp_duty = float(costs.get("stamp_duty_sell", 0.0))
    slippage = float(costs.get("slippage", 0.0))

    lag = max(0, int(execution_lag_days))
    for index, date in enumerate(dates):
        key = str(date.date()) if hasattr(date, "date") else str(date)[:10]
        if key in holdings:
            held = [t for t in holdings[key] if t in close.columns and pd.notna(close.loc[date, t])]
            if held:
                w_map = weights.get(key)
                target_weights = {t: (w_map.get(t, 1.0 / len(held)) if w_map else 1.0 / len(held)) for t in held}
            else:
                target_weights = {}
            first_execution_index = index + lag
            scheduled_weights[first_execution_index] = (key, target_weights, first_execution_index)

        if active_weights:
            # Missing returns contribute zero; uninvested weight remains cash.
            valid = {t: w for t, w in active_weights.items() if pd.notna(r.loc[date, t])}
            if valid:
                invested = sum(valid.values())
                if invested > 0:
                    valid = {ticker: weight / invested for ticker, weight in valid.items()}
                day_ret = sum(valid[t] * r.loc[date, t] for t in valid)
                if np.isfinite(day_ret):
                    prev_nav *= 1.0 + day_ret

        # Execute at this session's close, after its close-to-close return has
        # already occurred. The new book earns returns from the next interval.
        if index in scheduled_weights:
            from tradingagents.agents.utils.exchange_rules import price_limit_pct

            signal_date, target_weights, first_execution_index = scheduled_weights[index]
            next_weights = dict(active_weights)
            blocked_buys: List[str] = []
            blocked_sells: List[str] = []
            blocked_suspensions: List[str] = []
            executed_buys: List[str] = []
            executed_sells: List[str] = []
            buy_turnover = 0.0
            sell_turnover = 0.0
            universe = set(active_weights) | set(target_weights)

            for ticker in sorted(universe):
                current = float(active_weights.get(ticker, 0.0))
                target = float(target_weights.get(ticker, 0.0))
                delta = target - current
                suspended = (
                    execution_volume is not None
                    and ticker in execution_volume.columns
                    and date in execution_volume.index
                    and (
                        pd.isna(execution_volume.loc[date, ticker])
                        or float(execution_volume.loc[date, ticker]) <= 0
                    )
                )
                if delta != 0 and suspended:
                    blocked_suspensions.append(ticker)
                    continue
                pct = r.loc[date, ticker] if ticker in r.columns else np.nan
                suffix = ticker.rsplit(".", 1)[-1].upper() if "." in ticker else ""
                limit = price_limit_pct(ticker) if suffix in {"SH", "SZ", "BJ"} else None
                at_limit_up = limit is not None and pd.notna(pct) and float(pct) * 100 >= limit - 0.2
                at_limit_down = limit is not None and pd.notna(pct) and float(pct) * 100 <= -limit + 0.2
                if delta > 0 and at_limit_up:
                    blocked_buys.append(ticker)
                    continue
                if delta < 0 and at_limit_down:
                    blocked_sells.append(ticker)
                    continue
                next_weights[ticker] = target
                if delta > 0:
                    buy_turnover += delta
                    executed_buys.append(ticker)
                elif delta < 0:
                    sell_turnover += -delta
                    executed_sells.append(ticker)

            active_weights = {ticker: weight for ticker, weight in next_weights.items() if weight > 0}
            transaction_cost = (
                buy_turnover * (commission + slippage)
                + sell_turnover * (commission + stamp_duty + slippage)
            )
            prev_nav *= max(0.0, 1.0 - transaction_cost)
            has_unfilled = bool(blocked_buys or blocked_sells or blocked_suspensions)
            if has_unfilled and index + 1 < len(dates) and index + 1 not in scheduled_weights:
                scheduled_weights[index + 1] = (signal_date, target_weights, first_execution_index)
            if execution_log is not None:
                execution_log.append(
                    {
                        "signal_date": signal_date,
                        "execution_date": key,
                        "executed_buys": executed_buys,
                        "executed_sells": executed_sells,
                        "blocked_buys": blocked_buys,
                        "blocked_sells": blocked_sells,
                        "blocked_suspensions": blocked_suspensions,
                        "buy_turnover": buy_turnover,
                        "sell_turnover": sell_turnover,
                        "turnover": buy_turnover + sell_turnover,
                        "transaction_cost": transaction_cost,
                        "status": "UNFILLED_RETRY" if has_unfilled else "FILLED",
                        "delay_days": index - first_execution_index,
                    }
                )
        nav.append(prev_nav)

    out = pd.Series(nav, index=dates, dtype=float)
    out.name = "strategy"
    out.iloc[0] = 1.0  # first day day_ret is NaN -> stays 1.0
    return out
