"""Typed use-case contracts for the Analyzer pipeline.

``AnalysisRequest`` is the single typed input for one deep analysis run;
``AnalysisResult`` is the single typed output. Both remain convertible to the
plain dicts the existing UI consumes (``to_dict`` / ``from_questionnaire``),
so the migration is contract-first without breaking any caller.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from tradingagents.default_config import DEFAULT_CONFIG

ANALYST_ORDER = ["market", "social", "news", "fundamentals"]


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

    ``confidence`` stays ``None`` until actually implemented — never a faked 0.
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
