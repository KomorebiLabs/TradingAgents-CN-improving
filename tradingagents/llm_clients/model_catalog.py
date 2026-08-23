"""Shared model catalog for CLI selections and validation.

R8 (trustworthiness): this catalog intentionally lists CONSERVATIVE, real,
widely-available model IDs rather than speculative "next-gen" names. Model
ecosystems move fast — treat this as a safe built-in subset and PREFER the
official provider docs / API for the exact current model IDs. The system
accepts any model id via config (``deep_think_llm`` / ``quick_think_llm`` /
custom), so this file only shapes the CLI picker, never constrains runtime.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

ModelOption = Tuple[str, str]
ProviderModeOptions = Dict[str, Dict[str, List[ModelOption]]]


MODEL_OPTIONS: ProviderModeOptions = {
    "openai": {
        "quick": [
            ("GPT-4o-mini - Fast, cheap, reliable", "gpt-4o-mini"),
            ("GPT-4o - Balanced, proven", "gpt-4o"),
            ("Custom model ID", "custom"),
        ],
        "deep": [
            ("GPT-4o - Balanced, proven", "gpt-4o"),
            ("GPT-4.1 - Stronger reasoning", "gpt-4.1"),
            ("Custom model ID", "custom"),
        ],
    },
    "anthropic": {
        "quick": [
            ("Claude 3.5 Haiku - Fast, reliable", "claude-3-5-haiku"),
            ("Claude 3.5 Sonnet - Balanced", "claude-3-5-sonnet"),
            ("Custom model ID", "custom"),
        ],
        "deep": [
            ("Claude 3.5 Sonnet - Strong reasoning", "claude-3-5-sonnet"),
            ("Claude 3 Opus - Deep reasoning", "claude-3-opus"),
            ("Custom model ID", "custom"),
        ],
    },
    "google": {
        "quick": [
            ("Gemini 1.5 Flash - Fast, efficient", "gemini-1.5-flash"),
            ("Gemini 2.0 Flash - Current fast tier", "gemini-2.0-flash"),
            ("Custom model ID", "custom"),
        ],
        "deep": [
            ("Gemini 1.5 Pro - Strong reasoning", "gemini-1.5-pro"),
            ("Gemini 2.0 Flash - Balanced", "gemini-2.0-flash"),
            ("Custom model ID", "custom"),
        ],
    },
    "xai": {
        "quick": [
            ("Grok 2 - Fast, chat", "grok-2"),
            ("Custom model ID", "custom"),
        ],
        "deep": [
            ("Grok 2 - Current public model", "grok-2"),
            ("Grok beta - Alternative", "grok-beta"),
            ("Custom model ID", "custom"),
        ],
    },
    "deepseek": {
        "quick": [
            ("DeepSeek Chat - V3, general purpose", "deepseek-chat"),
            ("Custom model ID", "custom"),
        ],
        "deep": [
            ("DeepSeek V3 - Strong reasoning", "deepseek-chat"),
            ("DeepSeek Reasoner - R1 reasoning", "deepseek-reasoner"),
            ("Custom model ID", "custom"),
        ],
    },
    "qwen": {
        "quick": [
            ("Qwen Plus - Balanced DashScope", "qwen-plus"),
            ("Qwen Turbo - Fast, cheap", "qwen-turbo"),
            ("Custom model ID", "custom"),
        ],
        "deep": [
            ("Qwen Max - Stronger DashScope", "qwen-max"),
            ("Qwen Long - Long-context", "qwen-long"),
            ("Custom model ID", "custom"),
        ],
    },
    "glm": {
        "quick": [
            ("GLM-4-Flash - Fast, free-tier China", "glm-4-flash"),
            ("GLM-4 - Balanced Zhipu", "glm-4"),
            ("Custom model ID", "custom"),
        ],
        "deep": [
            ("GLM-4-Plus - Stronger Zhipu", "glm-4-plus"),
            ("GLM-4-32B - Open mid-range", "glm-4-32b"),
            ("Custom model ID", "custom"),
        ],
    },
    "agnes": {
        "quick": [
            ("Agnes 2.5 Flash - Fast, free-tier compatible", "agnes-2.5-flash"),
            ("Custom model ID", "custom"),
        ],
        "deep": [
            ("Agnes 2.5 Flash - General purpose", "agnes-2.5-flash"),
            ("Custom model ID", "custom"),
        ],
    },
    # OpenRouter: models fetched dynamically. Azure: any deployed model name.
    "ollama": {
        "quick": [
            ("Qwen2.5:latest (7B, local)", "qwen2.5:latest"),
            ("GLM4:latest (9B, local)", "glm4:latest"),
            ("Llama3.1:latest (8B, local)", "llama3.1:latest"),
        ],
        "deep": [
            ("Qwen2.5:latest (7B, local)", "qwen2.5:latest"),
            ("GLM4:latest (9B, local)", "glm4:latest"),
            ("Llama3.1:latest (8B, local)", "llama3.1:latest"),
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
