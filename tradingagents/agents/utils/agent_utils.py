try:  # pragma: no cover - optional runtime dependency
    from langchain_core.messages import HumanMessage, RemoveMessage
except Exception:  # pragma: no cover
    class HumanMessage:
        def __init__(self, content: str):
            self.content = content

    class RemoveMessage:
        def __init__(self, id=None):
            self.id = id
from dataclasses import asdict
from typing import Any, Dict, List

from tradingagents.dataflows.config import get_config


def _lazy_tool_imports():
    from tradingagents.agents.utils.core_stock_tools import get_stock_data
    from tradingagents.agents.utils.technical_indicators_tools import get_indicators
    from tradingagents.agents.utils.fundamental_data_tools import (
        get_fundamentals,
        get_balance_sheet,
        get_cashflow,
        get_income_statement,
    )
    from tradingagents.agents.utils.news_data_tools import (
        get_cn_market_flow,
        get_cn_policy_news,
        get_news,
        get_insider_transactions,
        get_global_news,
    )
    from tradingagents.agents.utils.cn_sector_news_tools import (
        get_cn_tech_sector_news,
        get_cn_new_energy_news,
        get_cn_pharma_news,
        get_cn_real_estate_news,
        get_cn_fintech_news,
        get_sector_tools_for_ticker,
    )
    from tradingagents.agents.utils.cn_macro_tools import (
        get_cn_macro_data,
        get_cn_rate_outlook,
        get_cn_trade_data,
        should_mount_macro_tools,
    )

    return {
        "get_stock_data": get_stock_data,
        "get_indicators": get_indicators,
        "get_fundamentals": get_fundamentals,
        "get_balance_sheet": get_balance_sheet,
        "get_cashflow": get_cashflow,
        "get_income_statement": get_income_statement,
        "get_cn_market_flow": get_cn_market_flow,
        "get_cn_policy_news": get_cn_policy_news,
        "get_news": get_news,
        "get_insider_transactions": get_insider_transactions,
        "get_global_news": get_global_news,
        "get_cn_tech_sector_news": get_cn_tech_sector_news,
        "get_cn_new_energy_news": get_cn_new_energy_news,
        "get_cn_pharma_news": get_cn_pharma_news,
        "get_cn_real_estate_news": get_cn_real_estate_news,
        "get_cn_fintech_news": get_cn_fintech_news,
        "get_sector_tools_for_ticker": get_sector_tools_for_ticker,
        "get_cn_macro_data": get_cn_macro_data,
        "get_cn_rate_outlook": get_cn_rate_outlook,
        "get_cn_trade_data": get_cn_trade_data,
        "should_mount_macro_tools": should_mount_macro_tools,
    }

SEMANTIC_PROMPT_SCHEMA_NAME = "screener.semantic_prompt_slots"
SEMANTIC_PROMPT_SCHEMA_VERSION = "1.0"


ANALYST_TOOLSETS: Dict[str, List] = {}


SKILL_INSTRUMENT_NOTES: Dict[str, str] = {
    "chinext_growth_board": "This is a ChiNext growth-board listing. Expect higher volatility, stronger momentum swings, and tighter drawdown discipline.",
    "star_market_policy": "This is a STAR Market listing. Pay extra attention to technology-policy sensitivity, R&D narrative risk, and event-driven repricing.",
    "bse_liquidity_watch": "This is a Beijing Stock Exchange listing. Treat liquidity, slippage, and abrupt volume changes as first-class constraints.",
    "dividend_factor_focus": "This instrument fits a dividend-style candidate bucket. Check cash-flow resilience, payout sustainability, and defensive positioning.",
    "growth_factor_focus": "This instrument fits a growth-style candidate bucket. Focus on growth durability, valuation sensitivity, and sentiment-driven volatility.",
}


def _is_cn_equity_symbol(ticker: str) -> bool:
    if not ticker:
        return False

    value = ticker.strip().upper()
    if "." in value:
        _, exchange = value.split(".", 1)
        return exchange in {"SH", "SZ", "BJ", "XSHG", "XSHE", "BSE"}

    return value[:1] in {"0", "2", "3", "4", "6", "8", "9"} and value.isdigit()


def _extract_symbol_code(ticker: str) -> str:
    value = (ticker or "").strip().upper()
    if "." in value:
        code, _ = value.split(".", 1)
        return code
    return value


def _classify_cn_equity_segment(ticker: str, exchange: str) -> str:
    code = _extract_symbol_code(ticker)

    if exchange in {"BJ", "BSE"} or code.startswith(("4", "8")):
        return "cn_bse_equity"
    if exchange in {"SH", "XSHG"} and code.startswith("688"):
        return "cn_star_equity"
    if exchange in {"SZ", "XSHE"} and code.startswith("300"):
        return "cn_chinext_equity"
    return "cn_main_board_equity"


def _classify_style_bucket(ticker: str) -> str:
    code = _extract_symbol_code(ticker)
    if code.startswith(("600", "601", "603", "605", "000")):
        return "dividend_style_candidate"
    if code.startswith(("300", "688")):
        return "growth_style_candidate"
    return ""


