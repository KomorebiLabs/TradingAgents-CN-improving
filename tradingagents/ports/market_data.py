"""MarketDataPort: the market-data capability seam.

Purpose
-------
Generic layers (``dataflows``) must not depend on the Screener application
layer (``tradingagents.screener``). They consume market data through this
port instead. The default implementation currently adapts
``ScreenerDataAccess`` (see ``_default_port``); when the vendor layer is
refactored into dedicated adapters (roadmap Phase 4), only the factory
below changes — every consumer keeps calling the port.

The port is also a process-wide shared instance: the underlying throttle
state and hist cache only work if the same data-access object is reused
across calls (the old ``cn_indicators`` path created a fresh instance per
call, silently disabling both).

Usage
-----
    from tradingagents.ports.market_data import get_market_data_port

    df = get_market_data_port().fetch_hist("600519", "2026-01-01", "2026-02-01")

Tests may inject a stub via ``set_market_data_port(stub)`` and tear down
with ``reset_market_data_port()``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable

from tradingagents.dataflows.config import get_config


@runtime_checkable
class MarketDataPort(Protocol):
    """Market-data capability contract (method names match ScreenerDataAccess)."""

    def fetch_hist(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> Any:
        """Historical OHLCV bars for a ticker, vendor fallback applied."""
        ...

    def fetch_spot_snapshot(self, market: str = "all") -> Any:
        """Realtime spot snapshot for a market scope."""
        ...

    def fetch_index_constituents(self, index_code: str) -> Any:
        """Constituents of an index (e.g. '000300')."""
        ...

    def fetch_concept_boards(self) -> Any:
        """Concept board listing."""
        ...

    def fetch_concept_constituents(self, concept_name: str) -> Any:
        """Constituents of a concept board by name."""
        ...

    def fetch_industry_boards(self) -> Any:
        """Industry board listing."""
        ...

    def fetch_fund_flow(
        self, symbol: str = "即时", symbol_type: str = "individual"
    ) -> Any:
        """Money-flow data (individual stock or market)."""
        ...


_port: Optional[MarketDataPort] = None


def set_market_data_port(port: MarketDataPort) -> None:
    """Inject a port implementation (tests / future adapters)."""
    global _port
    _port = port


def reset_market_data_port() -> None:
    """Drop the cached port (tests); next get re-creates the default."""
    global _port
    _port = None


def _default_port() -> MarketDataPort:
    # Lazy import: keeps the module-level graph free of
    # ports -> screener edges; the runtime composition point is here ONLY.
    from tradingagents.screener.data_access import ScreenerDataAccess

    return ScreenerDataAccess(config=get_config())


def get_market_data_port() -> MarketDataPort:
    """Return the process-wide shared market-data port.

    The instance is cached so throttle state and the hist cache persist
    across calls (per-call instantiation silently disables both).
    """
    global _port
    if _port is None:
        _port = _default_port()
    return _port
