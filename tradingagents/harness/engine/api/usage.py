"""Usage snapshot for token tracking."""
from pydantic import BaseModel


class UsageSnapshot(BaseModel):
    """Token usage snapshot for a single LLM call."""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
