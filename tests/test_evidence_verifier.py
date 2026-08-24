"""A4: evidence verifier — the three-trap test matrix.

Trap coverage (each must produce ZERO false-verified):
1. unit drift       — 150 亿 claim vs 150 万 tool value
2. semantic drift   — 毛利率 85% claim vs 资产负债率 85% tool value
3. claim typing     — ranges need containment; growth claims skipped in v1

Asymmetric cost rule: anything ambiguous is unverified, never verified.
"""

from __future__ import annotations

from langchain_core.messages import ToolMessage

from tradingagents.agents.utils.evidence_verifier import (
    annotate_report,
    extract_claims,
    run_verification,
    verify_claim,
)


def _tool_msg(content: str, name: str = "get_stock_data") -> ToolMessage:
    return ToolMessage(content=content, name=name, tool_call_id=f"t-{name}")


def _state(reports: dict, tool_contents: list) -> dict:
    flat = {"market": "market_report", "social": "sentiment_report",
            "news": "news_report", "fundamentals": "fundamentals_report"}
    state = {"analyst_reports": reports, "messages": [
        _tool_msg(c) for c in tool_contents
    ]}
    for key, flat_key in flat.items():
        state[flat_key] = reports.get(key, "")
    return state


# ── extraction ────────────────────────────────────────────────────────────


class TestExtraction:
    def test_point_currency_with_unit(self):
        claims = extract_claims("公司2026年Q2净利润为 150 亿元，创历史新高。", "fundamentals")
        assert len(claims) == 1
        assert claims[0].value == 150e8
        assert claims[0].dimension == "currency"

    def test_percent_claim(self):
        claims = extract_claims("公司毛利率 85%，行业领先。", "fundamentals")
        assert len(claims) == 1
        assert claims[0].dimension == "percent" and claims[0].value == 85

    def test_range_claim(self):
        claims = extract_claims("当前批价在 2500-2700 元区间震荡。", "market")
        assert claims and claims[0].value_range == (2500.0, 2700.0)

    def test_growth_claims_skipped_in_v1(self):
        claims = extract_claims("净利润同比增长 30%，营收环比增长 5%。", "fundamentals")
        assert claims == []  # dual-period reconstruction not in v1

    def test_no_metric_keyword_no_claim(self):
        assert extract_claims("我们有 500 家门店。", "market") == []


# ── the three traps ───────────────────────────────────────────────────────


class TestThreeTraps:
    def test_trap_unit_drift_never_verified(self):
        """150 亿 claim must NOT verify against a tool 150 万 — certifying
        this mismatch is worse than no verifier at all."""
        claims = extract_claims("净利润为 150 亿元。", "fundamentals")
        evidence = [("本季度净利润 150 万元", "get_fundamentals")]
        result = verify_claim(claims[0], evidence)
        assert result.level == "unverified"

    def test_trap_semantic_drift_never_verified(self):
        claims = extract_claims("毛利率 85%。", "fundamentals")
        evidence = [("资产负债率 85%", "get_fundamentals")]
        assert verify_claim(claims[0], evidence).level == "unverified"

    def test_trap_semantic_match_does_verify(self):
        claims = extract_claims("毛利率 85%。", "fundamentals")
        evidence = [("2026年Q2 gross margin 85.2%", "get_fundamentals")]
        assert verify_claim(claims[0], evidence).level == "verified"

    def test_currency_verified_with_unit_normalization(self):
        claims = extract_claims("净利润 150 亿元。", "fundamentals")
        evidence = [("净利润 1500000 万元", "get_fundamentals")]  # 150万万元 = 150亿
        assert verify_claim(claims[0], evidence).level == "verified"

    def test_range_containment_verified(self):
        claims = extract_claims("批价在 2500-2700 元区间。", "market")
        evidence = [("今日批价 2600 元", "get_stock_data")]
        assert verify_claim(claims[0], evidence).level == "verified"

    def test_range_outside_not_verified(self):
        claims = extract_claims("批价在 2500-2700 元区间。", "market")
        evidence = [("今日批价 2400 元", "get_stock_data")]
        assert verify_claim(claims[0], evidence).level == "unverified"

    def test_usd_never_matches_cny(self):
        claims = extract_claims("净利润 150 亿美元。", "fundamentals")
        evidence = [("净利润 150 亿元", "get_fundamentals")]
        assert verify_claim(claims[0], evidence).level == "unverified"


# ── node-level pipeline ───────────────────────────────────────────────────


class TestRunVerification:
    def test_pipeline_counts_annotation_and_summary(self):
        reports = {
            "fundamentals": "净利润 150 亿元。这是不可验证的批价 9999 元表述。",
            "market": "批价在 2500-2700 元区间。",
        }
        state = _state(reports, ["净利润 1500000 万元", "今日批价 2600 元"])
        update = run_verification(state)

        v = update["verification"]
        # fundamentals carries 2 claims (净利润 150亿 + 批价 9999), market 1 range
        assert v["claims_total"] == 3
        assert v["verified"] == 2
        assert v["unverified"] == 1
        assert "## Evidence Verification Summary" in v["summary"]
        # annotated reports carry markers
        assert "[verified]" in update["analyst_reports"]["market"]
        assert "[unverified]" in update["analyst_reports"]["fundamentals"]

    def test_warnings_capped_at_20(self):
        # claims spaced 100 apart (beyond the +/-1% tolerance window so only
        # the exact-match claim verifies); evidence matches only 1500
        report = " ".join(f"批价 {1000 + 100 * i} 元。" for i in range(30))
        state = _state({"market": report}, ["今日批价 1500 元"])
        v = run_verification(state)["verification"]
        assert v["claims_total"] == 30
        assert v["verified"] == 1
        assert v["unverified"] == 29
        assert len(v["warnings"]) == 20  # cap: state-bloat guard

    def test_annotate_first_occurrence_only(self):
        text = "批价 2600 元。再次强调批价 2600 元。"
        claims = extract_claims(text, "market")
        annotated = annotate_report(text, claims[:1])
        assert annotated.count("[verified]") == 0  # unverified by default here
        assert annotated.count("[unverified]") == 1

    def test_financial_period_in_tool_output_is_usable_pit_evidence(self):
        reports = {"fundamentals": "2025年净利润为 823.20 亿元。"}
        state = _state(
            reports,
            [
                "# Income Statement data\n"
                "# Fiscal period latest: 2025-12-31\n"
                "Net Income From Continuing Operation Net Minority Interest: "
                "82320067101.68 元"
            ],
        )
        state["trade_date"] = "2026-08-20"

        verification = run_verification(state)["verification"]

        assert verification["verified"] == 1
        assert verification["unverified"] == 0
        assert not any("缺少来源日期" in warning for warning in verification["warnings"])


class TestThresholdClaims:
    """A4 taxonomy completion: directional claims verify by direction, not equality."""

    def test_floor_threshold_verified(self):
        claims = extract_claims("批价未跌破 2500 元支撑位。", "market")
        assert claims and claims[0].direction == ">="
        assert verify_claim(claims[0], [("今日批价 2600 元", "t")]).level == "verified"

    def test_ceiling_threshold_verified(self):
        claims = extract_claims("批价未突破 3000 元压力位。", "market")
        assert claims and claims[0].direction == "<="
        assert verify_claim(claims[0], [("今日批价 2600 元", "t")]).level == "verified"

    def test_broken_floor_not_verified(self):
        claims = extract_claims("批价未跌破 2500 元支撑位。", "market")
        assert verify_claim(claims[0], [("今日批价 2400 元", "t")]).level == "unverified"
