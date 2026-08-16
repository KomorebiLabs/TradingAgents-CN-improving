"""Typed vendor error boundary for the dataflows layer.

Only these EXPECTED failure categories may trigger vendor fallback /
degradation. Programming errors (AttributeError, TypeError, contract
violations) must bubble up and be observed — never swallowed.

All errors subclass RuntimeError so existing ``except RuntimeError``
handlers keep working during the migration.
"""

from __future__ import annotations


class VendorError(RuntimeError):
    """Base class for expected vendor failures."""


class VendorUnavailable(VendorError):
    """No registered vendor could serve the request (all failed or absent)."""


class VendorRateLimited(VendorError):
    """Vendor responded with a rate-limit / throttling signal."""


class DataNotFound(VendorError):
    """Vendor answered successfully but has no data for the request."""


class VendorSchemaChanged(VendorError):
    """Vendor response no longer matches the expected parse contract."""
