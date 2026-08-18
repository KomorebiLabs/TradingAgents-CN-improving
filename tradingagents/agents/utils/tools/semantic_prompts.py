"""Screener semantic prompt/flow-control construction and validation."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from tradingagents.dataflows.config import get_config

SEMANTIC_PROMPT_SCHEMA_NAME = "screener.semantic_prompt_slots"


SEMANTIC_PROMPT_SCHEMA_VERSION = "1.0"


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Only applied to user-facing agents (analysts, portfolio manager).
    Internal debate agents stay in English for reasoning quality.
    """
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def build_screener_semantic_instruction(
    state: Dict[str, Any],
    audience: str,
) -> str:
    """Render audience-specific prompt guidance from Screener semantic slots."""
    slots = dict(state.get("semantic_prompt_slots", {}) or {})
    if not slots:
        return ""

    schema_name = str(slots.get("schema_name", "") or "")
    schema_version = str(slots.get("schema_version", "") or "")
    schema_note = ""
    if schema_name != SEMANTIC_PROMPT_SCHEMA_NAME or schema_version != SEMANTIC_PROMPT_SCHEMA_VERSION:
        schema_note = (
            f"Semantic slot schema mismatch detected "
            f"(name={schema_name or 'missing'}, version={schema_version or 'missing'}); "
            f"treat semantic routing guidance conservatively."
        )

    policy_role = str(slots.get("policy_role", "") or "")
    capital_quality = str(slots.get("capital_quality", "") or "")
    decision_summary = str(slots.get("decision_summary", "") or "")
    trigger_reason = str(slots.get("trigger_reason", "") or "")
    risk_flags = slots.get("risk_flags", []) or []
    route_decision = state.get("route_decision", {}) or state.get("screener_context", {}).get("route_decision", {}) or {}
    route_family = str(route_decision.get("route_family", "") or "")
    conflict_tier = str(route_decision.get("conflict_tier", "") or "")
    analyst_focus = route_decision.get("analyst_focus", []) or []
    debate_rounds = str(route_decision.get("debate_rounds", "") or "")
    debate_risk_weight = str(route_decision.get("debate_risk_weight", "") or "")
    selected_analysts = route_decision.get("selected_analysts", []) or []
    policy_overlap = slots.get("policy_multi_concept_overlap_count", "N/A")
    policy_primary_score = slots.get("policy_primary_concept_score", "N/A")
    policy_competition_score = slots.get("policy_concept_competition_score", "N/A")
    policy_concept_conviction = slots.get("policy_concept_conviction_score", "N/A")
    policy_selection_summary = str(slots.get("policy_primary_concept_selection_summary", "") or "")
    capital_heat_gap = slots.get("capital_heat_quality_gap_score", "N/A")
    capital_quality_weight = slots.get("capital_quality_weight", "N/A")
    capital_risk_constraint = slots.get("capital_risk_constraint_score", "N/A")
    capital_continuity = slots.get("capital_continuity_score", "N/A")
    capital_quality_stability_index = slots.get("capital_quality_stability_index", "N/A")
    technical_structure_risk = slots.get("technical_structure_risk_score", "N/A")
    technical_extension = slots.get("technical_recent_extension_pct", "N/A")
    technical_volume_confirmation = slots.get("technical_volume_confirmation_score", "N/A")
    technical_breakout_quality = slots.get("technical_breakout_quality_score", "N/A")
    technical_volume_divergence = slots.get("technical_volume_price_divergence_score", "N/A")
    technical_signal_consistency_index = slots.get("technical_signal_consistency_index", "N/A")
    semantic_priority = slots.get("semantic_priority", "N/A")
    semantic_decision_reasons = slots.get("semantic_decision_reasons", []) or []

    common = [
        f"Semantic slot schema: {schema_name or 'missing'} v{schema_version or 'missing'}.",
        f"Screener semantic routing context: policy_role={policy_role or 'none'}, capital_quality={capital_quality or 'none'}, trigger_reason={trigger_reason or 'unknown'}.",
        f"Merger semantic decision summary: {decision_summary or 'none'}.",
        f"Structured semantic factors: semantic_priority={semantic_priority}, policy_overlap={policy_overlap}, policy_primary_score={policy_primary_score}, policy_competition_score={policy_competition_score}, policy_concept_conviction={policy_concept_conviction}, capital_heat_gap={capital_heat_gap}, capital_quality_weight={capital_quality_weight}, capital_risk_constraint={capital_risk_constraint}, capital_continuity={capital_continuity}, capital_quality_stability_index={capital_quality_stability_index}, technical_structure_risk={technical_structure_risk}, technical_extension={technical_extension}, technical_volume_confirmation={technical_volume_confirmation}, technical_breakout_quality={technical_breakout_quality}, technical_volume_divergence={technical_volume_divergence}, technical_signal_consistency_index={technical_signal_consistency_index}.",
    ]
    if schema_note:
        common.append(schema_note)
    if risk_flags:
        common.append(f"Existing Screener risk flags: {', '.join(str(flag) for flag in risk_flags)}.")
    if semantic_decision_reasons:
        common.append(f"Structured semantic decision reasons: {', '.join(str(reason) for reason in semantic_decision_reasons)}.")
    if policy_selection_summary:
        common.append(f"Primary concept selection summary: {policy_selection_summary}.")
    if route_family or selected_analysts:
        common.append(
            f"Graph route decision: route_family={route_family or 'none'}, conflict_tier={conflict_tier or 'none'}, "
            f"debate_rounds={debate_rounds or 'unknown'}, debate_risk_weight={debate_risk_weight or 'unknown'}, "
            f"selected_analysts={selected_analysts}, analyst_focus={analyst_focus}."
        )

    audience_specific: List[str] = []

    if audience == "market":
        if policy_role in {"policy_top_stock", "policy_core_member"}:
            audience_specific.append(
                "Treat the chart as a concept-board leader candidate and verify whether price/flow structure supports board leadership rather than generic momentum."
            )
        try:
            if int(policy_overlap) >= 2:
                audience_specific.append(
                    "This candidate sits in overlapping concepts; check whether price structure confirms true cross-theme leadership instead of diluted thematic tagging."
                )
        except Exception:
            pass
        if capital_quality == "capital_quality_speculative":
            audience_specific.append(
                "Prioritize detecting unstable breakout structure, execution pressure, and false-momentum risk because capital quality is speculative."
            )
        elif capital_quality in {"capital_quality_high", "capital_quality_persistent"}:
            audience_specific.append(
                "Check whether technical trend persistence confirms the Screener view of sustained capital support."
            )
        try:
            if float(technical_volume_divergence) <= 42 or float(technical_extension) >= 8:
                audience_specific.append(
                    "Explicitly test for volume-price divergence, overextension, and exhaustion rather than assuming breakout continuation."
                )
        except Exception:
            pass
        if conflict_tier in {"high", "severe"}:
            audience_specific.append(
                "This candidate was routed as a high-conflict case; prioritize contradiction checking and avoid over-trusting the first bullish signal."
            )

    elif audience == "news":
        if policy_role in {"policy_top_stock", "policy_core_member"}:
            audience_specific.append(
                "Prioritize concept-board catalyst verification, policy implementation links, and whether this name is a real beneficiary rather than a weak thematic passenger."
            )
        try:
            if int(policy_overlap) >= 2:
                audience_specific.append(
                    "Because this stock is a multi-concept overlap name, separate core driver news from incidental theme co-mentions."
                )
        except Exception:
            pass
        if capital_quality == "capital_quality_speculative":
            audience_specific.append(
                "Look for hype-driven headlines, overheated narratives, and low-substance catalysts that could explain high-heat low-quality flows."
            )
        if conflict_tier in {"high", "severe"}:
            audience_specific.append(
                "Because routing marked this as a conflict-heavy case, distinguish genuine catalyst confirmation from noisy narrative spillover."
            )

    elif audience == "social":
        if capital_quality == "capital_quality_speculative":
            audience_specific.append(
                "Treat social sentiment as a potential overheating signal; distinguish sticky conviction from short-lived crowd excitement."
            )
        elif capital_quality in {"capital_quality_high", "capital_quality_persistent"}:
            audience_specific.append(
                "Check whether sentiment support looks durable and consistent with multi-day capital persistence."
            )
        try:
            if float(capital_heat_gap) >= 22:
                audience_specific.append(
                    "Heat/quality gap is wide; focus on whether social buzz is detached from quality, continuity, and risk-control evidence."
                )
        except Exception:
            pass
        if debate_rounds == "compressed":
            audience_specific.append(
                "The graph route is compressed; focus on the most decision-relevant sentiment signal instead of broad mood summarization."
            )

    elif audience == "fundamentals":
        if capital_quality == "capital_quality_speculative":
            audience_specific.append(
                "Actively test whether valuation, earnings quality, and balance-sheet strength are weak relative to the current market heat."
            )
        elif policy_role in {"policy_top_stock", "policy_core_member"}:
            audience_specific.append(
                "Evaluate whether fundamentals can justify this stock being treated as a concept-board leader rather than a pure narrative trade."
            )
        try:
            if float(capital_heat_gap) >= 22:
                audience_specific.append(
                    "The Screener marked this as a heat-quality gap case; prioritize disproving narrative enthusiasm with hard valuation and quality constraints."
                )
        except Exception:
            pass
        if conflict_tier in {"high", "severe"}:
            audience_specific.append(
                "Because graph routing marked this as conflict-heavy, test fundamentals against the strongest opposing thesis rather than confirming only the favorable side."
            )

    elif audience == "research_manager":
        if policy_role == "policy_top_stock":
            audience_specific.append(
                "Weigh board-leadership evidence explicitly when deciding whether the bull case is thematic substance or only short-term theme-chasing."
            )
        try:
            if int(policy_overlap) >= 2:
                audience_specific.append(
                    "Because this is a multi-concept overlap name, judge which concept truly dominates the thesis and which overlaps are only supportive."
                )
        except Exception:
            pass
        if capital_quality == "capital_quality_speculative":
            audience_specific.append(
                "Demand stronger downside and valuation rebuttals before endorsing a bullish stance because Screener marked capital quality as speculative."
            )
        if conflict_tier in {"high", "severe"}:
            audience_specific.append(
                "This is a routed conflict case; explicitly state what evidence would falsify the bullish view."
            )

    elif audience == "trader":
        if capital_quality == "capital_quality_speculative":
            audience_specific.append(
                "If taking risk, prefer tactical sizing, tighter stops, and event-driven execution discipline instead of broad conviction sizing."
            )
        elif capital_quality in {"capital_quality_high", "capital_quality_persistent"}:
            audience_specific.append(
                "You may consider higher conviction only if timing and risk controls align with the sustained-capital thesis."
            )
        try:
            if float(capital_heat_gap) >= 22 or float(technical_volume_divergence) <= 42:
                audience_specific.append(
                    "Treat this as a high-heat low-quality or price-volume-divergence trade candidate: execution should bias toward faster validation and faster exit on failure."
                )
        except Exception:
            pass
        if policy_role == "policy_top_stock":
            audience_specific.append(
                "Treat this as a possible board-leader trade and think in terms of leadership continuation versus failed leadership."
            )
        if debate_rounds == "compressed" or debate_risk_weight == "high":
            audience_specific.append(
                "The graph route is compressed/high-risk; make your recommendation concise, explicit, and tightly risk-aware."
            )

    elif audience == "portfolio_manager":
        if capital_quality == "capital_quality_speculative":
            audience_specific.append(
                "Apply stricter position sizing, scenario analysis, and downgrade thresholds because the flow profile is speculative."
            )
        elif capital_quality in {"capital_quality_high", "capital_quality_persistent"}:
            audience_specific.append(
                "If the broader evidence agrees, sustained-capital quality can justify a less defensive rating than a generic momentum name."
            )
        try:
            if float(capital_heat_gap) >= 22:
                audience_specific.append(
                    "This is a heat-quality mismatch case; require stronger downside asymmetry and more skeptical sizing than a standard thematic winner."
                )
        except Exception:
            pass
        if policy_role in {"policy_top_stock", "policy_core_member"}:
            audience_specific.append(
                "Explicitly judge whether concept-board leadership strengthens the final rating or only increases crowding risk."
            )
        if conflict_tier in {"high", "severe"}:
            audience_specific.append(
                "Because routing marked this as a high-conflict case, require a clearer downside case before green-lighting size."
            )

    rendered = common + audience_specific
    if not rendered:
        return ""
    return " ".join(rendered)


