# tradingagents/graph/signal_processing.py

import re
from typing import Any, Optional

_DECISION_RE = re.compile(r"\b(?:BUY|OVERWEIGHT|HOLD|UNDERWEIGHT|SELL)\b", re.IGNORECASE)
_NEGATION_HINTS = ("not", "no ", "without", "avoid")


class SignalProcessor:
    """Extract a trading decision from analyst output.

    R11 structured-first: a regex-extracted decision is used when it is UNAMBIGUOUS
    (exactly one distinct decision token, no negation nearby) — saving an LLM
    call and making the extractor deterministic. Otherwise it falls back to the
    LLM (existing behavior).
    """

    def __init__(self, quick_thinking_llm: Any):
        """Initialize with an LLM for processing."""
        self.quick_thinking_llm = quick_thinking_llm

    @staticmethod
    def _structured_decision(full_signal: str) -> Optional[str]:
        """Return an unambiguously present decision token, else None."""
        text = str(full_signal)
        matches = list(_DECISION_RE.finditer(text))
        distinct = {m.group(0).upper() for m in matches}
        if len(distinct) != 1:
            return None
        token = next(iter(distinct))
        for m in matches:
            before = text[max(0, m.start() - 8) : m.start()].lower()
            if any(h in before for h in _NEGATION_HINTS):
                return None  # e.g. "not a BUY"
        return token

    def process_signal(self, full_signal: str) -> str:
        """Extract the core decision — regex-first, LLM fallback."""
        structured = self._structured_decision(full_signal)
        if structured:
            return structured

        messages = [
            (
                "system",
                "You are an efficient assistant that extracts the trading decision from analyst reports. "
                "Extract the rating as exactly one of: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL. "
                "Output only the single rating word, nothing else.",
            ),
            ("human", full_signal),
        ]

        return self.quick_thinking_llm.invoke(messages).content
