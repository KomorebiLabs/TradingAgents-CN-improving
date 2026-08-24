"""A6: untrusted-content isolation for tool data entering LLM context.

Layer 2 of the four-layer injection defense (constitution prompt / salted
delimiters / pattern filter / audit log):
- Salted delimiters use a NON-standard, natural-language-like boundary with a
  per-process random salt: attackers cannot pre-forge a closing tag to break
  out of the data region. The salt is exposed for artifact auditing.
- The pattern filter strips instruction-shaped sentences (imperative +
  self-referential). Criterion is INSTRUCTION STRUCTURE, never sentiment
  strength — a screaming headline is data, "ignore previous instructions"
  is an attack.
- Every filtered hit is logged (audit layer 4).

Honest boundary: salted delimiters stop tag-escape attacks; they cannot stop
in-content instructions — that is the constitution layer's job (lower the
compliance rate, not immunity).
"""

from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from dataclasses import dataclass, field
from uuid import uuid4

logger = logging.getLogger(__name__)

_SALT = uuid4().hex[:8]


@dataclass
class SecurityContext:
    run_id: str
    salt: str = field(default_factory=lambda: uuid4().hex[:8])
    filtered_count: int = 0
    entries: list[dict] = field(default_factory=list)


_SECURITY_CONTEXT: ContextVar[SecurityContext | None] = ContextVar(
    "tradingagents_security_context", default=None
)


def start_security_context(run_id: str) -> SecurityContext:
    """Start a fresh run-scoped salt and injection audit context."""
    context = SecurityContext(run_id=str(run_id))
    _SECURITY_CONTEXT.set(context)
    return context


def finish_security_context() -> dict:
    """Return and clear the current run audit without retaining raw content."""
    context = _SECURITY_CONTEXT.get()
    if context is None:
        return {
            "run_id": "",
            "salt": _SALT,
            "filtered_count": 0,
            "entries": [],
        }
    audit = {
        "run_id": context.run_id,
        "salt": context.salt,
        "filtered_count": context.filtered_count,
        "entries": list(context.entries),
    }
    _SECURITY_CONTEXT.set(None)
    return audit


def security_audit_snapshot() -> dict:
    """Return a safe snapshot for emitting timeline events during a run."""
    context = _SECURITY_CONTEXT.get()
    if context is None:
        return {"filtered_count": 0, "entries": []}
    return {
        "filtered_count": context.filtered_count,
        "entries": list(context.entries),
    }

# method-name keywords whose results are wrapped (news/social/text sources);
# tabular market data (CSV) is left raw to avoid polluting parseable data
_WRAP_FOR = ("news", "social", "sentiment", "announcement", "notice")

_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore (?:all )?(?:previous|prior|above) (?:instructions?|prompts?|rules?)",
        r"disregard .{0,24}(?:instruction|prompt|rule)",
        r"you must now (?:act|become|output|ignore)",
        r"(?:new|your) system prompt\s*[:：]",
        r"忘[记掉](?:之前|以上|所有|前面)(?:的)?(?:指令|提示|规则)",
        r"你必须(?:现在)?(?:扮演|输出|忽略|执行)",
        r"(?:从现在起|接下来)你(?:是|要)",
    )
]


def current_salt() -> str:
    """Return the run salt, or the compatibility process salt outside a run."""
    context = _SECURITY_CONTEXT.get()
    return context.salt if context is not None else _SALT


def should_wrap(method_name: str) -> bool:
    return any(k in method_name.lower() for k in _WRAP_FOR)


def sanitize_untrusted(text: str, source: str = "tool") -> str:
    """Strip instruction-shaped sentences, wrap in salted delimiters."""
    filtered = 0

    def _replace(m):
        nonlocal filtered
        filtered += 1
        return "[injection_filtered]"

    for pattern in _INJECTION_PATTERNS:
        text = pattern.sub(_replace, text)

    context = _SECURITY_CONTEXT.get()
    if filtered and context is not None:
        context.filtered_count += filtered
        context.entries.append({"source": source, "count": filtered})

    if filtered:
        logger.warning(
            "[injection-defense] %d instruction-shaped fragment(s) stripped from %s (salt=%s)",
            filtered, source, current_salt(),
        )
    return (
        f"<<<UNTRUSTED_DATA_{current_salt()}>>>\n"
        f"{text}\n"
        f"<<<END_UNTRUSTED_DATA_{current_salt()}>>>"
    )
