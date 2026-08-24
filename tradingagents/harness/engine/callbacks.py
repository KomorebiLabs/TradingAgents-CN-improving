"""LangGraph/LangChain callback that feeds token usage into CostTracker."""
from langchain_core.callbacks import BaseCallbackHandler

from .cost_tracker import CostTracker
from .api.usage import UsageSnapshot


class TokenCountingCallback(BaseCallbackHandler):
    """Captures token usage from every LLM call and accumulates it in CostTracker."""

    def __init__(self, tracker: CostTracker) -> None:
        self.tracker = tracker

    def on_llm_end(self, response, **kwargs) -> None:
        usage = None

        # Chat models expose provider-normalized usage on the generated
        # AIMessage, not on LLMResult itself. This is the path used by Agnes
        # through langchain-openai.
        for generation_list in getattr(response, "generations", []) or []:
            for generation in generation_list or []:
                message = getattr(generation, "message", None)
                meta = getattr(message, "usage_metadata", None)
                if meta:
                    usage = meta
                    break
            if usage is not None:
                break

        # Legacy/provider-specific LangChain metadata.
        if usage is None and hasattr(response, "llm_output") and response.llm_output:
            llm_output = response.llm_output
            if isinstance(llm_output, dict):
                usage = (
                    llm_output.get("token_usage")
                    or llm_output.get("usage")
                    or llm_output
                )
            else:
                usage = llm_output

        # Path 2: response.usage_metadata (LangChain 1.x)
        if usage is None and hasattr(response, "usage_metadata") and response.usage_metadata:
            meta = response.usage_metadata
            usage = {
                "prompt_tokens": meta.get("input_tokens", 0),
                "completion_tokens": meta.get("output_tokens", 0),
            }

        # Path 3: direct attributes
        if usage is None:
            usage = {
                "prompt_tokens": getattr(response, "prompt_tokens", 0),
                "completion_tokens": getattr(response, "completion_tokens", 0),
            }

        input_tok = (
            usage.get("prompt_tokens", 0)
            or usage.get("input_tokens", 0)
            or usage.get("input_token_count", 0)
            or 0
        )
        output_tok = (
            usage.get("completion_tokens", 0)
            or usage.get("output_tokens", 0)
            or usage.get("output_token_count", 0)
            or 0
        )
        self.tracker.add(UsageSnapshot(input_tokens=input_tok, output_tokens=output_tok))
