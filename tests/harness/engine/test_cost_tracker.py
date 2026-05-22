"""Tests for CostTracker."""
import pytest
from tradingagents.harness.engine.api.usage import UsageSnapshot
from tradingagents.harness.engine.cost_tracker import CostTracker


def test_cost_tracker_initial_state():
    tracker = CostTracker()
    assert tracker.total.input_tokens == 0
    assert tracker.total.output_tokens == 0
    assert tracker.total.total_tokens == 0


def test_cost_tracker_add_single():
    tracker = CostTracker()
    tracker.add(UsageSnapshot(input_tokens=100, output_tokens=50))
    assert tracker.total.input_tokens == 100
    assert tracker.total.output_tokens == 50
    assert tracker.total.total_tokens == 150


def test_cost_tracker_accumulates():
    tracker = CostTracker()
    tracker.add(UsageSnapshot(input_tokens=100, output_tokens=50))
    tracker.add(UsageSnapshot(input_tokens=200, output_tokens=100))
    assert tracker.total.input_tokens == 300
    assert tracker.total.output_tokens == 150
    assert tracker.total.total_tokens == 450
