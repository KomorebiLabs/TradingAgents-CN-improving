"""Offline Agnes provider wiring tests; no network or API key required."""

from __future__ import annotations

from types import SimpleNamespace

from cli import prompts as rich_prompts
from cli import utils as legacy_utils
from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients import openai_client


_AGNES_URL = "https://apihub.agnes-ai.com/v1"


def test_factory_routes_agnes_through_openai_compatible_client():
    client = create_llm_client("agnes", "agnes-2.5-flash")

    assert isinstance(client, openai_client.OpenAIClient)
    assert client.provider == "agnes"
    assert client.model == "agnes-2.5-flash"


def test_agnes_client_uses_base_url_and_environment_key(monkeypatch):
    captured = {}

    class FakeChat:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("AGNES_API_KEY", "test-only-key")
    monkeypatch.setattr(openai_client, "NormalizedChatOpenAI", FakeChat)

    client = create_llm_client("agnes", "agnes-2.5-flash")
    client.get_llm()

    assert captured["model"] == "agnes-2.5-flash"
    assert captured["base_url"] == _AGNES_URL
    assert captured["api_key"] == "test-only-key"
    assert "test-only-key" not in repr(client)


def test_rich_cli_lists_agnes_provider(monkeypatch):
    captured = {}

    def fake_ask(_prompt, **kwargs):
        captured["choices"] = kwargs["choices"]
        return "Agnes AI"

    monkeypatch.setattr(rich_prompts.Prompt, "ask", fake_ask)

    assert rich_prompts.ask_llm_provider() == ("agnes", _AGNES_URL)
    assert "Agnes AI" in captured["choices"]


def test_questionary_cli_lists_agnes_provider(monkeypatch):
    captured = {}

    def fake_select(_prompt, choices, **_kwargs):
        captured["values"] = [choice.value for choice in choices]
        return SimpleNamespace(ask=lambda: ("agnes", _AGNES_URL))

    monkeypatch.setattr(legacy_utils.questionary, "select", fake_select)

    assert legacy_utils.select_llm_provider() == ("agnes", _AGNES_URL)
    assert ("agnes", _AGNES_URL) in captured["values"]


def test_rich_model_prompt_accepts_numeric_selection(monkeypatch):
    captured = {}

    def fake_ask(prompt, **kwargs):
        if "model number" in prompt:
            captured["choices"] = kwargs["choices"]
            return "1"
        raise AssertionError(f"unexpected prompt: {prompt}")

    monkeypatch.setattr(rich_prompts.Prompt, "ask", fake_ask)

    assert rich_prompts.ask_model("agnes", "quick") == "agnes-2.5-flash"
    assert captured["choices"] == ["1", "2"]
