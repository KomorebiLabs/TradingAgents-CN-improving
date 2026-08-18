"""Runtime configuration store for the dataflows layer.

A module-level singleton holding the effective config dict. Semantics:

- ``initialize_config()``: copy ``DEFAULT_CONFIG`` into the store on first use;
- ``set_config(config)``: top-level ``dict.update`` merge (partial configs allowed);
- ``get_config()``: returns a shallow copy — nested dicts (e.g. ``data_vendors``)
  remain shared references with the store.

Priority (highest first):
1. ``set_config()`` calls — ``TradingAgentsGraph.__init__`` pushes its merged
   config here so graph settings drive data-vendor routing;
2. environment variables (read by the underlying vendor modules);
3. ``default_config.DEFAULT_CONFIG``.

Note: ``TradingAgentsGraph`` keeps its own instance config; this store is the
dataflows-side view of it, synchronized once at graph construction time.
"""

import tradingagents.default_config as default_config
from typing import Dict, Optional

_config: Optional[Dict] = None


def initialize_config():
    """Initialize the store from DEFAULT_CONFIG if not yet initialized."""
    global _config
    if _config is None:
        _config = default_config.DEFAULT_CONFIG.copy()


def set_config(config: Dict):
    """Merge ``config`` into the store (top-level keys only, later wins)."""
    global _config
    if _config is None:
        _config = default_config.DEFAULT_CONFIG.copy()
    _config.update(config)


def get_config() -> Dict:
    """Return a shallow copy of the current config (nested dicts shared)."""
    if _config is None:
        initialize_config()
    return _config.copy()


# Initialize on import so any get_config() call sees defaults immediately.
initialize_config()
