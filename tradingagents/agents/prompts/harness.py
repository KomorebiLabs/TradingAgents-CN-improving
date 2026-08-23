from __future__ import annotations

from typing import Iterable

from tradingagents.dataflows.config import get_config


def _output_language_directive() -> str:
    """Language directive appended to report-producing prompts.

    ``output_language`` reaches this module through the dataflows config
    store, which ``TradingAgentsGraph.__init__`` syncs at construction —
    before any node executes. Internal agent debate intentionally stays
    English (see default_config); only report-producing prompts get the
    directive.
    """
    lang = str(get_config().get("output_language") or "English").strip()
    if not lang or lang.lower() == "english":
        return ""
    return (
        f"\n\nOUTPUT LANGUAGE REQUIREMENT: Write your final report entirely in {lang}. "
        "Keep ticker symbols and standard financial abbreviations "
        "(e.g. PE, PEG, MACD, ATR) as-is."
    )


def build_collaboration_system_prompt(
    tool_names: str,
    role_prompt: str,
    current_date: str,
    instrument_context: str,
) -> str:
    """Shared harness-style wrapper for tool-using analyst prompts."""
    return (
        "You are a helpful AI assistant, collaborating with other assistants."
        " Use the provided tools to progress towards answering the question."
        " If you are unable to fully answer, that's OK; another assistant with different tools"
        " will help where you left off. Execute what you can to make progress."
        " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
        " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
        f" You have access to the following tools: {tool_names}.\n"
        f"{role_prompt}"
        f"For your reference, the current date is {current_date}. {instrument_context}"
        + _output_language_directive()
    )


def build_xml_decision_prompt(
    role_definition: str,
    task_instructions: str,
    few_shot_examples: str = "",
) -> str:
    """Build a shared XML-oriented prompt for decision agents."""
    parts = [
        role_definition,
        "Structure your response using these XML sections:",
        "<analysis>Summarize the key evidence and tradeoffs.</analysis>",
        "<decision>State the actionable recommendation and rationale.</decision>",
        "Keep the analysis concise, evidence-based, and professional.",
        task_instructions,
    ]
    if few_shot_examples:
        parts.append("Reference examples:\n" + few_shot_examples)
    parts.append(_output_language_directive())
    return "\n\n".join(p for p in parts if p)


def wrap_structured_sections(
    sections: Iterable[tuple[str, str]],
    include_xml_guidance: bool = False,
) -> str:
    """Compose shared prompt sections with optional future XML guidance."""
    rendered_sections = []
    if include_xml_guidance:
        rendered_sections.append(
            "When producing structured reasoning, prefer tagged sections such as "
            "<analysis> and <decision>. Do not emit fabricated tags unless instructed."
        )

    for title, body in sections:
        rendered_sections.append(f"{title}\n{body}")
    return "\n\n".join(rendered_sections)
