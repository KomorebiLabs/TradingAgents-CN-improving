"""Tests for TokenCountingCallback."""
import pytest
from tradingagents.harness.engine.cost_tracker import CostTracker
from tradingagents.harness.engine.callbacks import TokenCountingCallback


class FakeResponse:
    def __init__(self, llm_output=None, usage_metadata=None, prompt_tokens=0, completion_tokens=0):
        self.llm_output = llm_output
        self.usage_metadata = usage_metadata
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


def test_callback_extracts_from_llm_output():
    tracker = CostTracker()
    cb = TokenCountingCallback(tracker)
    response = FakeResponse(
        llm_output={"usage": {"prompt_tokens": 100, "completion_tokens": 50}}
    )
    cb.on_llm_end(response)
    assert tracker.total.input_tokens == 100
    assert tracker.total.output_tokens == 50


def test_callback_extracts_from_usage_metadata():
    tracker = CostTracker()
    cb = TokenCountingCallback(tracker)
    response = FakeResponse(usage_metadata={"input_tokens": 200, "output_tokens": 80})
    cb.on_llm_end(response)
    assert tracker.total.input_tokens == 200
    assert tracker.total.output_tokens == 80


def test_callback_extracts_from_direct_attributes():
    tracker = CostTracker()
    cb = TokenCountingCallback(tracker)
    response = FakeResponse(prompt_tokens=300, completion_tokens=150)
    cb.on_llm_end(response)
    assert tracker.total.input_tokens == 300
    assert tracker.total.output_tokens == 150


def test_callback_accumulates_across_calls():
    tracker = CostTracker()
    cb = TokenCountingCallback(tracker)
    cb.on_llm_end(FakeResponse(prompt_tokens=100, completion_tokens=50))
    cb.on_llm_end(FakeResponse(prompt_tokens=200, completion_tokens=100))
    assert tracker.total.total_tokens == 450
