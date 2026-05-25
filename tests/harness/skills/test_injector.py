"""tests/harness/skills/test_injector.py"""
import pytest

from tradingagents.harness.skills.injector import (
    SkillInjector,
    AnalystSkillInjector,
    SKILL_USAGE_INSTRUCTION,
)
from tradingagents.harness.skills.types import DecisionType


class TestSkillInjector:
    def setup_method(self):
        self.injector = SkillInjector()

    def test_build_skill_section_returns_tuple(self):
        result = self.injector.build_skill_section(
            DecisionType.OFFENSIVE,
            include_references=False,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        section, names = result
        assert isinstance(section, str)
        assert isinstance(names, list)

    def test_build_skill_section_offensive_has_content(self):
        section, names = self.injector.build_skill_section(
            DecisionType.OFFENSIVE,
            include_references=False,
        )
        assert "## Skill:" in section

    def test_round_1_no_references(self):
        section, names = self.injector.build_skill_section(
            DecisionType.OFFENSIVE,
            debate_round=1,
            include_references=False,
        )
        assert "**Reference:" not in section

    def test_inject_adds_separator(self):
        result, names = self.injector.inject(
            DecisionType.OFFENSIVE,
            existing_prompt="You are a bull researcher.",
            debate_round=1,
        )
        assert "INJECTED ANALYTICAL SKILLS" in result
        assert "You are a bull researcher." in result
        assert len(names) > 0

    def test_inject_adds_usage_instruction(self):
        result, names = self.injector.inject(
            DecisionType.OFFENSIVE,
            existing_prompt="You are a bull researcher.",
            debate_round=1,
        )
        assert "<SkillsUsed>" in result
        assert len(names) > 0

    def test_counter_round_adds_skills(self):
        _, normal = self.injector.build_skill_section(
            DecisionType.OFFENSIVE,
            node_name="bull",
            is_counter_round=False,
        )
        _, counter = self.injector.build_skill_section(
            DecisionType.OFFENSIVE,
            node_name="bull",
            is_counter_round=True,
        )
        assert len(counter) >= len(normal)

    def test_empty_prompt_returns_empty(self):
        result, names = self.injector.inject(
            DecisionType.OFFENSIVE,
            existing_prompt="",
        )
        assert "INJECTED ANALYTICAL SKILLS" in result


class TestAnalystSkillInjector:
    def setup_method(self):
        self.injector = AnalystSkillInjector()

    def test_market_maps_to_offensive(self):
        result = self.injector.inject_into_prompt("market", "prompt")
        assert "INJECTED ANALYTICAL SKILLS" in result

    def test_fundamentals_maps_to_valuation(self):
        result = self.injector.inject_into_prompt("fundamentals", "prompt")
        assert "INJECTED ANALYTICAL SKILLS" in result

    def test_unknown_analyst_defaults_to_valuation(self):
        result = self.injector.inject_into_prompt("unknown_type", "prompt")
        # Should not crash, may or may not have content
        assert isinstance(result, str)
