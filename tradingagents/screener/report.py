from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import json

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screener.models import DeepAnalysisResult, ScreeningResult
from tradingagents.dataflows.vendor_health import redact_error


def _extract_strategy_metric(card, strategy: str, key: str, default: Any = "N/A") -> Any:
    for evidence in card.signal_breakdown:
        if evidence.strategy == strategy:
            return (evidence.raw_metrics or {}).get(key, default)
    return default


def _policy_summary(card) -> str:
    tag = card.evidence_snapshot.get("policy_selection_tag", "none")
    concept = next((tag_name for tag_name in card.concept_tags if not str(tag_name).startswith("policy_") and not str(tag_name).startswith("capital_quality_")), "N/A")
    relative_rank = _extract_strategy_metric(card, "policy", "relative_rank_score")
    leadership = _extract_strategy_metric(card, "policy", "board_leadership_score")
    primary_concept_score = _extract_strategy_metric(card, "policy", "primary_concept_score")
    concept_competition_score = _extract_strategy_metric(card, "policy", "concept_competition_score")
    overlap_count = _extract_strategy_metric(card, "policy", "multi_concept_overlap_count")
    selection_summary = _extract_strategy_metric(card, "policy", "primary_concept_selection_summary")
    boundary = _extract_strategy_metric(card, "policy", "concept_linkage_boundary", {})
    linkage_mode = boundary.get("linkage_mode", "N/A") if isinstance(boundary, dict) else "N/A"
    confidence_tier = boundary.get("confidence_tier", "N/A") if isinstance(boundary, dict) else "N/A"
    return (
        f"{tag} | concept={concept} | relative_rank={relative_rank} | leadership={leadership} | "
        f"primary_concept={primary_concept_score} | competition={concept_competition_score} | "
        f"overlap={overlap_count} | linkage={linkage_mode} | boundary_confidence={confidence_tier} | "
        f"selection={selection_summary}"
    )


def _smart_money_summary(card) -> str:
    capital_tag = card.evidence_snapshot.get("capital_quality_tag", "none")
    persistence = _extract_strategy_metric(card, "smart_money", "multi_day_persistence_score")
    risk_constraint = _extract_strategy_metric(card, "smart_money", "risk_constraint_score")
    continuity = _extract_strategy_metric(card, "smart_money", "continuity_score")
    heat_quality_gap = _extract_strategy_metric(card, "smart_money", "heat_quality_gap_score")
    summary = card.evidence_snapshot.get("capital_quality_summary") or _extract_strategy_metric(
        card,
        "smart_money",
        "capital_quality_summary",
        "N/A",
    )
    return (
        f"{capital_tag} | persistence={persistence} | "
        f"risk_constraint={risk_constraint} | continuity={continuity} | heat_gap={heat_quality_gap} | summary={summary}"
    )


def _technical_structure_summary(card) -> str:
    structure_risk = _extract_strategy_metric(card, "technical", "structure_risk_score")
    consistency = _extract_strategy_metric(card, "technical", "trend_consistency_score")
    extension = _extract_strategy_metric(card, "technical", "recent_extension_pct")
    positive_days = _extract_strategy_metric(card, "technical", "positive_days_ratio_pct")
    volume_confirmation = _extract_strategy_metric(card, "technical", "volume_confirmation_score")
    breakout_quality = _extract_strategy_metric(card, "technical", "breakout_quality_score")
    volume_divergence = _extract_strategy_metric(card, "technical", "volume_price_divergence_score")
    summary = card.evidence_snapshot.get("technical_structure_summary", "N/A")
    return (
        f"structure_risk={structure_risk} | consistency={consistency} | "
        f"extension={extension} | positive_days={positive_days} | volume_confirmation={volume_confirmation} | "
        f"breakout_quality={breakout_quality} | volume_divergence={volume_divergence} | summary={summary}"
    )


def _render_retained_reason_card(card, retained_semantic_summaries: Dict[str, str]) -> List[str]:
    policy_summary = _policy_summary(card)
    smart_money_summary = _smart_money_summary(card)
    technical_summary = _technical_structure_summary(card)
    semantic_decision = retained_semantic_summaries.get(
        card.ticker,
        card.evidence_snapshot.get("semantic_decision_summary", "N/A"),
    )
    return [
        "- Retention Card:",
        f"  semantic_decision={semantic_decision}",
        f"  policy_reason_card={policy_summary}",
        f"  capital_reason_card={smart_money_summary}",
        f"  technical_reason_card={technical_summary}",
        f"  semantic_reason_payload={card.evidence_snapshot.get('semantic_reason_payload', {})}",
    ]


