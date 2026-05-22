"""Tests for skill file loader."""
import pytest
import tempfile
from pathlib import Path
from tradingagents.harness.skills.loader import load_skill_registry, _load_skill_file


def test_load_skill_registry_from_temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        bundled = Path(tmp)
        market_dir = bundled / "market"
        market_dir.mkdir()
        (market_dir / "indicator_library.md").write_text(
            """---
name: indicator_library
description: Technical indicator selection guide
applies_to_analyst: [market]
version: "1.0"
---
# Indicator Library

This skill covers RSI, MACD, and Bollinger Bands.""",
            encoding="utf-8",
        )
        registry = load_skill_registry(bundled)
        assert len(registry.list_skills()) == 1
        skill = registry.get("indicator_library")
        assert skill is not None
        assert skill.category == "market"
        assert "RSI" in skill.content
        assert skill.applies_to_analyst == ["market"]


def test_load_skill_without_frontmatter():
    """Test that skills without YAML frontmatter use filename as name."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "test.md"
        p.write_text("# No frontmatter skill\nContent here.", encoding="utf-8")
        skill = _load_skill_file(p, "news")
        assert skill.name == "test"
        assert skill.category == "news"
        assert skill.content == "# No frontmatter skill\nContent here."


def test_load_skill_registry_empty_dir():
    """Test that an empty directory returns an empty registry."""
    with tempfile.TemporaryDirectory() as tmp:
        registry = load_skill_registry(Path(tmp))
        assert len(registry.list_skills()) == 0


def test_load_skill_frontmatter_name_overrides_filename():
    """Test that YAML frontmatter 'name' field overrides filename."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "myfile.md"
        p.write_text(
            """---
name: overridden_name
description: Overridden description
applies_to_analyst: [fundamentals]
---
Content here.""",
            encoding="utf-8",
        )
        skill = _load_skill_file(p, "fundamentals")
        assert skill.name == "overridden_name"
        assert skill.description == "Overridden description"
        assert skill.applies_to_analyst == ["fundamentals"]
