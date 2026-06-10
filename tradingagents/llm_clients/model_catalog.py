"""Shared model catalog for CLI selections and validation.

All model names in this file are verified against live provider APIs as of June 2026.
Update this file when providers release new models or deprecate old ones.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

ModelOption = Tuple[str, str]
ProviderModeOptions = Dict[str, Dict[str, List[ModelOption]]]


MODEL_OPTIONS: ProviderModeOptions = {
    "openai": {
        "quick": [
            ("GPT-5.4 Mini - High-volume, low latency, best value", "gpt-5.4-mini"),
            ("GPT-5.4 Nano - Cheapest, simple high-volume tasks", "gpt-5.4-nano"),
            ("GPT-4.1 - Smartest non-reasoning model", "gpt-4.1"),
            ("GPT-4o - Balanced, proven", "gpt-4o"),
        ],
        "deep": [
            ("GPT-5.5 - Latest frontier, complex reasoning", "gpt-5.5"),
            ("GPT-5.5 Pro - Highest accuracy, premium pricing", "gpt-5.5-pro"),
            ("GPT-5.4 - Strong professional work model", "gpt-5.4"),
            ("GPT-5.4 Mini - Fast, strong tool use", "gpt-5.4-mini"),
        ],
    },
    "anthropic": {
        "quick": [
            ("Claude Sonnet 4.6 - Best speed and intelligence balance", "claude-sonnet-4-6"),
            ("Claude Haiku 4.5 - Fastest, near-instant responses", "claude-haiku-4-5"),
            ("Claude Sonnet 4.5 - Reliable, balanced", "claude-sonnet-4-5"),
        ],
        "deep": [
            ("Claude Opus 4.8 - Most intelligent, complex reasoning", "claude-opus-4-8"),
            ("Claude Opus 4.7 - Strong reasoning, agentic coding", "claude-opus-4-7"),
            ("Claude Fable 5 - Mythos-class, best overall capability", "claude-fable-5"),
            ("Claude Sonnet 4.6 - Best speed/intelligence balance", "claude-sonnet-4-6"),
        ],
    },
    "google": {
        "quick": [
            ("Gemini 3.5 Flash - Latest flagship, agentic and coding", "gemini-3.5-flash"),
            ("Gemini 3.1 Flash-Lite - Most cost-efficient", "gemini-3.1-flash-lite"),
            ("Gemini 3 Flash - Next-gen fast", "gemini-3-flash-preview"),
            ("Gemini 2.5 Flash - Stable, proven", "gemini-2.5-flash"),
        ],
        "deep": [
            ("Gemini 3.1 Pro - Complex reasoning, long-context", "gemini-3.1-pro-preview"),
            ("Gemini 3.5 Flash - Frontier performance, agentic", "gemini-3.5-flash"),
            ("Gemini 2.5 Pro - Stable professional model", "gemini-2.5-pro"),
            ("Gemini 3 Flash - Fast with Pro-level intelligence", "gemini-3-flash-preview"),
        ],
    },
    "xai": {
        "quick": [
            ("Grok 4.1 Fast - Speed optimized, 2M context", "grok-4-1-fast-non-reasoning"),
            ("Grok 4 Fast - Fast, balanced", "grok-4-fast-non-reasoning"),
            ("Grok 4.1 Fast (Reasoning) - High-performance reasoning", "grok-4-1-fast-reasoning"),
        ],
        "deep": [
            ("Grok 4 - Flagship model", "grok-4-0709"),
            ("Grok 4.1 Fast (Reasoning) - High-performance, 2M ctx", "grok-4-1-fast-reasoning"),
            ("Grok 4 Fast (Reasoning) - High-performance reasoning", "grok-4-fast-reasoning"),
            ("Grok 4.1 Fast (Non-Reasoning) - Speed optimized, 2M ctx", "grok-4-1-fast-non-reasoning"),
        ],
    },
    "deepseek": {
        "quick": [
            ("DeepSeek V4 Flash - Best price/performance, $0.003/M input", "deepseek-v4-flash"),
            ("DeepSeek V3 - Balanced, strong coding", "deepseek-v3"),
            ("Custom model ID", "custom"),
        ],
        "deep": [
            ("DeepSeek V4 Pro - Latest reasoning model", "deepseek-v4-pro"),
            ("DeepSeek V4 Flash - Best value, 1M context", "deepseek-v4-flash"),
            ("DeepSeek V3 - Strong all-around, coding", "deepseek-v3"),
            ("Custom model ID", "custom"),
        ],
    },
    "qwen": {
        "quick": [
            ("Qwen3 Flash - Latest fast model, best value", "qwen3-flash"),
            ("Qwen3.5 Flash - Proven stable, balanced", "qwen3.5-flash"),
            ("Qwen3-8B - Cheapest, 8B multilingual", "qwen3-8b"),
            ("Custom model ID", "custom"),
        ],
        "deep": [
            ("Qwen3 Max - Best overall capability", "qwen3-max"),
            ("Qwen3.6 Plus - Strong reasoning, latest", "qwen3.6-plus"),
            ("Qwen3.5 Plus - Stable, proven", "qwen3.5-plus"),
            ("Qwen-Max - Proven flagship, wide context", "qwen-max"),
        ],
    },
    "glm": {
        "quick": [
            ("GLM-5 - Best Chinese language quality", "glm-5"),
            ("GLM-4.7 - Fast, strong Chinese", "glm-4.7"),
            ("GLM-4-9B - Cheapest, lightweight tasks", "glm-4-9b-chat"),
            ("Custom model ID", "custom"),
        ],
        "deep": [
            ("GLM-5 - Best Chinese, Claude alternative", "glm-5"),
            ("GLM-5.1 - Latest, improved reasoning", "glm-5.1"),
            ("GLM-4-32B - Strong mid-range, Chinese", "glm-4-32b-chat"),
            ("Custom model ID", "custom"),
        ],
    },
    # OpenRouter: models fetched dynamically. Azure: any deployed model name.
    "ollama": {
        "quick": [
            ("Qwen3:latest (8B, local)", "qwen3:latest"),
            ("GLM-4.7-Flash:latest (30B, local)", "glm-4.7-flash:latest"),
            ("Llama 4 Scout:latest (local)", "llama4:latest"),
        ],
        "deep": [
            ("Qwen3:latest (8B, local)", "qwen3:latest"),
            ("GLM-4.7-Flash:latest (30B, local)", "glm-4.7-flash:latest"),
            ("Llama 4 Scout:latest (local)", "llama4:latest"),
        ],
    },
}


def get_model_options(provider: str, mode: str) -> List[ModelOption]:
    """Return shared model options for a provider and selection mode."""
    return MODEL_OPTIONS[provider.lower()][mode]


def get_known_models() -> Dict[str, List[str]]:
    """Build known model names from the shared CLI catalog."""
    return {
        provider: sorted(
            {
                value
                for options in mode_options.values()
                for _, value in options
            }
        )
        for provider, mode_options in MODEL_OPTIONS.items()
    }