def _render_dropped_reason_card(item: Dict[str, Any], dropped_semantic_summaries: Dict[str, str]) -> List[str]:
    semantic_decision = item.get("semantic_decision_summary") or dropped_semantic_summaries.get(
        item.get("ticker", ""),
        "N/A",
    )
    reasons = ", ".join(item.get("reasons", [])) or "None"
    return [
        "- Drop Card:",
        f"  semantic_decision={semantic_decision}",
        f"  rule_reasons={reasons}",
        f"  policy_reason_card={item.get('policy_selection_tag', 'N/A')}",
        f"  capital_reason_card={item.get('capital_quality_tag', 'N/A')} | {item.get('capital_quality_summary', 'N/A')}",
        f"  technical_reason_card={item.get('technical_structure_summary', 'N/A')}",
        f"  semantic_reason_payload={item.get('semantic_reason_payload', {})}",
    ]


def _deep_route_summary(result: DeepAnalysisResult) -> str:
    summary = result.final_state_summary or {}
    route = summary.get("route_decision", {}) or {}
    graph_snapshot = summary.get("graph_config_snapshot", {}) or {}
    selected_analysts = route.get("selected_analysts", [])
    analyst_focus = route.get("analyst_focus", [])
    flow_controls = route.get("semantic_flow_controls", {})
    if not isinstance(flow_controls, dict):
        flow_controls = {}
    return (
        f"mode={summary.get('analysis_mode', 'unknown')} | "
        f"route_family={route.get('route_family', 'unknown')} | "
        f"policy_role={route.get('policy_role', 'none')} | "
        f"capital_quality={route.get('capital_quality', 'none')} | "
        f"conflict={route.get('conflict_tier', 'none')} | "
        f"analysts={selected_analysts} | "
        f"focus={analyst_focus} | "
        f"debate_rounds={route.get('debate_rounds', 'unknown')} | "
        f"risk_weight={route.get('debate_risk_weight', 'unknown')} | "
        f"fallback={summary.get('fallback_used', False)} | "
        f"schema={graph_snapshot.get('semantic_schema_name', 'missing')}@{graph_snapshot.get('semantic_schema_version', 'missing')}"
    )


def _render_trigger_route_card(result: DeepAnalysisResult) -> List[str]:
    summary = result.final_state_summary or {}
    route = dict(summary.get("route_decision", {}) or {})
    audit = dict(summary.get("semantic_trigger_audit", {}) or {})
    execution_profile = dict(summary.get("semantic_execution_profile", {}) or {})
    audit_trail = list(summary.get("semantic_route_audit_trail", []) or [])

    decision = (result.final_decision or "").strip()
    lines = [
        "- Trigger Route Card:",
        (
            "  "
            + f"trigger={audit.get('semantic_trigger_reasons', [])} | "
            + f"route={route.get('route_family', 'unknown')}|policy={route.get('policy_role', 'none')}|capital={route.get('capital_quality', 'none')}|conflict={route.get('conflict_tier', 'none')} | "
            + f"execution={execution_profile.get('route_behavior_tag', '')}|style={execution_profile.get('response_style', '')}|mode={execution_profile.get('conclusion_mode', '')} | "
            + f"decision={decision}"
        ),
    ]
    if audit_trail:
        lines.append("  semantic_route_audit_trail=")
        for item in audit_trail[:5]:
            lines.append(
                "    "
                + f"{item.get('node', 'unknown')} -> {item.get('route_reason', '') or item.get('route_rule', '')} "
                + f"| triggers={item.get('semantic_trigger_reasons', [])}"
            )
    return lines


def _resolve_output_dir(config: Dict[str, Any] | None = None) -> Path:
    config = config or DEFAULT_CONFIG
    # D盘项目目录 reports/Screener 作为首选
    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        project_root / "reports" / "Screener",
        Path(config.get("results_dir", DEFAULT_CONFIG["results_dir"])) / "screener",
        Path.cwd() / "reports" / "screener",
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    raise PermissionError("Unable to create a writable screener report directory")