def build_semantic_execution_profile(state: Dict[str, Any], audience: str) -> Dict[str, Any]:
    """Derive runtime execution controls from semantic routing context."""
    slots = validate_semantic_prompt_slots(
        state.get("semantic_prompt_slots")
        or state.get("screener_context", {}).get("semantic_prompt_slots", {})
        or {}
    )
    route_decision = dict(
        state.get("route_decision")
        or state.get("screener_context", {}).get("route_decision", {})
        or {}
    )
    audit = dict(state.get("orchestration", {}).get("semantic_trigger_audit", {}) or {})
    trigger_reasons = list(audit.get("semantic_trigger_reasons", []) or [])

    policy_role = str(route_decision.get("policy_role", "") or slots.get("policy_role", "") or "none")
    capital_quality = str(route_decision.get("capital_quality", "") or slots.get("capital_quality", "") or "none")
    conflict_tier = str(route_decision.get("conflict_tier", "") or "none")
    debate_risk_weight = str(route_decision.get("debate_risk_weight", "") or "normal")
    analyst_focus = list(route_decision.get("analyst_focus", []) or [])
    selected_analysts = list(route_decision.get("selected_analysts", []) or [])

    memory_n_matches = 2
    trader_plan_char_limit = None
    emphasize_risk = False
    compress_to_highest_signal = False
    route_behavior_tag = "standard"
    response_style = "balanced"
    conclusion_mode = "standard"
    evidence_must_include: List[str] = []
    max_context_chars = 3200

    if capital_quality == "capital_quality_speculative" or debate_risk_weight == "high":
        memory_n_matches = 1
        trader_plan_char_limit = 1800
        emphasize_risk = True
        compress_to_highest_signal = True
        route_behavior_tag = "speculative_hardened"
        response_style = "concise_risk_first"
        conclusion_mode = "risk_first"
        max_context_chars = 1800
        evidence_must_include.extend(
            ["downside_invalidation", "liquidity_exit_plan", "crowding_unwind_risk"]
        )
    elif policy_role == "policy_top_stock" and capital_quality in {"capital_quality_high", "capital_quality_persistent"}:
        memory_n_matches = 3
        route_behavior_tag = "top_stock_priority"
        response_style = "thesis_first"
        conclusion_mode = "leader_continuation_vs_failure"
        evidence_must_include.extend(["board_leadership_confirmation", "trend_persistence_check"])
    elif policy_role == "policy_core_member":
        memory_n_matches = 2
        route_behavior_tag = "core_member_balanced"
        response_style = "balanced"
        conclusion_mode = "member_quality_confirmation"
        evidence_must_include.append("member_role_validation")

    if conflict_tier in {"high", "severe"}:
        emphasize_risk = True
        route_behavior_tag = f"{route_behavior_tag}_conflict"
        response_style = "conflict_resolution"
        evidence_must_include.append("strongest_counterargument_resolution")
    if "concept_overlap" in analyst_focus and policy_role in {"policy_top_stock", "policy_core_member"}:
        route_behavior_tag = f"{route_behavior_tag}_overlap"
        evidence_must_include.append("primary_concept_disambiguation")
    if "technical_risk" in analyst_focus:
        emphasize_risk = True
        evidence_must_include.append("technical_failure_trigger")
    try:
        if float(slots.get("technical_signal_consistency_index", 50.0)) <= 45:
            emphasize_risk = True
            compress_to_highest_signal = True
            response_style = "concise_risk_first"
            conclusion_mode = "risk_first"
            evidence_must_include.append("signal_consistency_failure")
            max_context_chars = min(max_context_chars, 1800)
    except Exception:
        pass
    try:
        if float(slots.get("policy_concept_conviction_score", 50.0)) >= 75 and policy_role in {
            "policy_top_stock",
            "policy_core_member",
        }:
            route_behavior_tag = f"{route_behavior_tag}_policy_conviction"
            if response_style == "balanced":
                response_style = "thesis_first"
            evidence_must_include.append("concept_conviction_validation")
    except Exception:
        pass
    try:
        if float(slots.get("capital_quality_stability_index", 50.0)) <= 48:
            emphasize_risk = True
            route_behavior_tag = f"{route_behavior_tag}_capital_instability"
            evidence_must_include.append("capital_stability_failure")
    except Exception:
        pass
    if audience in {"risk", "portfolio_manager"} and trader_plan_char_limit is None and debate_risk_weight == "high":
        trader_plan_char_limit = 1800

    return {
        "policy_role": policy_role,
        "capital_quality": capital_quality,
        "conflict_tier": conflict_tier,
        "debate_risk_weight": debate_risk_weight,
        "analyst_focus": analyst_focus,
        "selected_analysts": selected_analysts,
        "trigger_reasons": trigger_reasons,
        "memory_n_matches": memory_n_matches,
        "trader_plan_char_limit": trader_plan_char_limit,
        "emphasize_risk": emphasize_risk,
        "compress_to_highest_signal": compress_to_highest_signal,
        "route_behavior_tag": route_behavior_tag,
        "response_style": response_style,
        "conclusion_mode": conclusion_mode,
        "evidence_must_include": sorted(set(evidence_must_include)),
        "max_context_chars": max_context_chars,
    }


