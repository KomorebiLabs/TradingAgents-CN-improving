"""Application layer: typed use-case contracts, execution events, services.

This package sits between the CLI/Python-API surface and the graph runtime:
``cli`` (and any future Web API) depends on ``application``; ``application``
depends on the graph/domain — never the other way around.
"""

from tradingagents.application.contracts import AnalysisRequest, AnalysisResult
from tradingagents.application.events import (
    AgentStatusChanged,
    AnalysisCompleted,
    AnalysisEvent,
    AnalysisStarted,
    ChunkEventTranslator,
    MessageEmitted,
    MetricsUpdated,
    ReportSectionUpdated,
    StageMarked,
    TimelineNoted,
    ToolCallObserved,
)
from tradingagents.application.service import AnalysisService

__all__ = [
    "AnalysisRequest",
    "AnalysisResult",
    "AnalysisService",
    "AnalysisEvent",
    "AnalysisStarted",
    "AnalysisCompleted",
    "MessageEmitted",
    "ToolCallObserved",
    "ReportSectionUpdated",
    "AgentStatusChanged",
    "TimelineNoted",
    "StageMarked",
    "MetricsUpdated",
    "ChunkEventTranslator",
]
