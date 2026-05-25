"""tests/harness/skills/test_audit.py"""
import pytest

from tradingagents.harness.skills.audit import (
    parse_skill_usage,
    build_skill_audit_entry,
    build_skill_audit_summary,
)


class TestParseSkillUsage:
    def test_parses_single_skill_with_justification(self):
        content = "<SkillsUsed>\n- breakout-recognition: 用于验证突破有效性\n</SkillsUsed>"
        records = parse_skill_usage(content)
        assert len(records) == 1
        assert records[0].skill_name == "breakout-recognition"
        assert "验证突破" in records[0].justification

    def test_parses_multiple_skills(self):
        content = "<SkillsUsed>\n- breakout-recognition\n- volume-analysis: 用于确认量能\n</SkillsUsed>"
        records = parse_skill_usage(content)
        assert len(records) == 2
        names = {r.skill_name for r in records}
        assert "breakout-recognition" in names
        assert "volume-analysis" in names

    def test_no_skills_used(self):
        content = "<SkillsUsed>\n- (none)\n</SkillsUsed>"
        records = parse_skill_usage(content)
        assert len(records) == 1
        assert records[0].skill_name == "(none)"

    def test_no_skills_block_returns_empty(self):
        content = "This is a regular response without skill usage."
        records = parse_skill_usage(content)
        assert records == []

    def test_ignores_comments_and_blank_lines(self):
        content = "<SkillsUsed>\n# comment\n\n- fraud-detection: some reason\n</SkillsUsed>"
        records = parse_skill_usage(content)
        assert len(records) == 1
        assert records[0].skill_name == "fraud-detection"


class TestBuildSkillAuditEntry:
    def test_match_rate_calculation(self):
        entry = build_skill_audit_entry(
            node_name="bull",
            decision_type="offensive",
            debate_round=1,
            is_counter_round=False,
            is_adjudication=False,
            injected_skill_names=["breakout-recognition", "volume-analysis"],
            response_content="<SkillsUsed>\n- breakout-recognition\n</SkillsUsed>",
        )
        assert entry.skill_match_rate == 0.5
        # volume-analysis was injected but not declared -> decluttered
        decluttered = sorted(set(entry.injected_skills) - {r.skill_name for r in entry.declared_skills})
        assert "volume-analysis" in decluttered

    def test_full_match_rate(self):
        entry = build_skill_audit_entry(
            node_name="bull",
            decision_type="offensive",
            debate_round=1,
            is_counter_round=False,
            is_adjudication=False,
            injected_skill_names=["breakout-recognition"],
            response_content="<SkillsUsed>\n- breakout-recognition\n</SkillsUsed>",
        )
        assert entry.skill_match_rate == 1.0

    def test_no_declaration(self):
        entry = build_skill_audit_entry(
            node_name="bull",
            decision_type="offensive",
            debate_round=1,
            is_counter_round=False,
            is_adjudication=False,
            injected_skill_names=["fraud-detection"],
            response_content="No skills used in this response.",
        )
        assert entry.skill_match_rate == 0.0
        assert entry.unmatched_declared == []

    def test_undeclared_skills(self):
        entry = build_skill_audit_entry(
            node_name="bear",
            decision_type="defensive",
            debate_round=2,
            is_counter_round=True,
            is_adjudication=False,
            injected_skill_names=["fraud-detection", "risk-constraint"],
            response_content="<SkillsUsed>\n- fraud-detection\n</SkillsUsed>",
        )
        assert entry.skill_match_rate == 0.5
        # risk-constraint was injected but not declared -> decluttered
        decluttered = sorted(set(entry.injected_skills) - {r.skill_name for r in entry.declared_skills})
        assert "risk-constraint" in decluttered


class TestBuildSkillAuditSummary:
    def test_summary_aggregates_entries(self):
        entries = [
            build_skill_audit_entry("bull", "offensive", 1, False, False,
                                    ["breakout"], "<SkillsUsed>\n- breakout\n</SkillsUsed>"),
            build_skill_audit_entry("bear", "defensive", 1, False, False,
                                    ["fraud-detection"], "<SkillsUsed>\n- fraud-detection\n</SkillsUsed>"),
        ]
        summary = build_skill_audit_summary(entries)
        assert summary["total_invocations"] == 2
        assert "breakout" in summary["all_declared_skills"]
        assert "fraud-detection" in summary["all_declared_skills"]
        assert summary["avg_match_rate"] == 1.0

    def test_decluttered_skills(self):
        entry = build_skill_audit_entry(
            "bull", "offensive", 1, False, False,
            ["breakout-recognition", "volume-analysis"],
            "<SkillsUsed>\n- breakout-recognition\n</SkillsUsed>",
        )
        summary = build_skill_audit_summary([entry])
        assert "volume-analysis" in summary["decluttered_skills"]
