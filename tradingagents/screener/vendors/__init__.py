"""Per-vendor fetch implementations.

Each module has ONE reason to change: that vendor's API or response shape.
Functions take a ``VendorHttp`` instance for politeness/raw-HTTP and return
DataFrames or None — matching the ScreenerDataAccess contract exactly.

Submodules are imported eagerly so ``vendors.tencent`` etc. are ALWAYS
available (a missing attribute here crashed standalone ScreenerDataAccess
usage — R3 smoke-test find; fixed 2026-08).
"""

from __future__ import annotations

from tradingagents.screener.vendors import backup, misc, sina, tencent, ths  # noqa: F401

__all__ = ["tencent", "sina", "ths", "misc", "backup"]