def build_instrument_profile(ticker: str, config: Dict | None = None) -> Dict[str, Any]:
    config = config or get_config()
    value = (ticker or "").strip().upper()
    exchange = ""
    if "." in value:
        _, exchange = value.split(".", 1)

    is_cn_equity = _is_cn_equity_symbol(value)
    market = "cn_equity" if is_cn_equity else "global_equity"
    segment = ""
    style = ""
    if is_cn_equity:
        segment = _classify_cn_equity_segment(value, exchange)
        style = _classify_style_bucket(value)

    skill_rules = config.get("instrument_skill_rules", {})
    skills = list(skill_rules.get(market, []))
    if segment:
        for skill in skill_rules.get(segment, []):
            if skill not in skills:
                skills.append(skill)
    if style:
        for skill in skill_rules.get(style, []):
            if skill not in skills:
                skills.append(skill)
    if market == "global_equity":
        if exchange in {"NASDAQ", "NYSE", "AMEX"} or exchange == "":
            skills = list(skill_rules.get("us_equity", skills))

    return {
        "symbol": ticker,
        "market": market,
        "exchange": exchange or ("SHSZBJ" if is_cn_equity else ""),
        "is_cn_equity": is_cn_equity,
        "segment": segment,
        "style_bucket": style,
        "skills": skills,
    }


def _config_prefers_vendor(config: Dict, category: str, methods: List[str], vendor: str) -> bool:
    tool_vendors = config.get("tool_vendors", {})
    for method in methods:
        configured = tool_vendors.get(method)
        if configured and vendor in [item.strip() for item in configured.split(",")]:
            return True

    category_vendor = config.get("data_vendors", {}).get(category, "")
    return vendor in [item.strip() for item in category_vendor.split(",")]


def get_segment_constraints(ticker: str, config: Dict | None = None) -> List[str]:
    profile = build_instrument_profile(ticker, config)
    constraints: List[str] = []

    if profile["segment"] == "cn_chinext_equity":
        constraints.append(
            "Prefer shorter-horizon and volatility-aware interpretations; avoid presenting slow, balance-sheet-heavy conclusions as sufficient on their own."
        )
    elif profile["segment"] == "cn_star_equity":
        constraints.append(
            "Treat policy/news catalysts as material drivers and explicitly discuss event risk around technology and innovation narratives."
        )
    elif profile["segment"] == "cn_bse_equity":
        constraints.append(
            "Explicitly account for lower liquidity risk and execution fragility; do not overstate confidence from sparse data."
        )

    return constraints


def get_segment_advisory(ticker: str, audience: str, config: Dict | None = None) -> str:
    profile = build_instrument_profile(ticker, config)
    notes: List[str] = []

    if audience == "market":
        if profile["segment"] == "cn_chinext_equity":
            notes.append(
                "For this ChiNext listing, emphasize volatility clusters, momentum reversal risk, and stop-loss discipline."
            )
        elif profile["segment"] == "cn_bse_equity":
            notes.append(
                "For this Beijing Stock Exchange listing, avoid overconfident technical read-through from thin trading windows."
            )
    elif audience == "news":
        if profile["segment"] == "cn_star_equity":
            notes.append(
                "For this STAR Market listing, prioritize policy, regulation, subsidy, and technology-cycle catalysts in the news narrative."
            )
        elif profile["segment"] == "cn_chinext_equity":
            notes.append(
                "For this ChiNext listing, highlight sentiment swings and event-driven repricing risk in recent news."
            )
    elif audience == "risk":
        if profile["segment"] == "cn_bse_equity":
            notes.append(
                "Apply conservative sizing and execution assumptions because liquidity may deteriorate abruptly."
            )
        elif profile["segment"] in {"cn_chinext_equity", "cn_star_equity"}:
            notes.append(
                "Stress-test drawdown tolerance and avoid overstating conviction when valuation and sentiment can re-rate quickly."
            )

    return " ".join(notes)


