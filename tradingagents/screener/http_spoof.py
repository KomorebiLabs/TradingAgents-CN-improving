from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, Iterator

import requests


BROWSER_LIKE_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
}


@contextmanager
def patch_requests_browser_headers(
    extra_headers: Dict[str, str] | None = None,
) -> Iterator[None]:
    original_request = requests.sessions.Session.request
    merged_headers = dict(BROWSER_LIKE_HEADERS)
    if extra_headers:
        merged_headers.update(extra_headers)

    def wrapped_request(self, method, url, **kwargs):
        headers = dict(merged_headers)
        headers.update(kwargs.pop("headers", {}) or {})
        kwargs["headers"] = headers
        return original_request(self, method, url, **kwargs)

    requests.sessions.Session.request = wrapped_request
    try:
        yield
    finally:
        requests.sessions.Session.request = original_request
