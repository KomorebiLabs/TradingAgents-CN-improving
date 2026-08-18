"""Instrument classification: ticker -> market/segment/style/skills profile."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from tradingagents.dataflows.config import get_config

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
