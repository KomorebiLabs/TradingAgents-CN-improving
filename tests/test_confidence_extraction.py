"""Confidence extraction tests (task H).

Validates `extract_confidence_from_state`: real value from LLM-emitted
`Confidence: N/100` text (enable_confidence_score path) or screener
initial_confidence fallback; None when neither exists (never faked).
"""

from __future__ import annotations

from tradingagents.application.contracts import extract_confidence_from_state


def test_extract_from_decision_block_text():
    state = {
        "decision_blocks": {"final_trade_decision": "BUY. Confidence: 85/100. Growth intact."},
    }
    assert extract_confidence_from_state(state) == 85


def test_extract_from_flat_final_trade_decision():
    state = {"final_trade_decision": "HOLD. Confidence: 72"}
    assert extract_confidence_from_state(state) == 72


def test_extract_chinese_colon_and_case():
    state = {"final_trade_decision": "买入。confidence：90/100。"}
    assert extract_confidence_from_state(state) == 90


def test_extract_from_risk_judge_decision():
    state = {"risk_debate_state": {"judge_decision": "SELL. Confidence: 40/100."}}
    assert extract_confidence_from_state(state) == 40


def test_clamps_out_of_range():
    assert extract_confidence_from_state({"final_trade_decision": "Confidence: 150"}) == 100
    assert extract_confidence_from_state({"final_trade_decision": "Confidence: 0/100"}) == 0


def test_text_priority_over_signal_card_fallback():
    state = {
        "final_trade_decision": "Confidence: 88/100",
        "screener_context": {"route_decision": {"signal_card": {"initial_confidence": 55.0}}},
    }
    assert extract_confidence_from_state(state) == 88


def test_fallback_to_screener_initial_confidence():
    state = {
        "screener_context": {"route_decision": {"signal_card": {"initial_confidence": 83.4}}},
    }
    assert extract_confidence_from_state(state) == 83


def test_fallback_clamped():
    state = {
        "screener_context": {"route_decision": {"signal_card": {"initial_confidence": 200.0}}},
    }
    assert extract_confidence_from_state(state) == 100


def test_none_when_no_source():
    assert extract_confidence_from_state({}) is None
    assert extract_confidence_from_state({"decision_blocks": {}, "final_trade_decision": "BUY"}) is None
    assert extract_confidence_from_state({"decision_blocks": {"final_trade_decision": "not a confidence"}}) is None


def test_defensive_missing_paths():
    # decision_blocks absent entirely (plain dict access must not crash)
    assert extract_confidence_from_state({"screener_context": {}}) is None
    assert extract_confidence_from_state({"risk_debate_state": None}) is None


def test_ignores_non_string_confidence_field():
    assert extract_confidence_from_state({"final_trade_decision": 42}) is None


def test_ignores_boolean_signal_card_value():
    state = {"screener_context": {"route_decision": {"signal_card": {"initial_confidence": True}}}}
    assert extract_confidence_from_state(state) is None
