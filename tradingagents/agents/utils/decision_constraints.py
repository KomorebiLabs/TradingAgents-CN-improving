"""Deterministic B3/B5 decision constraint helpers.

The LLM remains responsible for proposing a plan. These helpers only change
values that are explicitly labelled in the decision text and return a structured
override record for the audit trail.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


_POSITION_PATTERNS = (
    ("position", re.compile(r"((?<!industry_)position\s*:\s*)(\d+(?:\.\d+)?)\s*%", re.I)),
    ("position", re.compile(r"(<position>\s*)(\d+(?:\.\d+)?)(\s*%</position>)", re.I)),
    ("max_single", re.compile(r"(仓位|加仓至|增持至|建仓至|配置比例)[^0-9%]{0,8}(\d+(?:\.\d+)?)\s*%")),
)
_INDUSTRY_RE = re.compile(r"(industry_position\s*:\s*)(\d+(?:\.\d+)?)\s*%", re.I)
_CASH_RE = re.compile(r"(cash\s*ratio\s*:\s*)(\d+(?:\.\d+)?)\s*%", re.I)


def extract_position_proposals(text: str) -> List[dict]:
    """Extract explicitly labelled position proposals without interpreting prose."""
    proposals: List[dict] = []
    for field, pattern in _POSITION_PATTERNS:
        for match in pattern.finditer(text):
            proposals.append({
                "field": field,
                "proposed": float(match.group(2)),
                "start": match.start(2),
                "end": match.end(2),
                "raw": match.group(0),
            })
    for field, pattern in (("max_industry", _INDUSTRY_RE), ("cash_ratio", _CASH_RE)):
        for match in pattern.finditer(text):
            proposals.append({
                "field": field,
                "proposed": float(match.group(2)),
                "start": match.start(2),
                "end": match.end(2),
                "raw": match.group(0),
            })
    return sorted(proposals, key=lambda item: item["start"])


def enforce_portfolio_constraints(text: str, portfolio: Dict[str, Any]) -> Tuple[str, List[dict]]:
    """Clamp only explicit position fields to portfolio limits."""
    constraints = portfolio.get("constraints") or {}
    caps = {
        "max_single": float(constraints["max_single"]) * 100
        if constraints.get("max_single") is not None else None,
        "max_industry": float(constraints["max_industry"]) * 100
        if constraints.get("max_industry") is not None else None,
        "cash_ratio": float(constraints["cash_ratio"]) * 100
        if constraints.get("cash_ratio") is not None else None,
    }
    caps["position"] = caps["max_single"]
    proposals = extract_position_proposals(text)
    replacements: List[tuple[int, int, str]] = []
    overrides: List[dict] = []
    for proposal in proposals:
        field = proposal["field"]
        constraint_field = "max_single" if field == "position" else field
        cap = caps.get(constraint_field)
        if cap is None:
            continue
        proposed = proposal["proposed"]
        violates = proposed > cap if field != "cash_ratio" else proposed < cap
        if not violates:
            continue
        replacements.append((proposal["start"], proposal["end"], f"{cap:g}"))
        overrides.append({
            "field": constraint_field,
            "proposed": proposed,
            "cap": cap,
            "reason": "minimum" if field == "cash_ratio" else "maximum",
        })

    corrected = text
    for start, end, replacement in reversed(replacements):
        corrected = corrected[:start] + replacement + corrected[end:]
    return corrected, overrides
