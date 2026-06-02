"""Screener package for Stage 1 candidate discovery."""

import warnings

# Suppress noisy third-party library warnings that don't affect functionality
warnings.filterwarnings("default", category=UserWarning, module="py_mini_racer")
warnings.filterwarnings("default", category=UserWarning, module="akshare")
# Suppress the specific "downloading data" warnings from akshare
warnings.filterwarnings("ignore", message="正在下载数据，请稍等", category=UserWarning)
# Suppress pkg_resources deprecation warning (third-party issue, not ours)
warnings.filterwarnings("ignore", message="pkg_resources is deprecated", category=UserWarning)

from .config import SCREENER_CONFIG, SCREENER_UNIVERSE
from .models import (
    DataFreshness,
    DeepAnalysisResult,
    ScreeningResult,
    ScreenerMetrics,
    SignalCard,
    SignalEvidence,
)

__all__ = [
    "SCREENER_CONFIG",
    "SCREENER_UNIVERSE",
    "ScreenerEngine",
    "DataFreshness",
    "DeepAnalysisResult",
    "ScreeningResult",
    "ScreenerMetrics",
    "SignalCard",
    "SignalEvidence",
]


def __getattr__(name: str):
    if name == "ScreenerEngine":
        from .engine import ScreenerEngine

        return ScreenerEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
