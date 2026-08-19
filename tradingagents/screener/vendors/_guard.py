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
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)


@dataclass
class VendorHealth:
    """Per-vendor accumulator (one instance per vendor name)."""

    name: str
    calls: int = 0
    failures: int = 0
    total_seconds: float = 0.0
    last_error: str = ""

    @property
    def failure_rate(self) -> float:
        return self.failures / self.calls if self.calls else 0.0

    @property
    def avg_seconds(self) -> float:
        return self.total_seconds / self.calls if self.calls else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "calls": self.calls,
            "failures": self.failures,
            "failure_rate": round(self.failure_rate, 3),
            "avg_seconds": round(self.avg_seconds, 3),
            "total_seconds": round(self.total_seconds, 2),
            "last_error": self.last_error[:200],
        }


class VendorHealthTracker:
    """Thread-safe accumulator of per-vendor fetch outcomes (R3 health monitor)."""

    def __init__(self) -> None:
        self._stats: Dict[str, VendorHealth] = {}
        self._lock = threading.Lock()

    def record(self, name: str, ok: bool, elapsed: float, error: str = "") -> None:
        with self._lock:
            health = self._stats.setdefault(name, VendorHealth(name=name))
            health.calls += 1
            health.total_seconds += elapsed
            if not ok:
                health.failures += 1
                health.last_error = (error or "")[:300]

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {name: h.to_dict() for name, h in sorted(self._stats.items())}

    def summary_lines(self) -> list[str]:
        lines = []
        for name, h in sorted(self._stats.items()):
            lines.append(
                f"  {name}: calls={h.calls} fail={h.failures} "
                f"rate={h.failure_rate * 100:.1f}% avg={h.avg_seconds:.2f}s"
                + (f" last_error={h.last_error[:80]}" if h.last_error else "")
            )
        return lines

    def reset(self) -> None:
        with self._lock:
            self._stats.clear()


# Shared process-wide tracker; every @vendor_call registers here.
TRACKER = VendorHealthTracker()


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
                TRACKER.record(name, ok=False, elapsed=dt, error=f"{type(exc).__name__}: {exc}")
                return None
            dt = time.time() - t0
            empty = result is None or (hasattr(result, "empty") and result.empty)
            if empty:
                logger.debug("[vendor:%s] returned empty/None (%.1fs)", name, dt)
                TRACKER.record(name, ok=False, elapsed=dt, error="empty/None result")
            else:
                logger.debug("[vendor:%s] ok (%.1fs)", name, dt)
                TRACKER.record(name, ok=True, elapsed=dt)
            return result

        return wrapper

    return deco
