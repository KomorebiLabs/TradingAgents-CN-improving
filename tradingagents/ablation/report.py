"""Ablation comparison report (R4): markdown table across configurations."""

from __future__ import annotations

from typing import Any, Dict, List


def build_report(
    header: str,
    cells: List[Dict[str, Any]],
    n_repeat: int,
    note: str = "",
) -> str:
    """Render a markdown ablation table from run_configuration cell dicts."""
    lines: List[str] = []
    lines.append(f"# Ablation Report — {header}\n")
    lines.append(f"- Repeats per cell: {n_repeat}")
    if note:
        lines.append(f"- {note}")
    lines.append("")

    lines.append(
        "| Config | Decision distribution | Consistency | Confidence (m±s) | "
        "Avg elapsed (s) | Route events | Compression rate |"
    )
    lines.append("|---|---|---|---|---|---|---|")

    for cell in cells:
        agg = cell.get("aggregate", {})
        dec = agg.get("decisions", {})
        dec_text = ", ".join(f"{k}:{v}" for k, v in sorted(dec.items())) if dec else "—"
        conf = agg.get("confidence_mean")
        conf_std = agg.get("confidence_std")
        conf_text = (
            f"{conf}±{conf_std}" if conf is not None else "—"
        )
        lines.append(
            f"| {cell.get('config', '')} ({cell.get('ticker', '')}) | {dec_text} | "
            f"{agg.get('consistency', 0.0)} | {conf_text} | {agg.get('avg_elapsed', 0.0)} | "
            f"{agg.get('avg_route_events', 0)} | {agg.get('compression_rate', 0.0)} |"
        )
    lines.append("")

    lines.append("## How to read this\n")
    lines.append(
        "- **Consistency** = majority-decision share across repeats (1.0 = fully stable). "
        "If multi-agent shows higher consistency than single-agent, debate de-risks decisions."
    )
    lines.append(
        "- **Confidence** is only populated when ``enable_confidence_score`` is on "
        "(LLM emits ``Confidence: N/100``)."
    )
    lines.append(
        "- **Route events / compression rate** proxy pipeline depth and token cost; "
        "deep debate should raise both — that is the trade-off quantified."
    )
    lines.append("- Real runs require an LLM API key and consume tokens.")
    return "\n".join(lines)
