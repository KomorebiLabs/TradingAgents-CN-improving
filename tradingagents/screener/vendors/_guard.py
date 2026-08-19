"""Vendor-call guard (task R3: data reliability).

Wraps every vendor fetch function so that swallowed failures become VISIBLE:
- logs warning with vendor name, exception type, duration;
- logs debug when a call returns empty/None (degradation signal);
- preserves the historical contract: failure -> None (callers keep fallback
  chains unchanged).

Applied by decorating vendor functions and removing their inner
``except Exception: return None`` blocks (behaviour-identical, observable).
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


def vendor_call(name: str) -> Callable:
    """Decorate a vendor fetch function: log failures/empties, keep None contract."""

    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.time()
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                logger.warning(
                    "[vendor:%s] raised %s: %s (%.1fs)",
                    name,
                    type(exc).__name__,
                    exc,
                    time.time() - t0,
                )
                return None
            elapsed = time.time() - t0
            if result is None or (hasattr(result, "empty") and result.empty):
                logger.debug("[vendor:%s] returned empty/None (%.1fs)", name, elapsed)
            else:
                logger.debug("[vendor:%s] ok (%.1fs)", name, elapsed)
            return result

        return wrapper

    return deco
