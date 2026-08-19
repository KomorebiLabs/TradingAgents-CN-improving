"""Lightweight LLM response cache (R11). Optional, opt-in.

LRU keyed by (model, messages) — identical prompts skip a re-call, cutting
token spend on repeated/defensive calls. Enabled explicitly by the caller
(not wired by default: LLM outputs are stochastic, so caching is a deliberate
policy for deterministic/symmetric calls only).
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Any, Callable, Dict, Tuple


class LLMCache:
    """Thread-safe LRU response cache."""

    def __init__(self, maxsize: int = 256):
        self._data: "OrderedDict[str, Any]" = OrderedDict()
        self._max = max(maxsize, 1)
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def key(model: str, messages: Any) -> str:
        blob = f"{model}|{messages!r}"
        return hashlib.md5(blob.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key in self._data:
                self._hits += 1
                self._data.move_to_end(key)
                return self._data[key]
            self._misses += 1
            return None

    def put(self, key: str, result: Any) -> None:
        with self._lock:
            self._data[key] = result
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {"hits": self._hits, "misses": self._misses, "size": len(self._data)}


def caching_invoke(
    invoke: Callable[[Any], Any],
    cache: LLMCache,
    model: str = "",
) -> Callable[[Any], Any]:
    """Wrap an ``invoke(messages)`` callable with the cache."""

    def wrapper(messages: Any) -> Any:
        key = cache.key(model, messages)
        cached = cache.get(key)
        if cached is not None:
            return cached
        result = invoke(messages)
        cache.put(key, result)
        return result

    return wrapper