def get_tools_for_analyst(analyst_type: str, ticker: str = "", config: Dict = None) -> List:
    lazy = _lazy_tool_imports()
    if not ANALYST_TOOLSETS:
        ANALYST_TOOLSETS.update(
            {
                "market": [lazy["get_stock_data"], lazy["get_indicators"]],
                "social": [lazy["get_news"]],
                "news": [lazy["get_news"], lazy["get_global_news"], lazy["get_insider_transactions"], lazy["get_cn_policy_news"]],
                "fundamentals": [lazy["get_fundamentals"], lazy["get_balance_sheet"], lazy["get_cashflow"], lazy["get_income_statement"]],
            }
        )
    tools = list(ANALYST_TOOLSETS[analyst_type])
    config = config or get_config()
    instrument_profile = build_instrument_profile(ticker, config)
    skills = set(instrument_profile.get("skills", []))

    if analyst_type == "news" and "cn_macro_news" not in skills and instrument_profile["is_cn_equity"]:
        tools = [tool for tool in tools if tool.name != "get_global_news"]
    if analyst_type == "news":
        if instrument_profile["segment"] in {"cn_star_equity", "cn_chinext_equity"}:
            if all(tool.name != "get_cn_policy_news" for tool in tools):
                tools.append(lazy["get_cn_policy_news"])
        else:
            tools = [tool for tool in tools if tool.name != "get_cn_policy_news"]

    # ========================================
    # Sector-specific tools mounting (L2 深化)
    # ========================================
    if analyst_type == "news" and instrument_profile["is_cn_equity"]:
        # Get sector tools based on ticker segment/industry
        sector_tools = lazy["get_sector_tools_for_ticker"](ticker)

        for sector_tool in sector_tools:
            # Only add if not already present
            if all(tool.name != sector_tool.name for tool in tools):
                tools.append(sector_tool)

        # Mount macro tools if skill is enabled
        if lazy["should_mount_macro_tools"](list(skills)):
            macro_tools = [lazy["get_cn_macro_data"], lazy["get_cn_rate_outlook"], lazy["get_cn_trade_data"]]
            for macro_tool in macro_tools:
                if all(tool.name != macro_tool.name for tool in tools):
                    tools.append(macro_tool)

    if analyst_type == "fundamentals" and instrument_profile["segment"] in {"cn_chinext_equity", "cn_star_equity", "cn_bse_equity"}:
        tools = [tool for tool in tools if tool.name != "get_income_statement"]

    if analyst_type == "market":
        if instrument_profile["segment"] == "cn_bse_equity":
            tools = [tool for tool in tools if tool.name != "get_indicators"]
        if instrument_profile["segment"] == "cn_bse_equity" or "growth_factor_focus" in skills:
            if all(tool.name != "get_cn_market_flow" for tool in tools):
                tools.append(lazy["get_cn_market_flow"])
        else:
            tools = [tool for tool in tools if tool.name != "get_cn_market_flow"]

    if (
        analyst_type == "fundamentals"
        and instrument_profile["is_cn_equity"]
        and _config_prefers_vendor(config, "fundamental_data", ["get_fundamentals"], "akshare")
    ):
        # CN fundamentals currently have a pruned AkShare company snapshot only.
        return [lazy["get_fundamentals"]]

    return tools


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


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    profile = build_instrument_profile(ticker)
    lines = [
        f"The instrument to analyze is `{ticker}`.",
        "Use this exact ticker in every tool call, report, and recommendation, preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`).",
        f"Market profile: market={profile['market']}, exchange={profile['exchange'] or 'N/A'}, segment={profile['segment'] or 'N/A'}, style_bucket={profile['style_bucket'] or 'N/A'}.",
    ]

    for skill in profile.get("skills", []):
        note = SKILL_INSTRUMENT_NOTES.get(skill)
        if note:
            lines.append(note)

    return " ".join(lines)


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


def enforce_execution_profile_output(content: str, execution_profile: Dict[str, Any]) -> str:
    rendered = str(content or "")
    must_include = list(execution_profile.get("evidence_must_include", []) or [])
    conclusion_mode = str(execution_profile.get("conclusion_mode", "standard") or "standard")
    missing_evidence = [
        item for item in must_include if str(item).lower() not in rendered.lower()
    ]

    template_checks: List[str] = []
    if conclusion_mode == "risk_first":
        if "risk" not in rendered.lower():
            template_checks.append("missing_risk_section")
    elif conclusion_mode == "leader_continuation_vs_failure":
        if "continuation" not in rendered.lower():
            template_checks.append("missing_continuation_section")
        if "failure" not in rendered.lower() and "invalidation" not in rendered.lower():
            template_checks.append("missing_failure_or_invalidation_section")
    elif conclusion_mode == "member_quality_confirmation":
        if "quality" not in rendered.lower():
            template_checks.append("missing_quality_section")

    if missing_evidence:
        rendered += (
            f"\n\n[execution_profile_evidence_check] missing={missing_evidence}"
        )
    if template_checks:
        rendered += (
            f"\n\n[execution_profile_structure_check] mode={conclusion_mode} missing={template_checks}"
        )
    return rendered


def enforce_skill_usage(
    content: str,
    injected_skill_names: List[str],
    node_name: str,
    decision_type: str,
    debate_round: int,
    is_counter_round: bool,
    is_adjudication: bool,
) -> dict:
    """Verify LLM response skill usage declarations and build audit record.

    If LLM declares no skills, append a reminder to content (does not modify existing content).
    Returns dict with updated content and audit_entry for AgentState writing.
    """
    from tradingagents.harness.skills.audit import build_skill_audit_entry

    entry = build_skill_audit_entry(
        node_name=node_name,
        decision_type=decision_type,
        debate_round=debate_round,
        is_counter_round=is_counter_round,
        is_adjudication=is_adjudication,
        injected_skill_names=injected_skill_names,
        response_content=content,
    )

    result_content = content
    if entry.declared_skills and entry.declared_skills[0].skill_name == "(none)":
        result_content = content.rstrip() + (
            "\n\n[skill_usage_reminder] No skills were declared. "
            "Consider if any of these were applicable: "
            + ", ".join(injected_skill_names[:5])
        )

    return {
        "content": result_content,
        "audit_entry": asdict(entry),
    }


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

def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        
