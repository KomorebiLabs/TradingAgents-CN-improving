"""LLM cost estimation (R11): approximate $ per run from token usage.

Prices are APPROXIMATE public list prices (per 1M tokens) at catalog time —
use them only to size experiments and compare runs, never for billing. Unknown
models fall back to a neutral rate.
"""

from __future__ import annotations

from typing import Optional

# Approximate USD per 1M tokens (input / output)
COST_PER_MT_IN: dict = {
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.0, 8.0),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
    "claude-3-5-haiku": (0.80, 4.0),
    "claude-3-5-sonnet": (3.0, 15.0),
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    "qwen-plus": (0.40, 1.20),
    "glm-4": (0.10, 0.10),
}
_FALLBACK = (1.0, 2.0)  # neutral unknown-model rate


def model_cost(model: Optional[str]) -> tuple:
    if not model:
        return _FALLBACK
    return COST_PER_MT_IN.get(model.lower(), _FALLBACK)


def estimate_cost(model: Optional[str], tokens_in: int, tokens_out: int) -> float:
    """Estimated USD cost for one call/run."""
    in_rate, out_rate = model_cost(model)
    return (tokens_in / 1_000_000) * in_rate + (tokens_out / 1_000_000) * out_rate


def format_cost(cost: float) -> str:
    if cost >= 0.01:
        return f"${cost:.3f}"
    return f"{cost * 100:.2f}¢"
