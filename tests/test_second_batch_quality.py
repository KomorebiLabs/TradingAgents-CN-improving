from types import SimpleNamespace

import pandas as pd
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from tradingagents.screener.data_access import ScreenerDataAccess
from tradingagents.screener.name_resolver import NameResolver
from tradingagents.screener.strategies.policy import PolicyStrategy
from tradingagents.screener.strategies.smart_money import SmartMoneyStrategy


def test_financial_ratios_are_computed_from_same_period_tool_evidence():
    from tradingagents.agents.utils.financial_metrics import build_financial_ratio_evidence

    messages = [
        SimpleNamespace(content=(
            "# Fiscal period latest: 2025-12-31\n"
            "Revenue (2025-12-31): 172050000000.00 元\n"
            "Net Income (2025-12-31): 82320000000.00 元\n"
            "Operating Cash Flow (2025-12-31): 61500000000.00 元"
        ))
    ]

    block = build_financial_ratio_evidence(messages)

    assert "OCF / Revenue" in block
    assert "61500000000.00 / 172050000000.00" in block
    assert "35.75%" in block
    assert "Net Margin" in block
    assert "period=2025-12-31" in block
    assert "unit=CNY yuan" in block


def test_financial_ratio_is_not_mixed_across_periods():
    from tradingagents.agents.utils.financial_metrics import build_financial_ratio_evidence

    messages = [SimpleNamespace(content=(
        "Revenue (2025-12-31): 100.00 元\n"
        "Operating Cash Flow (2024-12-31): 50.00 元"
    ))]

    assert build_financial_ratio_evidence(messages) == ""


def test_unverified_fund_flow_does_not_create_speculative_label():
    tag = SmartMoneyStrategy._build_capital_quality_tag(
        tick_score=80,
        multi_day_persistence_score=40,
        continuity_score=40,
        risk_constraint_score=40,
        institutional_score=40,
        heat_quality_gap_score=30,
        fund_flow_verified=False,
    )

    assert tag == "capital_quality_unverified"


def test_keyword_policy_linkage_is_explicitly_low_confidence():
    boundary = PolicyStrategy._build_concept_linkage_boundary(
        concept_verified=True,
        keyword_mode=True,
        concept_constituent_count=10,
        universe_cross_hit=False,
        concept_primary="ths",
        concept_fallback="eastmoney",
        news_auxiliary="baidu",
    )

    assert boundary["linkage_mode"] == "keyword_fallback_mapping"
    assert boundary["confidence_tier"] == "low"


def test_name_resolver_uses_snapshot_when_akshare_is_unavailable(monkeypatch, tmp_path):
    import tradingagents.screener.name_resolver as module

    monkeypatch.setattr(module, "_ak", None)
    monkeypatch.setattr(module, "_get_cache_root", lambda: tmp_path)
    snapshot = pd.DataFrame({"代码": ["600519"], "名称": ["贵州茅台"]})
    data_access = SimpleNamespace(fetch_spot_snapshot=lambda: snapshot)

    resolver = NameResolver(data_access=data_access, trade_date="2026-08-21").load()

    assert resolver.resolve("600519") == "贵州茅台"
    assert resolver.source == "spot_snapshot"


def test_tiny_partial_name_cache_is_rejected(monkeypatch, tmp_path):
    import json
    import tradingagents.screener.name_resolver as module

    monkeypatch.setattr(module, "_get_cache_root", lambda: tmp_path)
    cache_file = tmp_path / "names_20260821.json"
    cache_file.write_text(
        json.dumps({"names": {"000001": "平安银行", "000002": "万科企业", "000003": "测试公司"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    snapshot = pd.DataFrame({"代码": ["600519"], "名称": ["贵州茅台"]})
    resolver = NameResolver(
        data_access=SimpleNamespace(fetch_spot_snapshot=lambda: snapshot),
        trade_date="2026-08-21",
    ).load()

    assert resolver.resolve("600519") == "贵州茅台"
    assert any("invalidating" in warning for warning in resolver.warnings)


def test_index_constituents_fall_back_when_csindex_payload_fails(monkeypatch):
    from tradingagents.screener.vendors import sina

    expected = pd.DataFrame({"code": ["600519"], "name": ["贵州茅台"]})
    monkeypatch.setattr(sina, "fetch_index_cons_weight", lambda *_args: None)
    monkeypatch.setattr(sina, "fetch_index_cons_sina", lambda *_args: expected)
    access = ScreenerDataAccess(config={"a0_probe": {"enable_live_probes": False}})

    assert access.fetch_index_constituents("000300") is expected


def test_token_callback_reads_usage_from_chat_generation_message():
    from tradingagents.harness.engine import CostTracker, TokenCountingCallback

    tracker = CostTracker()
    callback = TokenCountingCallback(tracker)
    response = LLMResult(generations=[[
        ChatGeneration(message=AIMessage(
            content="ok",
            usage_metadata={"input_tokens": 123, "output_tokens": 45, "total_tokens": 168},
        ))
    ]])

    callback.on_llm_end(response)

    assert tracker.total.input_tokens == 123
    assert tracker.total.output_tokens == 45
