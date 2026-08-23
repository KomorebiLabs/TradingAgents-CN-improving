"""A2: convergence-driven debate stopping.

Covers the convergence node (scoring, truncation floor, parse fallback,
feature flag) and the post-convergence router (early stop / escalate /
round-count fallback / escalation cap). Design rule under test throughout:
uncertainty always biases toward CONTINUING the debate.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from tradingagents.graph.conditional_logic import (
    MAX_EXTRA_ROUNDS,
    ConditionalLogic,
)
from tradingagents.graph.setup import (
    _latest_turn,
    _truncate_speech,
    create_debate_convergence_node,
)


class FakeLLM:
    def __init__(self, content):
        self.content = content
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        resp = MagicMock()
        resp.content = self.content
        return resp


def _state(bull_hist, bear_hist, count=2, score=None):
    debate = {
        "bull_history": bull_hist,
        "bear_history": bear_hist,
        "count": count,
        "latest_speaker": "Bear Researcher",
    }
    if score is not None:
        debate["convergence_score"] = score
    return {"investment_debate_state": debate, "orchestration": {}}


# ── helpers ───────────────────────────────────────────────────────────────


class TestSpeechHelpers:
    def test_latest_turn_extracts_final_speech(self):
        history = "Bull Analyst: first\nBull Analyst: second"
        assert _latest_turn(history, "Bull Analyst: ") == "Bull Analyst: second"

    def test_latest_turn_empty_history(self):
        assert _latest_turn("", "Bull Analyst: ") == ""

    def test_truncate_keeps_head_and_tail_with_marker(self):
        text = "H" * 3000 + "M" * 8000 + "T" * 1000
        out, truncated = _truncate_speech(text, budget=5000)
        assert truncated is True
        assert "已省略" in out
        assert out.startswith("H")
        assert out.endswith("T")

    def test_short_speech_not_truncated(self):
        out, truncated = _truncate_speech("short", budget=100)
        assert truncated is False and out == "short"


# ── convergence node ──────────────────────────────────────────────────────


class TestConvergenceNode:
    def test_score_parsed_and_logged(self):
        llm = FakeLLM('<convergence score="2" divergences="" consensus="moat intact"/>')
        node = create_debate_convergence_node(llm)
        out = node(_state("Bull Analyst: a", "Bear Analyst: b"))
        debate = out["investment_debate_state"]
        assert debate["convergence_score"] == 2
        assert debate["convergence_consensus"] == "moat intact"
        assert debate["convergence_log"][0]["count"] == 2
        assert out["orchestration"]["convergence_log"] == debate["convergence_log"]

    def test_parse_failure_falls_back_to_neutral(self):
        node = create_debate_convergence_node(FakeLLM("garbage response"))
        out = node(_state("Bull Analyst: a", "Bear Analyst: b"))
        assert out["investment_debate_state"]["convergence_score"] == 3

    def test_truncated_input_floors_score_at_3(self):
        """A2 hard rule: no early stop on partial evidence. Judge says 2 but
        the core rebuttal may live in the omitted 10K middle chars."""
        long_bull = "Bull Analyst: " + "x" * 9000 + "tail-end rebuttal"
        llm = FakeLLM('<convergence score="2" divergences="" consensus=""/>')
        node = create_debate_convergence_node(llm)
        out = node(_state(long_bull, "Bear Analyst: b"))
        assert out["investment_debate_state"]["convergence_score"] == 3
        assert out["investment_debate_state"]["convergence_log"][0]["truncated"] is True

    def test_feature_flag_off_is_noop(self):
        from tradingagents.dataflows.config import set_config

        set_config({"convergence_check": False})
        try:
            node = create_debate_convergence_node(FakeLLM("<convergence score='1'/>"))
            assert node(_state("Bull Analyst: a", "Bear Analyst: b")) == {}
        finally:
            set_config({"convergence_check": True})

    def test_score_clamped_to_range(self):
        node = create_debate_convergence_node(FakeLLM('<convergence score="9"/>'))
        out = node(_state("Bull Analyst: a", "Bear Analyst: b"))
        assert out["investment_debate_state"]["convergence_score"] == 5


# ── post-convergence router ───────────────────────────────────────────────


def _router():
    return ConditionalLogic(
        max_debate_rounds=2,
        max_risk_discuss_rounds=1,
        max_recur_limit=100,
    )


class TestConvergenceRouter:
    def test_early_stop_beats_round_count(self):
        # count=1 < limit=4, but converged -> judge immediately
        assert _router().should_continue_after_convergence(_state("b", "r", count=1, score=1)) == "Research Manager"

    def test_escalate_extends_beyond_round_limit(self):
        # count=4 == limit=4, still divergent -> one more round
        assert _router().should_continue_after_convergence(_state("b", "r", count=4, score=5)) == "Bull Researcher"

    def test_escalation_cap_bounds_extra_rounds(self):
        count = 4 + 2 * MAX_EXTRA_ROUNDS  # beyond cap -> conclude
        assert _router().should_continue_after_convergence(_state("b", "r", count=count, score=5)) == "Research Manager"

    def test_neutral_score_uses_round_count_logic(self):
        r = _router()
        assert r.should_continue_after_convergence(_state("b", "r", count=1, score=3)) == "Bull Researcher"
        assert r.should_continue_after_convergence(_state("b", "r", count=4, score=3)) == "Research Manager"

    def test_missing_score_uses_round_count_logic(self):
        r = _router()
        assert r.should_continue_after_convergence(_state("b", "r", count=4)) == "Research Manager"
        assert r.should_continue_after_convergence(_state("b", "r", count=2)) == "Bull Researcher"

    def test_route_reason_recorded(self):
        state = _state("b", "r", count=1, score=1)
        _router().should_continue_after_convergence(state)
        assert state["orchestration"]["route_reason"] == "convergence_early_stop"
