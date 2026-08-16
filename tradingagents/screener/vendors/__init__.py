"""Per-vendor fetch implementations.

Each module has ONE reason to change: that vendor's API or response shape.
Functions take a ``VendorHttp`` instance for politeness/raw-HTTP and return
DataFrames or None — matching the ScreenerDataAccess contract exactly.
"""

__all__ = ["tencent", "sina", "ths", "misc"]
