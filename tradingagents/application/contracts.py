"""Typed use-case contracts for the Analyzer pipeline.

``AnalysisRequest`` is the single typed input for one deep analysis run;
``AnalysisResult`` is the single typed output. Both remain convertible to the
plain dicts the existing UI consumes (``to_dict`` / ``from_questionnaire``),
so the migration is contract-first without breaking any caller.
"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from tradingagents.default_config import DEFAULT_CONFIG

ANALYST_ORDER = ["market", "social", "news", "fundamentals"]

# Portfolio/Research Manager write `Confidence: N/100` inside <decision> when
# enable_confidence_score is on (see agents/managers/{research_manager,portfolio_manager}.py).
_CONFIDENCE_RE = re.compile(r"[Cc]onfidence\s*[:：]\s*(\d{1,3})(?:\s*/\s*100)?")

# Where the final <decision> text lives in AgentState (structured + flat mirrors).
_CONFIDENCE_TEXT_PATHS = (
    ("decision_blocks", "final_trade_decision"),
    "final_trade_decision",
    ("risk_debate_state", "judge_decision"),
    ("decision_blocks", "risk_decision"),
)


def extract_confidence_from_state(final_state: Dict[str, Any]) -> Optional[int]:
    """Extract the real final-decision confidence (0-100) from an AgentState.

    Priority:
      1. textual ``Confidence: N/100`` emitted by Portfolio/Research Manager
         when ``enable_confidence_score`` is enabled (searched across the
         decision texts above);
      2. numeric ``signal_card.initial_confidence`` from screener context, when
         present (fallback floor, not a fake);
      3. ``None`` — never fabricate a value.

    Returns an int in [0, 100] (UI renders an int progress bar), or ``None``.
    """
    for path in _CONFIDENCE_TEXT_PATHS:
        if isinstance(path, tuple):
            node = final_state.get(path[0])
            value = (node or {}).get(path[1]) if isinstance(node, dict) else None
        else:
            value = final_state.get(path)
        if isinstance(value, str):
            match = _CONFIDENCE_RE.search(value)
            if match:
                raw = int(match.group(1))
                return min(100, max(0, raw))

    screener = final_state.get("screener_context") or {}
    route_decision = screener.get("route_decision") or {}
    signal_card = route_decision.get("signal_card")
    if isinstance(signal_card, dict):
        initial = signal_card.get("initial_confidence")
        if isinstance(initial, (int, float)) and not isinstance(initial, bool):
            clipped = min(100, max(0, int(initial)))
            return clipped

    return None


@dataclass(frozen=True)
class AnalysisRequest:
    """One deep-analysis run request (typed replacement for the config dict).

    Field mapping from the questionnaire dict (``cli/analyze/app.get_user_config``):
    ticker, date, output_language, analysts (AnalystType enums -> value strings),
    research_depth, llm_provider, backend_url, shallow/deep_thinking_model,
    thinking_level / reasoning_effort / anthropic_effort.
    """

    ticker: str
    trade_date: str
    selected_analysts: tuple[str, ...] = tuple(ANALYST_ORDER)
    output_language: str = "English"
    research_depth: int = 1
    llm_provider: str = DEFAULT_CONFIG["llm_provider"]
    deep_think_llm: str = DEFAULT_CONFIG["deep_think_llm"]
    quick_think_llm: str = DEFAULT_CONFIG["quick_think_llm"]
    backend_url: Optional[str] = DEFAULT_CONFIG.get("backend_url")
    thinking_level: Optional[str] = None       # Google
    reasoning_effort: Optional[str] = None     # OpenAI
    anthropic_effort: Optional[str] = None     # Anthropic

    @classmethod
    def from_questionnaire(cls, config: Dict[str, Any]) -> "AnalysisRequest":
        """Build a request from the questionnaire dict (see cli/analyze/app.py)."""
        analysts = [
            getattr(a, "value", a) for a in config.get("analysts", ANALYST_ORDER)
        ]
        return cls(
            ticker=config["ticker"],
            trade_date=config["date"],
            selected_analysts=tuple(analysts),
            output_language=config.get("output_language", "English"),
            research_depth=config.get("research_depth", 1),
            llm_provider=config["llm_provider"],
            deep_think_llm=config["deep_thinking_model"],
            quick_think_llm=config["shallow_thinking_model"],
            backend_url=config.get("backend_url"),
            thinking_level=config.get("thinking_level"),
            reasoning_effort=config.get("reasoning_effort"),
            anthropic_effort=config.get("anthropic_effort"),
        )

    @classmethod
    def default_for(cls, ticker: str, trade_date: str | None = None) -> "AnalysisRequest":
        """Non-interactive defaults: all analysts, depth 1, config-default models."""
        return cls(
            ticker=ticker,
            trade_date=trade_date or datetime.now().strftime("%Y-%m-%d"),
        )

    def to_graph_config(self) -> Dict[str, Any]:
        """Full TradingAgentsGraph config (defaults merged with overrides)."""
        graph_config = deepcopy(DEFAULT_CONFIG)
        graph_config["max_debate_rounds"] = self.research_depth
        graph_config["max_risk_discuss_rounds"] = self.research_depth
        graph_config["quick_think_llm"] = self.quick_think_llm
        graph_config["deep_think_llm"] = self.deep_think_llm
        graph_config["backend_url"] = self.backend_url
        graph_config["llm_provider"] = self.llm_provider.lower()
        graph_config["google_thinking_level"] = self.thinking_level
        graph_config["openai_reasoning_effort"] = self.reasoning_effort
        graph_config["anthropic_effort"] = self.anthropic_effort
        graph_config["output_language"] = self.output_language
        return graph_config

    def analyst_keys(self) -> List[str]:
        """Selected analysts in canonical pipeline order."""
        selected = set(self.selected_analysts)
        return [key for key in ANALYST_ORDER if key in selected]


@dataclass
class AnalysisResult:
    """One deep-analysis run outcome (typed replacement for the result dict).

    ``confidence`` is populated by ``extract_confidence_from_state`` at the
    service assembly point: real value when available (LLM-emitted
    ``Confidence: N/100`` or screener initial_confidence), else ``None`` —
    never a faked 0.
    """

    ticker: str
    trade_date: str
    decision: str
    confidence: Optional[float] = None
    elapsed_time: float = 0.0
    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    report_path: Optional[Path] = None
    final_state: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Legacy dict shape consumed by ui/summary.py (keys must not drift)."""
        return {
            "ticker": self.ticker,
            "decision": self.decision,
            "confidence": self.confidence,
            "elapsed_time": self.elapsed_time,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "report_path": self.report_path,
            "final_state": self.final_state,
        }
