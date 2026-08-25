from __future__ import annotations

import pandas as pd
import importlib.util
import sys
from types import ModuleType


if importlib.util.find_spec("yfinance") is None:
    yfinance = ModuleType("yfinance")
    exceptions = ModuleType("yfinance.exceptions")
    exceptions.YFRateLimitError = type("YFRateLimitError", (Exception,), {})
    sys.modules["yfinance"] = yfinance
    sys.modules["yfinance.exceptions"] = exceptions
if importlib.util.find_spec("stockstats") is None:
    stockstats = ModuleType("stockstats")
    stockstats.wrap = lambda frame: frame
    sys.modules["stockstats"] = stockstats

from tradingagents.dataflows.stockstats_utils import _clean_dataframe


def test_clean_dataframe_makes_volume_numeric_without_inventing_future_volume():
    frame = pd.DataFrame(
        {
            "Date": ["2026-08-19", "2026-08-20", "2026-08-21"],
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 11.5, 12.5],
            "Volume": [1000, None, "3000"],
        }
    )

    cleaned = _clean_dataframe(frame)

    assert cleaned["Volume"].tolist() == [1000.0, 0.0, 3000.0]
    assert cleaned["Volume"].dtype.kind == "f"
