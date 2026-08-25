"""Vendor-call guard + health tracker (R1/R3: reliability & observability).

``vendor_call`` wraps every vendor fetch function so that swallowed failures
become VISIBLE and are COUNTED:
- logs warning with vendor name, exception type, duration;
- records every call into the shared ``VendorHealthTracker`` (calls, failures,
  elapsed, last error) for run-end health summaries;
- preserves the historical contract: failure -> None (callers keep fallback
  chains unchanged).

``VendorHealthTracker`` is the "supplier health monitoring" seam: any layer can
read a snapshot of failure rates / degraded calls per vendor, and the screener
attaches it to its capability summary.
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Callable

from tradingagents.dataflows.vendor_health import (
    TRACKER,
    VendorHealth,
    VendorHealthTracker,
    classify_exception,
)

logger = logging.getLogger(__name__)


def vendor_call(name: str) -> Callable:
    """Decorate a vendor fetch function: log + record failures/empties, keep None contract."""

    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.time()
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                dt = time.time() - t0
                logger.warning(
                    "[vendor:%s] raised %s: %s (%.1fs)",
                    name,
                    type(exc).__name__,
                    exc,
                    dt,
                )
                TRACKER.record(
                    name,
                    status=classify_exception(exc),
                    elapsed=dt,
                    error=f"{type(exc).__name__}: {exc}",
                )
                return None
            dt = time.time() - t0
            empty = result is None or (hasattr(result, "empty") and result.empty)
            if empty:
                logger.debug("[vendor:%s] returned empty/None (%.1fs)", name, dt)
                TRACKER.record(name, status="empty", elapsed=dt, error="empty/None result")
            else:
                logger.debug("[vendor:%s] ok (%.1fs)", name, dt)
                TRACKER.record(name, status="ok", elapsed=dt)
            return result

        return wrapper

    return deco