def build_conclusion_template_instruction(conclusion_mode: str) -> str:
    mode = str(conclusion_mode or "standard")
    if mode == "risk_first":
        return (
            "Use this conclusion template exactly: "
            "1) Primary Risks, 2) Decision, 3) Invalidation/Exit Conditions."
        )
    if mode == "leader_continuation_vs_failure":
        return (
            "Use this conclusion template exactly: "
            "1) Leadership Continuation Evidence, 2) Leadership Failure Triggers, 3) Decision."
        )
    if mode == "member_quality_confirmation":
        return (
            "Use this conclusion template exactly: "
            "1) Member-Role Quality Check, 2) Risk Controls, 3) Decision."
        )
    return "Use a clear 3-part conclusion: Thesis, Risks, Decision."


def validate_semantic_prompt_slots(slots: Dict[str, Any] | None) -> Dict[str, Any]:
    """Normalize semantic slots and surface schema/version drift explicitly."""
    slots = dict(slots or {})
    schema_name = str(slots.get("schema_name", "") or "")
    schema_version = str(slots.get("schema_version", "") or "")
    valid = schema_name == SEMANTIC_PROMPT_SCHEMA_NAME and schema_version == SEMANTIC_PROMPT_SCHEMA_VERSION

    normalized = {
        "schema_name": schema_name or "missing",
        "schema_version": schema_version or "missing",
        "valid": valid,
        "policy_role": str(slots.get("policy_role", "none") or "none"),
        "policy_interpretation": str(slots.get("policy_interpretation", "") or ""),
        "capital_quality": str(slots.get("capital_quality", "none") or "none"),
        "capital_interpretation": str(slots.get("capital_interpretation", "") or ""),
        "decision_summary": str(slots.get("decision_summary", "") or ""),
        "risk_flags": list(slots.get("risk_flags", []) or []),
        "trigger_reason": str(slots.get("trigger_reason", "") or ""),
        "strategy_sources": list(slots.get("strategy_sources", []) or []),
        "semantic_reason_payload": dict(slots.get("semantic_reason_payload", {}) or {}),
        "semantic_decision_reasons": list(slots.get("semantic_decision_reasons", []) or []),
        "semantic_priority": slots.get("semantic_priority", 0),
        "policy_strength": slots.get("policy_strength", 0),
        "policy_primary_concept_score": slots.get("policy_primary_concept_score", "N/A"),
        "policy_concept_competition_score": slots.get("policy_concept_competition_score", "N/A"),
        "policy_multi_concept_overlap_count": slots.get("policy_multi_concept_overlap_count", "N/A"),
        "policy_primary_concept_selection_summary": str(slots.get("policy_primary_concept_selection_summary", "") or ""),
        "capital_heat_quality_gap_score": slots.get("capital_heat_quality_gap_score", "N/A"),
        "capital_quality_weight": slots.get("capital_quality_weight", "N/A"),
        "capital_risk_constraint_score": slots.get("capital_risk_constraint_score", "N/A"),
        "capital_continuity_score": slots.get("capital_continuity_score", "N/A"),
        "technical_structure_risk_score": slots.get("technical_structure_risk_score", "N/A"),
        "technical_trend_consistency_score": slots.get("technical_trend_consistency_score", "N/A"),
        "technical_recent_extension_pct": slots.get("technical_recent_extension_pct", "N/A"),
        "technical_volume_confirmation_score": slots.get("technical_volume_confirmation_score", "N/A"),
        "technical_breakout_quality_score": slots.get("technical_breakout_quality_score", "N/A"),
        "technical_volume_price_divergence_score": slots.get("technical_volume_price_divergence_score", "N/A"),
    }
    if not valid:
        normalized["validation_warning"] = (
            f"semantic_prompt_slots schema mismatch: expected "
            f"{SEMANTIC_PROMPT_SCHEMA_NAME} v{SEMANTIC_PROMPT_SCHEMA_VERSION}, "
            f"got {normalized['schema_name']} v{normalized['schema_version']}"
        )
    return normalized


