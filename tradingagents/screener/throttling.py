from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass
class AntiBanConfig:
    base_interval: float = 0.5
    burst_threshold: int = 10
    burst_pause: float = 2.0
    failure_penalty: float = 1.5
    soft_rpm_limit: int = 30


class ThrottledRequester:
    def __init__(self, config: AntiBanConfig | None = None):
        self.config = config or AntiBanConfig()
        self._start_time = time.time()
        self._last_request_time = 0.0
        self._consecutive_requests = 0
        self._total_requests = 0
        self._failed_requests = 0
        self._warnings: List[str] = []
        self._last_error_detail: str = ""

    def request(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        self._total_requests += 1
        self._consecutive_requests += 1

        if self._consecutive_requests > self.config.burst_threshold:
            time.sleep(self.config.burst_pause)
            self._consecutive_requests = 1

        elapsed = time.time() - self._last_request_time
        if elapsed < self.config.base_interval:
            time.sleep(self.config.base_interval - elapsed)

        self._last_request_time = time.time()

        try:
            result = func(*args, **kwargs)
            self._last_error_detail = ""
            self._maybe_warn_rpm()
            return result
        except Exception as exc:
            self._failed_requests += 1
            self._last_error_detail = repr(exc)
            self._warnings.append(f"[ERROR] 请求失败: {getattr(func, '__name__', 'unknown')} -> {exc}")
            time.sleep(self.config.failure_penalty)
            self._maybe_warn_rpm()
            return None

    def get_last_error_detail(self) -> str:
        return self._last_error_detail

    def _maybe_warn_rpm(self) -> None:
        elapsed_minutes = max((time.time() - self._start_time) / 60.0, 1e-6)
        rpm = self._total_requests / elapsed_minutes
        if rpm > self.config.soft_rpm_limit:
            self._warnings.append(
                f"[WARN] 请求频率 {rpm:.1f}/min 超过软限制 {self.config.soft_rpm_limit}/min"
            )

    def get_stats(self) -> Dict[str, Any]:
        elapsed = time.time() - self._start_time
        return {
            "total_requests": self._total_requests,
            "failed_requests": self._failed_requests,
            "elapsed_seconds": round(elapsed, 1),
            "avg_interval": round(elapsed / max(1, self._total_requests), 2),
            "warnings": list(self._warnings),
        }
