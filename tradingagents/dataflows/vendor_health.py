"""Shared vendor health tracking for dataflows and screener adapters."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


HEALTH_STATUSES = (
    "ok",
    "empty",
    "not_configured",
    "rate_limited",
    "blocked",
    "auth_error",
    "schema_error",
    "timeout",
    "exception",
)
_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|token|authorization|secret)(\s*[:=]\s*)([^\s,;]+)"
)


def redact_error(value: str) -> str:
    """Remove token-like values before an error enters logs/artifacts."""
    return _SECRET_RE.sub(r"\1\2[REDACTED]", str(value or ""))[:300]


@dataclass
class VendorHealth:
    name: str
    calls: int = 0
    failures: int = 0
    total_seconds: float = 0.0
    last_error: str = ""
    last_status: str = ""
    status_counts: Dict[str, int] = field(default_factory=dict)

    @property
    def failure_rate(self) -> float:
        return self.failures / self.calls if self.calls else 0.0

    @property
    def avg_seconds(self) -> float:
        return self.total_seconds / self.calls if self.calls else 0.0

    def record(self, status: str, elapsed: float, error: str = "") -> None:
        status = status if status in HEALTH_STATUSES else "exception"
        self.calls += 1
        self.total_seconds += max(float(elapsed), 0.0)
        self.last_status = status
        self.status_counts[status] = self.status_counts.get(status, 0) + 1
        if status != "ok":
            self.failures += 1
            self.last_error = redact_error(error or status)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "calls": self.calls,
            "failures": self.failures,
            "failure_rate": round(self.failure_rate, 3),
            "avg_seconds": round(self.avg_seconds, 3),
            "total_seconds": round(self.total_seconds, 2),
            "last_status": self.last_status,
            "status_counts": dict(sorted(self.status_counts.items())),
            "last_error": self.last_error,
        }


class VendorHealthTracker:
    """Thread-safe per-run/process vendor outcome accumulator.

    ``record(ok=...)`` remains supported for the existing screener tests;
    new dataflow callers should provide an explicit ``status``.
    """

    def __init__(self) -> None:
        self._stats: Dict[str, VendorHealth] = {}
        self._lock = threading.Lock()

    def record(
        self,
        name: str,
        ok: Optional[bool] = None,
        elapsed: float = 0.0,
        error: str = "",
        status: Optional[str] = None,
    ) -> None:
        resolved = status or ("ok" if ok else "exception")
        with self._lock:
            health = self._stats.setdefault(name, VendorHealth(name=name))
            health.record(resolved, elapsed, error)

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {name: item.to_dict() for name, item in sorted(self._stats.items())}

    def summary_lines(self) -> list[str]:
        snapshot = self.snapshot()
        return [
            f"  {name}: calls={item['calls']} fail={item['failures']} "
            f"rate={item['failure_rate'] * 100:.1f}% status={item['last_status']}"
            + (f" last_error={item['last_error'][:80]}" if item["last_error"] else "")
            for name, item in snapshot.items()
        ]

    def reset(self) -> None:
        with self._lock:
            self._stats.clear()


TRACKER = VendorHealthTracker()


def classify_exception(exc: BaseException) -> str:
    """Map common transport/provider failures to a stable health status."""
    text = str(exc).lower()
    name = type(exc).__name__.lower()
    if "timeout" in text or "timeout" in name:
        return "timeout"
    if "rate" in text or "429" in text or "ratelimit" in name:
        return "rate_limited"
    if "401" in text or "403" in text or "permission" in text or "unauthorized" in text:
        return "auth_error"
    if "schema" in text or "unexpected keyword" in text or "missing required" in text:
        return "schema_error"
    return "exception"


def classify_provider_text(value: str) -> str:
    """Classify a provider's explicit degraded-text response.

    Some APIs encode permission and throttling failures in a successful HTTP
    response body. Keeping these distinct from a genuinely empty dataset is
    important for operator action and fallback diagnosis.
    """
    text = str(value or "").lower()
    if any(token in text for token in ("permission", "unauthorized", "forbidden", "没有接口", "无权限")):
        return "auth_error"
    if any(token in text for token in ("rate limit", "ratelimit", "too many requests", "频繁", "限流")):
        return "rate_limited"
    if any(token in text for token in ("schema", "字段不存在", "数据格式")):
        return "schema_error"
    return "empty"
