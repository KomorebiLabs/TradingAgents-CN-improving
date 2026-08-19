"""R11 tests: cost estimation, structured decision extraction, LLM cache. Offline."""

from __future__ import annotations

from types import SimpleNamespace

from tradingagents.llm_clients.cache import LLMCache, caching_invoke
from tradingagents.llm_clients.cost import estimate_cost, format_cost, model_cost
from tradingagents.graph.signal_processing import SignalProcessor


# ---------------------------------------------------------------------------
# cost
# ---------------------------------------------------------------------------


def test_cost_known_and_unknown_models():
    # gpt-4o: 1M in @2.5 + 1M out @10 = $12.5 (full million)
    assert estimate_cost("gpt-4o", 1_000_000, 1_000_000) == 2.5 + 10.0
    # proportional: 100k in + 20k out on gpt-4o-mini ($0.15 / $0.6 per M)
    assert estimate_cost("gpt-4o-mini", 100_000, 20_000) == 0.15 * 0.1 + 0.6 * 0.02
    # unknown model -> neutral fallback (no crash)
    cost = estimate_cost("made-up-model", 1000, 500)
    assert cost > 0
    assert estimate_cost(None, 0, 0) == 0.0


def test_format_cost():
    assert format_cost(0.05) == "$0.050"
    assert format_cost(0.001) == "0.10¢"


# ---------------------------------------------------------------------------
# structured decision extraction
# ---------------------------------------------------------------------------


class SpyLLM:
    def __init__(self):
        self.calls = 0
        self.content = "HOLD"

    def invoke(self, messages):
        self.calls += 1
        return SimpleNamespace(content=self.content)


def test_structured_extracts_unambiguous_decision_without_llm():
    llm = SpyLLM()
    sp = SignalProcessor(llm)
    assert sp.process_signal("Final rating: we recommend BUY with conviction.") == "BUY"
    assert llm.calls == 0  # regex path skips the LLM call entirely


def test_structured_respects_case_and_lowercase():
    llm = SpyLLM()
    sp = SignalProcessor(llm)
    assert sp.process_signal("outlook is sell, keep it short") == "SELL"
    assert llm.calls == 0


def test_ambiguous_two_tokens_falls_back_to_llm():
    llm = SpyLLM()
    sp = SignalProcessor(llm)
    assert sp.process_signal("Some say BUY, others HOLD — we need judgement.") == "HOLD"
    assert llm.calls == 1  # LLM invoked


def test_negation_not_trusted_by_regex():
    llm = SpyLLM()
    sp = SignalProcessor(llm)
    assert sp.process_signal("This is NOT a BUY opportunity.") == "HOLD"
    assert llm.calls == 1  # negation forces LLM path


def test_no_decision_token_falls_back():
    llm = SpyLLM()
    sp = SignalProcessor(llm)
    assert sp.process_signal("Nothing here.") == "HOLD"
    assert llm.calls == 1


# ---------------------------------------------------------------------------
# LLM cache
# ---------------------------------------------------------------------------


def test_cache_hits_and_misses():
    cache = LLMCache(maxsize=4)
    key = cache.key("gpt-4o", [("human", "hi")])
    assert cache.get(key) is None
    assert cache.stats()["misses"] == 1
    cache.put(key, "answer")
    assert cache.get(key) == "answer"
    assert cache.stats()["hits"] == 1


def test_caching_invoke_calls_underlying_once():
    cache = LLMCache()
    calls = {"n": 0}

    def invoke(messages):
        calls["n"] += 1
        return "ok"

    wrapped = caching_invoke(invoke, cache, model="m")
    messages = [("human", "same prompt")]
    assert wrapped(messages) == "ok"
    assert wrapped(messages) == "ok"
    assert calls["n"] == 1  # second call served from cache
