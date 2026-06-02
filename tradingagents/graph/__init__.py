# TradingAgents/graph/__init__.py

from .conditional_logic import ConditionalLogic
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor

__all__ = [
    "ConditionalLogic",
    "Propagator",
    "Reflector",
    "SignalProcessor",
]

try:  # pragma: no cover - optional heavy graph runtime
    from .trading_graph import TradingAgentsGraph, GraphExecutionError
    from .setup import GraphSetup

    __all__.extend(
        [
            "TradingAgentsGraph",
            "GraphExecutionError",
            "GraphSetup",
        ]
    )
except Exception:
    pass
