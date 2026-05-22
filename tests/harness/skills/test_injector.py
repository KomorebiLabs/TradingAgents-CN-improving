"""Tests for SkillInjector."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from tradingagents.harness.skills.injector import SkillInjector, ANALYST_SKILL_MAPPING


def test_analyst_skill_mapping_defined():
    """Verify all analyst types are mapped."""
    assert "market" in ANALYST_SKILL_MAPPING
    assert "news" in ANALYST_SKILL_MAPPING
    assert "fundamentals" in ANALYST_SKILL_MAPPING
    assert "social" in ANALYST_SKILL_MAPPING
    assert len(ANALYST_SKILL_MAPPING["market"]) == 4
    assert len(ANALYST_SKILL_MAPPING["news"]) == 3
    assert len(ANALYST_SKILL_MAPPING["fundamentals"]) == 3
    assert len(ANALYST_SKILL_MAPPING["social"]) == 2


def test_injector_builds_skill_section():
    """Verify SkillInjector builds content from bundled skills."""
    injector = SkillInjector()  # uses bundled dir
    section = injector.build_skill_section("market")
    # Should contain at least the header or skill content
    assert isinstance(section, str)
    assert "Analytical Skills" in section or len(section) > 0


def test_injector_returns_empty_for_unknown_analyst():
    """Unknown analyst type returns empty string."""
    injector = SkillInjector()
    section = injector.build_skill_section("unknown_analyst")
    assert section == ""


def test_inject_into_prompt_returns_original_if_no_skills():
    """If no skills, inject_into_prompt returns the original prompt unchanged."""
    with tempfile.TemporaryDirectory() as tmp:
        bundled = Path(tmp)
        market_dir = bundled / "market"
        market_dir.mkdir()
        (market_dir / "m1.md").write_text(
            "---\nname: m1\ndescription: m1 desc\napplies_to_analyst: []\n---\nContent.",
            encoding="utf-8",
        )
        injector = SkillInjector(bundled)
        result = injector.inject_into_prompt("market", "You are a market analyst.")
        assert "You are a market analyst." in result


def test_inject_into_prompt_adds_separator_and_skills():
    """inject_into_prompt adds separator and skill content."""
    with tempfile.TemporaryDirectory() as tmp:
        bundled = Path(tmp)
        market_dir = bundled / "market"
        market_dir.mkdir()
        (market_dir / "test_skill.md").write_text(
            "---\nname: test_skill\ndescription: test desc\napplies_to_analyst: [market]\n---\n# Test Skill\n\nTest content.",
            encoding="utf-8",
        )
        injector = SkillInjector(bundled)
        with patch.object(
            injector,
            "build_skill_section",
            return_value="# Analytical Skills Available\n\n## Skill: test_skill\n\nTest content.",
        ):
            result = injector.inject_into_prompt("market", "You are a market analyst.")
        assert "You are a market analyst." in result
        assert "INJECTED ANALYTICAL SKILLS" in result
        assert "test_skill" in result


def test_build_skill_section_returns_empty_for_unknown_analyst():
    """Unknown analyst type with no mapping returns empty."""
    with tempfile.TemporaryDirectory() as tmp:
        bundled = Path(tmp)
        (bundled / "market").mkdir()
        injector = SkillInjector(bundled)
        section = injector.build_skill_section("nonexistent_analyst")
        assert section == ""
