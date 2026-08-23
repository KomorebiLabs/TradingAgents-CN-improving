"""A4: Evidence Verifier — zero-LLM numeric claim verification.

Checks numeric assertions in analyst reports against the raw data returned
by tools (ToolMessages in state). Guards against the three verifier traps
(the failure mode worse than no verification: certifying wrong numbers):

1. Unit drift    — "150 亿" must not match a tool "150 万": all currency
                   values normalize to yuan before comparison, and currency
                   never matches percent/multiples (dimension lock).
2. Semantic drift— "毛利率 85%" must not match an unrelated 85: the evidence
                   sentence must contain a keyword from the claim's metric
                   family (synonym table).
3. Claim types   — point values compare within ±1%; ranges require the tool
                   value INSIDE them; growth/threshold claims are unverified
                   in v1 (no dual-period evidence reconstruction).

Levels: ``verified`` (anchor + dimension + value all match) / ``unverified``
(anything else). Ambiguity ALWAYS degrades to unverified — a false verified
is far more dangerous than a false unverified (asymmetric cost rule).
Derived arithmetic (PE = price / EPS) is deliberately out of v1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import ToolMessage

# metric family -> (dimension, synonyms); order of synonyms is the family key
_METRIC_FAMILIES: Dict[str, Tuple[str, List[str]]] = {
    "net_income": ("currency", ["净利润", "归母净利润", "net income", "net profit"]),
    "revenue": ("currency", ["营收", "营业收入", "revenue"]),
    "gross_margin": ("percent", ["毛利率", "gross margin"]),
    "debt_ratio": ("percent", ["资产负债率", "debt ratio", "负债率"]),
    "pe": ("multiple", ["市盈率", "PE", "P/E"]),
    "pb": ("multiple", ["市净率", "PB", "P/B"]),
    "price": ("currency", ["股价", "批价", "收盘价", "现价", "price"]),
}

_DIMENSION_UNITS = {
    "currency": ("元", "万元", "亿", "亿", "万", "美元", "人民币"),
    "percent": ("%",),
    "multiple": ("倍",),
}

_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(亿|万|千万)?\s*(元|%|倍|美元)?")
_THRESHOLD_RE = re.compile(r"(未跌破|不低于|高于|大于|守住|未突破|未站上|低于|小于)\s*(\d+(?:\.\d+)?)\s*(亿|万)?\s*(元|%)?")
_RANGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:亿|万)?\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*(亿|万)?\s*(元|%)?")

# growth/threshold words that mark a claim as unverifiable in v1
_GROWTH_WORDS = ("同比", "环比", "增长", "下降", "涨幅", "跌幅", "yoy", "mom")


@dataclass
class Claim:
    sentence: str
    report_key: str
    family: str
    dimension: str
    value: Optional[float] = None          # point value, normalized
    value_range: Optional[Tuple[float, float]] = None
    raw: str = ""
    level: str = "unverified"
    evidence: str = ""
    usd: bool = False  # currency claim in USD: never verified in v1 (no FX table)
    direction: Optional[str] = None  # threshold claims: '>=' or '<=' (directional check)


@dataclass
class VerificationResult:
    claims_total: int = 0
    verified: int = 0
    unverified: int = 0
    warnings: List[str] = field(default_factory=list)

    def summary_markdown(self) -> str:
        pct = f"{self.verified / self.claims_total:.0%}" if self.claims_total else "n/a"
        lines = [
            "## Evidence Verification Summary",
            "",
            f"- Numeric claims checked: **{self.claims_total}**",
            f"- Verified against tool data: **{self.verified}** ({pct})",
            f"- Unverified (no matching tool evidence): **{self.unverified}**",
        ]
        if self.warnings:
            lines.append("")
            lines.append("Top unverified claims:")
            for w in self.warnings:
                lines.append(f"- {w}")
        return "\n".join(lines)


def _norm_currency(value: float, unit: Optional[str], scale: Optional[str]) -> Optional[float]:
    """Normalize a currency figure to yuan. Returns None for unknown units
    (never guess — ambiguity degrades the claim, per the asymmetric rule)."""
    if unit == "美元":
        return None  # v1: no FX table; cross-currency comparison is unsafe
    v = value
    if scale == "亿":
        v *= 1e8
    elif scale == "千万":
        v *= 1e7
    elif scale == "万":
        v *= 1e4
    return v


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[。；;.!?\n])", text)
    return [p.strip() for p in parts if p.strip()]


def _family_for(sentence: str) -> Optional[str]:
    low = sentence.lower()
    best: Optional[str] = None
    best_len = 0
    for fam, (_dim, synonyms) in _METRIC_FAMILIES.items():
        for syn in synonyms:
            if syn.lower() in low and len(syn) > best_len:
                best, best_len = fam, len(syn)
    return best


def extract_claims(report_text: str, report_key: str) -> List[Claim]:
    """Sentence-level claim extraction (sentences, not lines — tables and
    wrapped lines must not break positioning)."""
    claims: List[Claim] = []
    for sentence in _split_sentences(report_text):
        if any(w in sentence for w in _GROWTH_WORDS):
            # growth claims need both periods' data: v1 marks nothing yet —
            # they are simply not extracted as verifiable point claims
            continue
        family = _family_for(sentence)
        if family is None:
            continue
        dimension = _METRIC_FAMILIES[family][0]
        thr = _THRESHOLD_RE.search(sentence)
        if thr:
            ge_words = ("未跌破", "不低于", "高于", "大于", "守住")
            direction = ">=" if thr.group(1) in ge_words else "<="
            tval = float(thr.group(2))
            scale, unit = thr.group(3), thr.group(4)
            if dimension == "percent":
                val = tval if unit == "%" else None
            else:
                val = _norm_currency(tval, unit if unit in (None, "元") else unit, scale)
            if val is not None:
                claims.append(Claim(sentence=sentence, report_key=report_key,
                                    family=family, dimension=dimension,
                                    value=val, raw=thr.group(0), direction=direction))
                continue
        rng = _RANGE_RE.search(sentence)
        if rng:
            scale = rng.group(3) or ""
            unit = rng.group(4)
            lo = _norm_currency(float(rng.group(1)), unit, scale)
            hi = _norm_currency(float(rng.group(2)), unit, scale)
            if dimension == "percent":
                lo, hi = float(rng.group(1)), float(rng.group(2))
            if lo is not None and hi is not None and hi >= lo:
                claims.append(Claim(
                    sentence=sentence, report_key=report_key, family=family,
                    dimension=dimension, value_range=(lo, hi), raw=rng.group(0),
                ))
                continue
        m = None
        # pick the first number WITH a currency scale/unit — bare numbers in
        # a sentence are usually years/counts ("2026年Q2净利润为 150 亿元")
        for cand in _NUM_RE.finditer(sentence):
            if cand.group(2) or cand.group(3):
                m = cand
                break
        if m is None:
            continue
        value = float(m.group(1))
        scale, unit = m.group(2), m.group(3)
        if dimension == "percent":
            if unit == "%":
                claims.append(Claim(sentence=sentence, report_key=report_key,
                                    family=family, dimension=dimension,
                                    value=value, raw=m.group(0)))
        elif dimension == "multiple":
            if unit == "倍" or unit is None:  # "PE 30" is conventionally a multiple
                claims.append(Claim(sentence=sentence, report_key=report_key,
                                    family=family, dimension=dimension,
                                    value=value, raw=m.group(0)))
        else:  # currency
            if unit == "美元":
                # extracted but never verified in v1 (no FX table — cross
                # currency comparison is unsafe; ambiguity degrades, never upgrades)
                claims.append(Claim(sentence=sentence, report_key=report_key,
                                    family=family, dimension=dimension,
                                    value=value, raw=m.group(0), usd=True))
            elif unit in (None, "元") or scale in ("亿", "万", "千万"):
                norm = _norm_currency(value, unit, scale)
                if norm is not None:
                    claims.append(Claim(sentence=sentence, report_key=report_key,
                                        family=family, dimension=dimension,
                                        value=norm, raw=m.group(0)))
    return claims


def _tool_evidence_sentences(messages: List[Any]) -> List[Tuple[str, str]]:
    """(sentence, tool_name) pairs from raw tool outputs."""
    out: List[Tuple[str, str]] = []
    for message in messages or []:
        if not isinstance(message, ToolMessage):
            continue
        content = str(getattr(message, "content", "") or "")
        tool = str(getattr(message, "name", "tool"))
        for s in _split_sentences(content):
            out.append((s, tool))
    return out


def verify_claim(claim: Claim, evidence: List[Tuple[str, str]]) -> Claim:
    """Anchor + dimension + value matching against tool evidence sentences."""
    if claim.usd:
        return claim  # no FX table in v1: USD stays unverified by definition
    synonyms = _METRIC_FAMILIES[claim.family][1]
    for sentence, _tool in evidence:
        # semantic anchor: evidence sentence must mention the metric family
        if not any(syn.lower() in sentence.lower() for syn in synonyms):
            continue
        if claim.direction is not None:
            for m in _NUM_RE.finditer(sentence):
                raw = float(m.group(1))
                scale, unit = m.group(2), m.group(3)
                if claim.dimension == "percent":
                    if m.group(3) != "%":
                        continue
                    val = raw
                elif claim.dimension == "multiple":
                    val = raw if m.group(3) in (None, "倍") else None
                else:
                    if not (scale or unit):
                        continue
                    val = _norm_currency(raw, unit, scale)
                if val is None:
                    continue
                ok = val >= claim.value if claim.direction == ">=" else val <= claim.value
                if ok:
                    claim.level, claim.evidence = "verified", sentence
                    return claim
            return claim
        if claim.value_range is not None:
            m = _NUM_RE.search(sentence)
            if not m:
                continue
            raw = float(m.group(1))
            scale, unit = m.group(2), m.group(3)
            if claim.dimension == "percent":
                val = raw if m.group(3) == "%" else None
            else:
                val = _norm_currency(raw, unit, scale)
            if val is None:
                continue
            lo, hi = claim.value_range
            if lo <= val <= hi:
                claim.level, claim.evidence = "verified", sentence
                return claim
        else:
            for m in _NUM_RE.finditer(sentence):
                raw = float(m.group(1))
                scale, unit = m.group(2), m.group(3)
                if claim.dimension == "percent":
                    if m.group(3) != "%":
                        continue
                    val = raw
                elif claim.dimension == "multiple":
                    val = raw if m.group(3) in (None, "倍") else None
                else:
                    if not (scale or unit):
                        continue  # bare number (likely a year/count): unsafe evidence
                    val = _norm_currency(raw, unit, scale)
                if val is None:
                    continue
                if abs(val - claim.value) <= max(abs(claim.value) * 0.01, 1e-9):
                    claim.level, claim.evidence = "verified", sentence
                    return claim
    return claim


def annotate_report(report_text: str, claims: List[Claim]) -> str:
    """Insert level markers after each claimed sentence (sentence-level, so
    tables/newlines don't break positioning). First occurrence per sentence."""
    annotated = report_text
    for claim in claims:
        marker = f" [{claim.level}]"
        if claim.sentence + marker not in annotated and claim.sentence in annotated:
            annotated = annotated.replace(claim.sentence, claim.sentence + marker, 1)
    return annotated


MAX_WARNINGS = 20  # state bloat guard: warnings cap feeds compression budget


def run_verification(state: Dict[str, Any], report_keys=("market", "social", "news", "fundamentals")) -> Dict[str, Any]:
    """Full pipeline: extract -> verify -> annotate -> summarize.

    Returns the state update dict for the Evidence Verifier node:
    annotated analyst_reports + a verification summary block (warnings capped).
    """
    reports_block = dict(state.get("analyst_reports") or {})
    evidence = _tool_evidence_sentences(state.get("messages", []))

    result = VerificationResult()
    annotated_block: Dict[str, str] = {}
    for key in report_keys:
        text = reports_block.get(key) or state.get(
            {"market": "market_report", "social": "sentiment_report",
             "news": "news_report", "fundamentals": "fundamentals_report"}.get(key, ""),
            "",
        ) or ""
        if not text:
            continue
        claims = [verify_claim(c, evidence) for c in extract_claims(text, key)]
        result.claims_total += len(claims)
        for c in claims:
            if c.level == "verified":
                result.verified += 1
            else:
                result.unverified += 1
                if len(result.warnings) < MAX_WARNINGS:
                    result.warnings.append(
                        f"[{key}] {c.sentence[:120]}"
                    )
        annotated_block[key] = annotate_report(text, claims)

    update: Dict[str, Any] = {
        "verification": {
            "claims_total": result.claims_total,
            "verified": result.verified,
            "unverified": result.unverified,
            "warnings": result.warnings,
            "summary": result.summary_markdown(),
        },
        "sender": "Evidence Verifier",
    }
    if annotated_block:
        merged = dict(reports_block)
        merged.update(annotated_block)
        update["analyst_reports"] = merged
    return update
