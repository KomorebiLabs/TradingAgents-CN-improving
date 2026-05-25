"""tests/harness/skills/test_mapping.py"""
import pytest

from tradingagents.harness.skills.types import DecisionType
from tradingagents.harness.skills.mapping import (
    DecisionSkillMapper,
    DECISION_SKILL_MAPPING,
    COUNTER_ROUND_EXTRA,
)


class TestDecisionSkillMapping:
    def test_offensive_contains_expected_skills(self):
        skills = DECISION_SKILL_MAPPING[DecisionType.OFFENSIVE]
        assert "breakout-recognition" in skills
        assert "trend-patterns" in skills

    def test_defensive_contains_fraud_detection(self):
        skills = DECISION_SKILL_MAPPING[DecisionType.DEFENSIVE]
        assert "fraud-detection" in skills

    def test_valuation_contains_valuation_methods(self):
        skills = DECISION_SKILL_MAPPING[DecisionType.VALUATION]
        assert "valuation-methods" in skills

    def test_all_decision_types_have_skills(self):
        for dt in DecisionType:
            assert len(DECISION_SKILL_MAPPING[dt]) > 0, f"{dt} has no skills"

    def test_counter_round_extra_keys(self):
        assert "bull" in COUNTER_ROUND_EXTRA
        assert "bear" in COUNTER_ROUND_EXTRA


class TestDecisionSkillMapper:
    def setup_method(self):
        self.mapper = DecisionSkillMapper()

    def test_round_1_no_references(self):
        strategy = self.mapper.get_injection_strategy(debate_round=1)
        assert strategy["include_references"] is False

    def test_round_n_has_references(self):
        strategy = self.mapper.get_injection_strategy(debate_round=3)
        assert strategy["include_references"] is True

    def test_counter_round_adds_extra_skills(self):
        names = self.mapper.get_skill_names(
            DecisionType.OFFENSIVE,
            node_name="bull",
            is_counter_round=True,
        )
        assert "fraud-detection" in names

    def test_normal_round_no_extra(self):
        names = self.mapper.get_skill_names(
            DecisionType.OFFENSIVE,
            node_name="bull",
            is_counter_round=False,
        )
        assert "fraud-detection" not in names

    def test_adjudication_strategy(self):
        strategy = self.mapper.get_injection_strategy(
            debate_round=1,
            is_adjudication=True,
        )
        assert strategy["skill_strategy"] == "valuation_focused"
        assert strategy["include_references"] is True

    def test_custom_mapping_override(self):
        custom = {DecisionType.OFFENSIVE: ["breakout-recognition"]}
        mapper = DecisionSkillMapper(custom)
        names = mapper.get_skill_names(DecisionType.OFFENSIVE)
        assert names == ["breakout-recognition"]
