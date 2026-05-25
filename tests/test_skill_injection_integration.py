"""tests/test_skill_injection_integration.py"""
import pytest

from tradingagents.harness.skills.injector import SkillInjector
from tradingagents.harness.skills.types import DecisionType
from tradingagents.harness.skills.audit import (
    parse_skill_usage,
    build_skill_audit_entry,
    build_skill_audit_summary,
)


class TestSkillInjectionIntegration:
    def setup_method(self):
        self.injector = SkillInjector()

    def test_all_decision_types_produce_sections(self):
        for dt in DecisionType:
            section, names = self.injector.build_skill_section(dt, include_references=False)
            assert isinstance(section, str), f"DecisionType.{dt} section not a string"

    def test_offensive_includes_breakout(self):
        section, names = self.injector.build_skill_section(
            DecisionType.OFFENSIVE, include_references=True
        )
        assert "breakout" in section.lower() or "trend" in section.lower()

    def test_defensive_includes_fraud_or_risk(self):
        section, names = self.injector.build_skill_section(
            DecisionType.DEFENSIVE, include_references=True
        )
        text_lower = section.lower()
        assert "fraud" in text_lower or "risk" in text_lower or "crowd" in text_lower

    def test_inject_adds_separator_and_usage_instruction(self):
        result, names = self.injector.inject(
            DecisionType.OFFENSIVE,
            existing_prompt="You are a bull researcher.",
            debate_round=1,
        )
        assert "INJECTED ANALYTICAL SKILLS" in result
        assert "You are a bull researcher." in result
        assert "<SkillsUsed>" in result
        assert len(names) > 0

    def test_round_1_no_references(self):
        result, names = self.injector.inject(
            DecisionType.OFFENSIVE,
            existing_prompt="You are a bull researcher.",
            debate_round=1,
        )
        assert "**Reference:" not in result

    def test_adjudication_includes_references(self):
        result, names = self.injector.inject(
            DecisionType.VALUATION,
            existing_prompt="You are a judge.",
            debate_round=1,
            is_adjudication=True,
        )
        # Adjudication rounds should include references

    def test_backward_compat_analyst_injector(self):
        from tradingagents.harness.skills.injector import AnalystSkillInjector
        inj = AnalystSkillInjector()
        result = inj.inject_into_prompt("market", "prompt")
        assert "INJECTED ANALYTICAL SKILLS" in result

    def test_counter_round_bull_gets_extra_skills(self):
        _, normal = self.injector.build_skill_section(
            DecisionType.OFFENSIVE, node_name="bull", is_counter_round=False
        )
        _, counter = self.injector.build_skill_section(
            DecisionType.OFFENSIVE, node_name="bull", is_counter_round=True
        )
        assert len(counter) > len(normal)

    def test_audit_entry_with_response(self):
        entry = build_skill_audit_entry(
            node_name="bull",
            decision_type="offensive",
            debate_round=2,
            is_counter_round=True,
            is_adjudication=False,
            injected_skill_names=["breakout-recognition", "volume-analysis"],
            response_content="<SkillsUsed>\n- breakout-recognition\n</SkillsUsed>",
        )
        assert entry.node_name == "bull"
        assert entry.skill_match_rate == 0.5
        assert entry.debate_round == 2

    def test_audit_summary(self):
        entries = [
            build_skill_audit_entry("bull", "offensive", 1, False, False,
                                    ["breakout"], "<SkillsUsed>\n- breakout\n</SkillsUsed>"),
        ]
        summary = build_skill_audit_summary(entries)
        assert summary["total_invocations"] == 1
        assert "breakout" in summary["all_declared_skills"]
        assert summary["avg_match_rate"] == 1.0
