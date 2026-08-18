"""Shared infrastructure for the AkShare vendor modules.

One reason to change: request-politeness / rate-limit strategy or generic
symbol/text helpers. Extracted verbatim from akshare_interface.py during the
Phase-4 split (2026-08-16).
"""
from __future__ import annotations

import time
import threading
from datetime import datetime, timedelta
from io import StringIO
from typing import Iterable, Tuple

import pandas as pd

from typing import Any  # rate-limit machinery annotations



class RequestThrottle:
    """请求节流器，控制 API 请求频率"""

    def __init__(self, min_interval: float = 1.0):
        """
        Args:
            min_interval: 最小请求间隔（秒），默认 1 秒
        """
        self.min_interval = min_interval
        self._last_request_time = 0.0
        self._lock = threading.Lock()

    def wait(self):
        """等待直到可以发送下一个请求"""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            self._last_request_time = time.time()

    def reset(self):
        """重置节流器"""
        with self._lock:
            self._last_request_time = 0.0


_throttle_tencent = RequestThrottle(min_interval=1.0)   # 腾讯财经：1秒间隔


_throttle_eastmoney = RequestThrottle(min_interval=1.5)  # 东方财富：1.5秒间隔


_throttle_news = RequestThrottle(min_interval=2.0)        # 新闻数据：2秒间隔


def _require_akshare():
    try:
        import akshare as ak
    except ImportError as exc:
        raise ImportError(
            "AkShare is required for vendor 'akshare'. Install it with `pip install akshare`."
        ) from exc
    return ak


def _normalize_cn_symbol(symbol: str) -> Tuple[str, str]:
    value = symbol.strip().upper()
    if "." in value:
        code, exchange = value.split(".", 1)
        exchange = exchange.upper()
        if exchange in {"SZ", "XSHE"}:
            return code, "sz"
        if exchange in {"SH", "XSHG"}:
            return code, "sh"
        if exchange in {"BJ", "BSE"}:
            return code, "bj"
    if value.startswith(("6", "9")):
        return value, "sh"
    if value.startswith(("0", "2", "3")):
        return value, "sz"
    if value.startswith(("4", "8")):
        return value, "bj"
    raise ValueError(
        f"Unsupported CN ticker format '{symbol}'. Use A-share symbols like 600519.SH or 000001.SZ."
    )


def _truncate_text(value: object, limit: int = 180) -> str:
    text = "" if value is None else str(value).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _render_bullets(lines: Iterable[str]) -> str:
    return "\n".join(f"- {line}" for line in lines if line)


# NOTE (2026-08-16): an unused rate-limit machinery (~90 lines of exception
# classes, _handle_rate_limit / _check_rate_limit / _rate_limit_state) lived
# here, inherited verbatim from akshare_interface.py. It had zero call sites
# and referenced an AlphaVantageRateLimitError that was never imported —
# it would have raised NameError on first use. Deleted during the split.
# interface.py's rate-limit detection matches exception class NAMES as
# strings, so no runtime coupling existed.
