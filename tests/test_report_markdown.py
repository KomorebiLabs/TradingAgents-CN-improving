"""Report artifact presentation tests.

Covers the .md polishing applied at the presentation layer:
- XML section wrappers (<analysis>/<decision>/<SkillsUsed>) become Markdown
  headings in the report files (state/event payloads keep the raw tags).
"""

from __future__ import annotations

from cli.analyze.run_impl import _markdownify_report_content


def test_xml_wrappers_become_markdown_headings():
    raw = "\n\n\n<analysis>\nEvidence summary.\n</analysis>\n<decision>\nHOLD\n</decision>"
    md = _markdownify_report_content(raw)

    assert "<analysis>" not in md and "</decision>" not in md
    assert "### Analysis" in md
    assert "### Decision" in md
    assert "Evidence summary." in md and "HOLD" in md
    # leading blank lines left by the stripped first tag are collapsed
    assert md.startswith("### Analysis")


def test_skillsused_heading():
    raw = "<SkillsUsed>\n- trend-patterns: assessed range structure\n</SkillsUsed>"
    md = _markdownify_report_content(raw)
    assert "### Skills Used" in md
    assert "- trend-patterns" in md


def test_plain_content_untouched():
    assert _markdownify_report_content("plain report text") == "plain report text"


def test_unknown_tags_pass_through():
    # tags outside the known set are left as-is (structured extraction
    # downstream may still need them)
    raw = "<foo>bar</foo>"
    assert _markdownify_report_content(raw) == raw
