"""Evaluation report (R10): confusion matrix + accuracy as markdown."""

from __future__ import annotations

from typing import Any, Dict, List

from tradingagents.eval.cases import BUY_THRESHOLD, SELL_THRESHOLD
from tradingagents.eval.matrix import (
    DECISIONS,
    confusion_matrix,
    directional_stats,
    normalize_decision,
    overall_accuracy,
)


def build_report(
    title: str,
    results: List[Dict[str, Any]],
    horizon_days: int = 20,
    note: str = "",
    *,
    framework_ready: bool = True,
    real_model_run: bool = False,
) -> str:
    labels = [r["label"] for r in results]
    preds = [
        r.get("normalized_decision", normalize_decision(r.get("decision")))
        for r in results
    ]
    matrix = confusion_matrix(labels, preds)
    overall = overall_accuracy(matrix)
    directional = directional_stats(matrix)

    lines = [f"# Decision-Correctness Evaluation — {title}", ""]
    lines.append(f"- Cases: {len(results)} | horizon: {horizon_days} trading days")
    lines.append(
        f"- True labels: BUY forward-return ≥ +{BUY_THRESHOLD:.0%}, SELL ≤ {SELL_THRESHOLD:.0%}, else NEUTRAL"
    )
    lines.append(f"- Framework ready: {framework_ready} | Real model run: {real_model_run}")
    if note:
        lines.append(f"- {note}")
    lines.append("")

    lines.append("## Confusion Matrix (rows=ground truth, cols=predicted)\n")
    header = "| True \\ Pred | " + " | ".join(DECISIONS) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(DECISIONS) + 1))
    for label in ("BUY", "SELL", "NEUTRAL"):
        row = matrix.get(label, {})
        lines.append(f"| {label} | " + " | ".join(str(row.get(d, 0)) for d in DECISIONS) + " |")
    lines.append("")

    lines.append("## Accuracy\n")
    lines.append(f"- **Overall accuracy**: {overall['correct']}/{overall['total']} = {overall['accuracy']*100:.1f}%")
    lines.append(
        f"- **Directional accuracy** (correct side on BUY/SELL ground truth): "
        f"{directional['directional_correct']}/{directional['directional_total']} = "
        f"{directional['directional_accuracy']*100:.1f}%  (HOLD on a directional case = miss)"
    )
    lines.append("")

    lines.append("## Reading\n")
    lines.append(
        "- This is a **correctness baseline** LLM unit tests cannot provide "
        "(they freeze behavior; this checks whether decisions align with subsequent outcomes)."
    )
    if not real_model_run:
        lines.append(
            "- **Real model run: false** — the numbers above reflect offline "
            "framework/matrix validation, not an LLM benchmark result."
        )
    lines.append(
        "- A market-neutral random douze would score ~50% directional; above that suggests signal, "
        "below suggests the pipeline adds noise. Small-N results are indicative only."
    )
    lines.append("- Historical outcomes are event-dependent; NOT a live-trading guarantee.")
    return "\n".join(lines)
