from __future__ import annotations

from typing import Iterable


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
    return "\n\n".join(parts)


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
