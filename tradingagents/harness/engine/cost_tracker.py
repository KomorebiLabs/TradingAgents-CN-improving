"""Cost tracker — accumulates token usage across multiple LLM calls."""
from .api.usage import UsageSnapshot


class CostTracker:
    """Accumulates token usage across multiple LLM invocations."""

    def __init__(self) -> None:
        self._usage = UsageSnapshot(input_tokens=0, output_tokens=0)

    def add(self, usage: UsageSnapshot) -> None:
        self._usage = UsageSnapshot(
            input_tokens=self._usage.input_tokens + usage.input_tokens,
            output_tokens=self._usage.output_tokens + usage.output_tokens,
        )

    @property
    def total(self) -> UsageSnapshot:
        return self._usage
