"""R8 trustworthiness guard-rails: no speculative/fake model names in code or docs-facing catalogs."""

from __future__ import annotations

import pytest

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients.model_catalog import (
    MODEL_OPTIONS,
    get_known_models,
    get_model_options,
)

# tokens that should never appear in the catalog (fabricated/speculative names)
_FORBIDDEN = [
    "5.4", "5.5", "nano",           # GPT-5.x family
    "claude-4", "opus-4", "fable",  # Anthropic mythos
    "gemini-3",                     # Google v3 (speculative at catalog date)
    "grok-4",                       # xAI speculative
    "deepseek-v4",                  # DeepSeek speculative
    "qwen3", "3.5", "3.6",          # Qwen speculative
    "glm-5", "glm-4.7",             # GLM speculative
]


def _all_catalog_ids() -> list:
    ids = []
    for mode_opts in MODEL_OPTIONS.values():
        for options in mode_opts.values():
            ids.extend(value for _, value in options)
    return ids


def test_no_speculative_model_names_in_catalog():
    ids = " ".join(_all_catalog_ids())
    for token in _FORBIDDEN:
        assert token.replace(".", r"\.") not in ids, f"forbidden speculative token: {token}"


def test_every_provider_has_quick_and_deep():
    for provider, modes in MODEL_OPTIONS.items():
        assert "quick" in modes and "deep" in modes, provider
        assert modes["quick"], f"{provider}/quick empty"
        assert modes["deep"], f"{provider}/deep empty"


def test_default_models_exist_in_catalog():
    provider = DEFAULT_CONFIG["llm_provider"]
    known = get_known_models()[provider]
    assert DEFAULT_CONFIG["deep_think_llm"] in known
    assert DEFAULT_CONFIG["quick_think_llm"] in known


def test_default_provider_is_openai_with_real_ids():
    assert DEFAULT_CONFIG["llm_provider"] == "openai"
    assert DEFAULT_CONFIG["deep_think_llm"] in {"gpt-4o", "gpt-4.1", "gpt-4o-mini"}
    assert DEFAULT_CONFIG["quick_think_llm"] in {"gpt-4o", "gpt-4o-mini"}


def test_agnes_provider_uses_official_model_id():
    assert get_model_options("agnes", "quick")[0][1] == "agnes-2.5-flash"
    assert get_model_options("agnes", "deep")[0][1] == "agnes-2.5-flash"
    assert "agnes-2.5-flash" in get_known_models()["agnes"]


    opts = get_model_options("openai", "quick")
    assert all(len(opt) == 2 for opt in opts)
    assert get_model_options("deepseek", "deep")[0][1] in {"deepseek-chat", "deepseek-reasoner"}
