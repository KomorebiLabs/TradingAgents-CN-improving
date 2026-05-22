"""ScreenerContextInjector — selectively extracts Screener data and renders Markdown context."""
from typing import Any, Dict, List

from tradingagents.screener.models import SignalCard, SignalEvidence


class ScreenerContextInjector:
    """Extracts key Screener scan data from a SignalCard and renders it as Markdown.

    Injection scope (selective):
    1. Technical indicators from technical signal_breakdown raw_metrics
    2. Capital quality tag and scores from smart_money signal_breakdown
    3. Sector and concept tags
    4. Risk flags
    5. Overall screening score and confidence
    """

    def build_context(self, signal_card: SignalCard) -> str:
        """Build Markdown context string from a SignalCard.

        Args:
            signal_card: The SignalCard produced by Screener

        Returns:
            A Markdown string ready for injection into an Agent system prompt.
        """
        parts: List[str] = [
            "# Screener Scan Results",
            f"## {signal_card.ticker}",
            f"**Overall Score:** {signal_card.screening_score:.1f}  **Confidence:** {signal_card.initial_confidence:.1f}",
            "",
        ]

        if signal_card.sector_tags or signal_card.concept_tags:
            parts.append("## Tags")
            if signal_card.sector_tags:
                parts.append(f"- Sectors: {', '.join(signal_card.sector_tags)}")
            if signal_card.concept_tags:
                parts.append(f"- Concepts: {', '.join(signal_card.concept_tags)}")
            parts.append("")

        tech_metrics = self._extract_metrics(signal_card, "technical")
        if tech_metrics:
            parts.append("## Technical Metrics")
            for key, value in sorted(tech_metrics.items()):
                if isinstance(value, (dict, list)):
                    continue
                parts.append(f"- {key}: {value}")
            parts.append("")

        capital_metrics = self._extract_metrics(signal_card, "smart_money")
        if capital_metrics:
            parts.append("## Capital Quality")
            capital_tag = signal_card.evidence_snapshot.get("capital_quality_tag", "unknown")
            parts.append(f"- Quality Tag: {capital_tag}")
            for key in (
                "heat_quality_gap_score",
                "capital_quality_weight",
                "risk_constraint_score",
                "continuity_score",
                "quality_stability_index",
            ):
                if key in capital_metrics:
                    parts.append(f"- {key}: {capital_metrics[key]}")
            parts.append("")

        if signal_card.risk_flags:
            parts.append("## Risk Flags")
            for flag in signal_card.risk_flags:
                parts.append(f"- {flag}")
            parts.append("")

        if signal_card.strategy_sources:
            parts.append(f"**Signal Sources:** {', '.join(signal_card.strategy_sources)}")

        return "\n".join(parts)

    def _extract_metrics(self, card: SignalCard, strategy: str) -> Dict[str, Any]:
        """Extract raw_metrics from the first matching strategy evidence."""
        for evidence in card.signal_breakdown:
            if evidence.strategy == strategy:
                return evidence.raw_metrics or {}
        return {}
