"""Tests for SkillRegistry."""
import pytest
from tradingagents.harness.skills.types import SkillDefinition
from tradingagents.harness.skills.registry import SkillRegistry


def test_registry_register_and_get():
    registry = SkillRegistry()
    skill = SkillDefinition(
        name="test_skill",
        description="A test skill",
        category="market",
        applies_to_analyst=["market"],
        content="# Test Skill Content",
    )
    registry.register(skill)
    assert registry.get("test_skill") is skill
    assert registry.get("nonexistent") is None


def test_registry_get_skills_for_analyst():
    registry = SkillRegistry()
    market_skill = SkillDefinition(
        name="m1", description="m", applies_to_analyst=["market"], content=""
    )
    fund_skill = SkillDefinition(
        name="f1", description="f", applies_to_analyst=["fundamentals"], content=""
    )
    both_skill = SkillDefinition(
        name="both", description="b", applies_to_analyst=["market", "fundamentals"], content=""
    )
    registry.register(market_skill)
    registry.register(fund_skill)
    registry.register(both_skill)

    market_skills = registry.get_skills_for_analyst("market")
    assert len(market_skills) == 2
    assert {s.name for s in market_skills} == {"m1", "both"}

    fund_skills = registry.get_skills_for_analyst("fundamentals")
    assert len(fund_skills) == 2
    assert {s.name for s in fund_skills} == {"f1", "both"}


def test_registry_get_skills_by_names():
    registry = SkillRegistry()
    registry.register(SkillDefinition(name="a", description="", applies_to_analyst=[], content=""))
    registry.register(SkillDefinition(name="b", description="", applies_to_analyst=[], content=""))
    skills = registry.get_skills_by_names(["a", "b", "c"])
    assert [s.name for s in skills] == ["a", "b"]