def derive_semantic_selected_analysts(
    requested_analysts: List[str],
    semantic_slots: Dict[str, Any] | None,
) -> List[str]:
    """Adjust analyst pipeline based on Screener semantics."""
    slots = validate_semantic_prompt_slots(semantic_slots)
    selected = list(requested_analysts)
    policy_role = slots.get("policy_role", "none")
    overlap_count = slots.get("policy_multi_concept_overlap_count", "N/A")
    heat_gap = slots.get("capital_heat_quality_gap_score", "N/A")

    if policy_role == "policy_top_stock":
        prioritized = ["news", "market", "social", "fundamentals"]
        selected = [name for name in prioritized if name in selected]
    elif policy_role == "policy_core_member":
        prioritized = ["news", "market", "fundamentals"]
        selected = [name for name in prioritized if name in selected]
    else:
        selected = list(requested_analysts)

    try:
        if int(overlap_count) >= 2 and "news" in selected:
            selected = ["news"] + [name for name in selected if name != "news"]
    except Exception:
        pass

    try:
        if float(heat_gap) >= 22 and "social" in selected:
            selected = [name for name in selected if name != "social"] + ["social"]
    except Exception:
        pass

    if not selected:
        return list(requested_analysts)
    return selected


def derive_semantic_flow_controls(semantic_slots: Dict[str, Any] | None) -> Dict[str, Any]:
    """Translate Screener semantics into graph-level routing controls."""
    slots = validate_semantic_prompt_slots(semantic_slots)
    policy_role = slots.get("policy_role", "none")
    capital_quality = slots.get("capital_quality", "none")
    overlap_count = slots.get("policy_multi_concept_overlap_count", "N/A")
    heat_gap = slots.get("capital_heat_quality_gap_score", "N/A")
    technical_divergence = slots.get("technical_volume_price_divergence_score", "N/A")

    controls = {
        "debate_round_limit": None,
        "risk_round_limit": None,
        "force_risk_review": False,
        "risk_hardening": False,
        "prompt_slot_mode": "structured_semantic_payload",
    }

    if capital_quality == "capital_quality_speculative":
        controls["debate_round_limit"] = 1
        controls["risk_round_limit"] = 2
        controls["force_risk_review"] = True
        controls["risk_hardening"] = True
    elif capital_quality in {"capital_quality_high", "capital_quality_persistent"}:
        controls["debate_round_limit"] = 2
        controls["risk_round_limit"] = 1

    if policy_role == "policy_top_stock":
        if controls["debate_round_limit"] is None:
            controls["debate_round_limit"] = 2
    elif policy_role == "policy_core_member":
        if controls["debate_round_limit"] is None:
            controls["debate_round_limit"] = 1

    try:
        if int(overlap_count) >= 2 and controls["debate_round_limit"] is not None:
            controls["debate_round_limit"] += 1
    except Exception:
        pass

    try:
        if float(heat_gap) >= 22:
            controls["force_risk_review"] = True
            controls["risk_hardening"] = True
            if controls["risk_round_limit"] is None:
                controls["risk_round_limit"] = 2
    except Exception:
        pass

    try:
        if float(technical_divergence) <= 42:
            controls["risk_hardening"] = True
    except Exception:
        pass

    return controls