def render_markdown_report(
    screening_result: ScreeningResult,
    deep_results: List[DeepAnalysisResult],
) -> str:
    capability_summary = screening_result.metrics.get("capability_summary", {})
    probe_results = capability_summary.get("probe_results", {})
    strategy_status = screening_result.strategy_status
    vendor_baseline = capability_summary.get("vendor_baseline", {})
    vendor_health = _sanitize_vendor_health(capability_summary.get("vendor_health", {}))
    strategy_capabilities = capability_summary.get("strategy_capabilities", {})
    universe_metadata = screening_result.universe_metadata or screening_result.metrics.get("universe_summary", {})
    retained_semantic_summaries = {card.ticker: card.evidence_snapshot.get("semantic_decision_summary", "") for card in screening_result.candidates}
    dropped_semantic_summaries = {item.get("ticker", f"dropped_{idx}"): item.get("semantic_decision_summary", "") for idx, item in enumerate(screening_result.dropped_candidates, 1)}
    retained_semantic_payloads = {card.ticker: card.evidence_snapshot.get("semantic_reason_payload", {}) for card in screening_result.candidates}
    dropped_semantic_payloads = {item.get("ticker", f"dropped_{idx}"): item.get("semantic_reason_payload", {}) for idx, item in enumerate(screening_result.dropped_candidates, 1)}

    lines = [
        "# Screener Report",
        f"- Run ID: {screening_result.run_id}",
        f"- Mode: {screening_result.mode}",
        f"- Trade Date: {screening_result.trade_date}",
        f"- Run Status: {screening_result.run_status}",
        f"- Universe Size: {screening_result.universe_size}",
        f"- Candidates: {len(screening_result.candidates)}",
        f"- Dropped Candidates: {len(screening_result.dropped_candidates)}",
        "",
        "## Funnel Summary",
    ]

    # P5-5: Add Stage A / Stage B funnel info
    stagea_audit = screening_result.metrics.get("effective_config_used", {}).get("stagea_audit", {})
    if stagea_audit:
        lines.extend([
            f"- Stage A Input: {stagea_audit.get('stagea_input_count', 'N/A')}",
            f"- Stage A Pass: {stagea_audit.get('stagea_pass_count', 'N/A')}",
            f"- Stage A Drop: {stagea_audit.get('stagea_drop_count', 'N/A')}",
            f"- Stage B Input: {stagea_audit.get('stageb_input_count', 'N/A')}",
            f"- Funnel Reduction: {stagea_audit.get('stagea_drop_count', 0) / max(stagea_audit.get('stagea_input_count', 1), 1) * 100:.1f}%" if stagea_audit.get('stagea_input_count', 0) > 0 else "- Funnel Reduction: N/A",
        ])
        drop_breakdown = stagea_audit.get("stagea_drop_breakdown", {})
        if drop_breakdown:
            lines.append("- Drop Breakdown:")
            for reason, count in drop_breakdown.items():
                lines.append(f"  - {reason}: {count}")
    else:
        lines.append("- Stage A: disabled")

    lines.extend(["", "## Data Issues"])
    if screening_result.data_issues:
        lines.extend([f"- {issue}" for issue in screening_result.data_issues])
    else:
        lines.append("- None")

    lines.extend(["", "## Universe Summary"])
    if universe_metadata:
        for key, value in universe_metadata.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- None")

    lines.extend(["", "## Strategy Status"])
    if strategy_status:
        for name, status in strategy_status.items():
            lines.append(f"- {name}: {status}")
    else:
        lines.append("- None")

    if strategy_status:
        lines.append("")
        lines.extend(["## Strategy Summary"])
        lines.append(
            f"- technical: {strategy_status.get('technical', 'N/A')}, "
            f"policy: {strategy_status.get('policy', 'N/A')}, "
            f"smart_money: {strategy_status.get('smart_money', 'N/A')}"
        )
    lines.extend(["", "## Semantic Home Chain"])
    home_chain = screening_result.metrics.get("semantic_home_chain", {}) or {}
    if home_chain:
        for ticker, payload in home_chain.items():
            route_decision = payload.get("route", {}) or {}
            execution_profile = payload.get("execution", {}) or {}
            trigger_reasons = payload.get("trigger", [])
            decision = payload.get("decision", "")
            lines.append(
                f"- {ticker}: trigger={trigger_reasons} | "
                + f"route={route_decision.get('route_family', 'unknown')}|policy={route_decision.get('policy_role', 'none')}|capital={route_decision.get('capital_quality', 'none')}|conflict={route_decision.get('conflict_tier', 'none')} | "
                + f"execution={execution_profile.get('route_behavior_tag', '')}|style={execution_profile.get('response_style', '')}|mode={execution_profile.get('conclusion_mode', '')} | "
                + f"decision={decision}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Capability Summary"])
    if capability_summary:
        lines.extend(
            [
                f"- akshare_importable: {capability_summary.get('akshare_importable')}",
                f"- fund_flow_bulk_verified: {capability_summary.get('fund_flow_bulk_verified')}",
                f"- concept_list_verified: {capability_summary.get('concept_list_verified')}",
                f"- hist_fetch_verified: {capability_summary.get('hist_fetch_verified')}",
                f"- tencent_hist_verified: {capability_summary.get('tencent_hist_verified')}",
                f"- yfinance_hist_verified: {capability_summary.get('yfinance_hist_verified')}",
                f"- fund_flow_fallback_vendor: {capability_summary.get('fund_flow_fallback_vendor', '') or 'None'}",
                f"- concept_list_fallback_vendor: {capability_summary.get('concept_list_fallback_vendor', '') or 'None'}",
                f"- hist_fetch_primary_vendor: {capability_summary.get('hist_fetch_primary_vendor', '') or 'None'}",
                f"- hist_fetch_secondary_vendor: {capability_summary.get('hist_fetch_secondary_vendor', '') or 'None'}",
                f"- hist_fetch_fallback_vendor: {capability_summary.get('hist_fetch_fallback_vendor', '') or 'None'}",
                f"- probed_at: {capability_summary.get('probed_at', 'N/A')}",
            ]
        )
    else:
        lines.append("- None")

    lines.extend(["", "## Vendor Baseline"])
    if vendor_baseline:
        for module, mapping in vendor_baseline.items():
            lines.append(f"### {module}")
            if isinstance(mapping, dict):
                for key, value in mapping.items():
                    lines.append(f"- {key}: {value or 'None'}")
            else:
                lines.append(f"- value: {mapping}")
            lines.append("")
    else:
        lines.append("- None")

    lines.extend(["", "## 供应商健康状态"])
    if vendor_health:
        for name, item in vendor_health.items():
            lines.append(
                f"- {name}: calls={item.get('calls', 0)}, failures={item.get('failures', 0)}, "
                f"failure_rate={float(item.get('failure_rate', 0)) * 100:.1f}%, "
                f"avg_seconds={item.get('avg_seconds', 0)}, last_status={item.get('last_status', 'unknown')}"
            )
            if item.get("last_error"):
                lines.append(f"  - last_error: {item['last_error']}")
    else:
        lines.append("- None")

    lines.extend(["## Strategy Capabilities"])
    if strategy_capabilities:
        for strategy, payload in strategy_capabilities.items():
            lines.append(f"### {strategy}")
            if isinstance(payload, dict):
                for key, value in payload.items():
                    lines.append(f"- {key}: {value}")
            else:
                lines.append(f"- value: {payload}")
            lines.append("")
    else:
        lines.append("- None")

    lines.extend(["", "## Probe Results"])
    if probe_results:
        for name, result in probe_results.items():
            lines.extend(
                [
                    f"### {name}",
                    f"- ok: {result.get('ok')}",
                    f"- classification: {result.get('classification', 'N/A')}",
                    f"- detail: {result.get('detail', 'N/A')}",
                    "",
                ]
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Candidates"])
    for idx, card in enumerate(screening_result.candidates, 1):
        lines.extend(
            [
                f"### #{idx} {card.ticker} {card.company_name}",
                f"- Score: {card.screening_score:.1f}",
                f"- Confidence: {card.initial_confidence:.1f}",
                f"- Sources: {', '.join(card.strategy_sources)}",
                f"- Trigger: {card.trigger_reason}",
                f"- Risks: {', '.join(card.risk_flags) if card.risk_flags else 'None'}",
                f"- Verified: {card.data_source_verified}",
                f"- 正式推荐资格: {card.recommendation_eligible}",
                f"- 已验证模块: {', '.join(card.verified_modules) if card.verified_modules else 'None'}",
                f"- 缺失必需模块: {', '.join(card.missing_required_modules) if card.missing_required_modules else 'None'}",
                f"- 降级模块: {', '.join(card.degraded_modules) if card.degraded_modules else 'None'}",
                f"- 关键数据最旧日期: {card.latest_required_data_date or 'N/A'}",
                f"- 关键数据最大滞后: {card.max_required_data_lag_days if card.max_required_data_lag_days is not None else 'N/A'} 天",
                f"- 过期关键来源: {', '.join(card.stale_required_sources) if card.stale_required_sources else 'None'}",
                f"- Semantic Decision: {retained_semantic_summaries.get(card.ticker, card.evidence_snapshot.get('semantic_decision_summary', 'N/A'))}",
                f"- Policy Selection: {_policy_summary(card)}",
                f"- Smart Money Quality: {_smart_money_summary(card)}",
                f"- Technical Structure: {_technical_structure_summary(card)}",
                f"- Semantic Payload: {retained_semantic_payloads.get(card.ticker, card.evidence_snapshot.get('semantic_reason_payload', {}))}",
            ]
        )
        lines.extend(_render_retained_reason_card(card, retained_semantic_summaries))
        lines.append("")

    lines.extend(["## Dropped Candidates"])
    if screening_result.dropped_candidates:
        for item in screening_result.dropped_candidates:
            lines.extend(
                [
                    f"### {item.get('ticker', 'N/A')} {item.get('company_name', '')}".rstrip(),
                    f"- Stage: {item.get('stage', 'unknown')}",
                    f"- Reasons: {', '.join(item.get('reasons', [])) or 'None'}",
                    f"- Semantic Decision: {item.get('semantic_decision_summary') or dropped_semantic_summaries.get(item.get('ticker', ''), 'N/A')}",
                    f"- Policy Selection: {item.get('policy_selection_tag', 'N/A')}",
                    f"- Smart Money Quality: {item.get('capital_quality_tag', 'N/A')}",
                    f"- Technical Structure: {item.get('technical_structure_summary', 'N/A')}",
                    f"- Semantic Payload: {dropped_semantic_payloads.get(item.get('ticker', ''), item.get('semantic_reason_payload', {}))}",
                ]
            )
            lines.extend(_render_dropped_reason_card(item, dropped_semantic_summaries))
            lines.append("")
    else:
        lines.append("- None")

    lines.append("## Deep Analysis")
    if deep_results:
        for result in deep_results:
            lines.extend(
                [
                    f"### {result.signal_card.ticker}",
                    f"- Success: {result.success}",
                    f"- Execution Status: {result.execution_status}",
                    f"- Decision: {result.final_decision or 'N/A'}",
                    f"- Mode: {result.final_state_summary.get('analysis_mode', 'unknown')}",
                    f"- Semantic Context: {result.final_state_summary.get('semantic_context_summary', 'N/A')}",
                    f"- Prompt Slots: {result.final_state_summary.get('semantic_prompt_slots', {})}",
                    f"- Route Summary: {_deep_route_summary(result)}",
                ]
            )
            lines.extend(_render_trigger_route_card(result))
            lines.append("")
    else:
        lines.append("- Not executed")

    return "\n".join(lines).rstrip() + "\n"


def write_run_artifacts(
    screening_result: ScreeningResult,
    deep_results: List[DeepAnalysisResult],
    config: Dict[str, Any] | None = None,
) -> Dict[str, str]:
    output_dir = _resolve_output_dir(config)
    run_dir = output_dir / screening_result.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    json_path = run_dir / "screening_result.json"
    md_path = run_dir / "daily_gold_stocks_report.md"
    vendor_health_path = run_dir / "vendor_health.json"

    payload = screening_result.model_dump()
    capability_summary = payload.get("metrics", {}).get("capability_summary", {})
    vendor_health = _sanitize_vendor_health(capability_summary.get("vendor_health", {}))
    capability_summary["vendor_health"] = vendor_health
    payload["deep_analysis_results"] = [result.model_dump() for result in deep_results]
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(screening_result, deep_results), encoding="utf-8")
    vendor_health_path.write_text(
        json.dumps(vendor_health, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "vendor_health": str(vendor_health_path),
    }


def _sanitize_vendor_health(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for name, raw_item in (snapshot or {}).items():
        item = dict(raw_item or {})
        item["last_error"] = redact_error(item.get("last_error", ""))
        sanitized[str(name)] = item
    return sanitized
