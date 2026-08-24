"""Deterministic financial ratios derived from tool evidence only."""

from __future__ import annotations

import re
from typing import Any, Iterable


_FACT_RE = re.compile(
    r"^(Revenue|Gross Profit|Net Income|Operating Cash Flow)\s*"
    r"\((\d{4}-\d{2}-\d{2})\):\s*([-+]?\d+(?:\.\d+)?)\s*元\s*$",
    re.MULTILINE,
)


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else str(content or "")


def build_financial_ratio_evidence(messages: Iterable[Any]) -> str:
    """Compute ratios only when numerator and denominator share one period."""
    facts: dict[str, dict[str, float]] = {}
    for message in messages:
        for label, period, raw_value in _FACT_RE.findall(_message_text(message)):
            facts.setdefault(period, {})[label] = float(raw_value)

    lines: list[str] = []
    for period in sorted(facts, reverse=True):
        period_facts = facts[period]
        revenue = period_facts.get("Revenue")
        if revenue is None or revenue == 0:
            continue
        for label, numerator_name in (
            ("OCF / Revenue", "Operating Cash Flow"),
            ("Gross Margin", "Gross Profit"),
            ("Net Margin", "Net Income"),
        ):
            numerator = period_facts.get(numerator_name)
            if numerator is None:
                continue
            ratio = numerator / revenue * 100.0
            lines.append(
                f"- {label} (period={period}; unit=CNY yuan): "
                f"{numerator:.2f} / {revenue:.2f} = {ratio:.2f}%"
            )

    if not lines:
        return ""
    return "## Deterministic financial ratios\n\n" + "\n".join(lines)
