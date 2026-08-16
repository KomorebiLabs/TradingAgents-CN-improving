"""Vendor HTTP primitives shared by the fetch layer.

One reason to change: anti-ban / throttling / raw-HTTP strategy. Combines:
- per-vendor sleep with jitter (politeness),
- optional browser-header spoofing context,
- the raw Tencent direct GET used as the primary CN data source.

Extracted from ScreenerDataAccess (data_access.py) during the Phase 4 split.
"""

from __future__ import annotations

import random
import time
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Dict

from tradingagents.screener.http_spoof import patch_requests_browser_headers

__all__ = ["DataSourceConfig", "VendorHttp"]


@dataclass
class DataSourceConfig:
    """Politeness / retry tuning for vendor requests."""

    request_timeout: float = 10.0
    probe_timeout: float = 30.0
    max_retries: int = 2
    retry_delay: float = 1.0
    sina_page_interval: float = 1.5
    ths_interval: float = 1.0
    random_jitter: float = 0.1
    graceful_degrade: bool = True


class VendorHttp:
    """Politeness + raw HTTP helpers for vendor fetch functions."""

    def __init__(self, ds_config, spoof_browser_headers: bool = True):
        self._ds_config = ds_config
        self._spoof_browser_headers = spoof_browser_headers

    @classmethod
    def from_vendor_config(cls, ds_config, vendors: Dict[str, Any]) -> "VendorHttp":
        return cls(
            ds_config=ds_config,
            spoof_browser_headers=bool(vendors.get("spoof_browser_headers", True)),
        )

    def spoof(self):
        """Context manager that patches requests headers when enabled."""
        if self._spoof_browser_headers:
            return patch_requests_browser_headers()
        return nullcontext()

    def sleep_for_vendor(self, vendor: str) -> None:
        interval_map = {
            "sina": self._ds_config.sina_page_interval,
            "ths": self._ds_config.ths_interval,
            "tencent": 1.0,
            "baostock": 0.5,
            "baidu": 0.7,
        }
        base = float(interval_map.get(vendor, 0.5))
        jitter = random.uniform(0.0, max(0.0, self._ds_config.random_jitter))
        time.sleep(base + jitter)

    def tencent_direct(self, url: str, timeout: float = 10.0) -> str | None:
        """Raw Tencent direct HTTP GET; returns response text or None."""
        try:
            import requests

            self.sleep_for_vendor("tencent")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://finance.qq.com/",
                "Accept": "*/*",
            }
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None
