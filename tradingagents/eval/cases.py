"""Decision-correctness evaluation set (R10): "did the system get it right?"

``EvaluationCase`` is one historical "known-outcome" instance: a ticker on an
eval date plus the FORWARD horizon return (computed from real history) mapped
to a true label (BUY/SELL/NEUTRAL). Running the full decision chain on these
cases and comparing to the labels yields accuracy + a confusion matrix — a
correctness baseline the unit tests can't give (they freeze behavior, not truth).

Labels are computed deterministically from real prices; thresholds are explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from tradingagents.screener.data_access import ScreenerDataAccess

__all__ = [
    "BUY_THRESHOLD",
    "SELL_THRESHOLD",
    "EvaluationCase",
    "label_from_return",
    "build_case_set",
]

BUY_THRESHOLD = 0.10   # +10% forward return -> good outcome
SELL_THRESHOLD = -0.10  # -10% forward return -> bad outcome


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    ticker: str
    eval_date: str
    horizon_days: int = 20
    horizon_return: Optional[float] = None
    label: str = "NEUTRAL"


def label_from_return(r: Optional[float]) -> str:
    if r is None:
        return "NEUTRAL"
    if r >= BUY_THRESHOLD:
        return "BUY"
    if r <= SELL_THRESHOLD:
        return "SELL"
    return "NEUTRAL"


def _forward_return(
    data_access: ScreenerDataAccess,
    ticker: str,
    eval_date: str,
    horizon_days: int,
) -> Optional[float]:
    """Close return from eval_date over the next ``horizon_days`` trading days.

    Uses real history AFTER the eval date — deterministic at evaluation time
    (the outcome is genuinely known for historical dates).
    """
    start = pd.Timestamp(eval_date)
    end = start + pd.Timedelta(days=int(horizon_days * 1.75) + 7)  # generous calendar window
    df = data_access.fetch_hist(ticker, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
    if df is None or getattr(df, "empty", True) or "close" not in df.columns:
        return None
    prices = pd.to_datetime(df["date"]) if "date" in df.columns else None
    closes = df["close"].astype(float)
    if prices is not None:
        ordered = df.assign(date=pd.to_datetime(df["date"])).sort_values("date")
    else:
        ordered = df.sort_index()
    closes = ordered["close"].astype(float)
    dates = pd.to_datetime(ordered["date"])
    # eval date's own close is the entry reference
    mask = dates >= pd.Timestamp(eval_date)
    after = closes[mask]
    if len(after) < 2:
        return None
    entry = float(after.iloc[0])
    # pick the close ~horizon trading days later
    target = after.iloc[min(horizon_days, len(after) - 1)]
    if not entry:
        return None
    return float(target / entry - 1.0)


def build_case_set(
    data_access: ScreenerDataAccess,
    tickers: List[str],
    eval_date: str,
    horizon_days: int = 20,
    n: int = 20,
    seed: int = 42,
) -> List[EvaluationCase]:
    """Build up to ``n`` labeled cases with real forward returns (deterministic slice)."""
    import numpy as np

    if not tickers:
        return []
    unique = sorted(set(tickers))
    rng = np.random.RandomState(seed)
    picked = rng.choice(unique, size=min(n, len(unique)), replace=False).tolist()
    cases: List[EvaluationCase] = []
    for i, ticker in enumerate(picked):
        ret = _forward_return(data_access, ticker, eval_date, horizon_days)
        cases.append(
            EvaluationCase(
                id=f"{eval_date}_{ticker}",
                ticker=ticker,
                eval_date=eval_date,
                horizon_days=horizon_days,
                horizon_return=ret,
                label=label_from_return(ret),
            )
        )
    return cases
