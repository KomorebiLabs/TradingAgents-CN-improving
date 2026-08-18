"""Ports package: dependency-inversion seams between layers.

A port is a pure typing contract (no implementation imports). Consumers
depend on the port; the composition happens via ``set_*``/``get_*``
registries in each port module. See ``market_data.py``.
"""

__all__ = ["market_data"]
