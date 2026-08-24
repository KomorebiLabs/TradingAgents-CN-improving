from tradingagents.screener.merger import merge_signal_cards
from tradingagents.screener.models import DataFreshness, SignalCard, SignalEvidence
from tradingagents.screener.models import ScreeningResult
from cli.screener.run_impl import _serialize_for_output
from tradingagents.screener.report import render_markdown_report


def _card(strategy: str, freshness: list[DataFreshness]) -> SignalCard:
    evidence = SignalEvidence(
        strategy=strategy,
        score=85,
        reason="qualification-test",
        freshness=freshness,
    )
    return SignalCard(
        ticker="600000.SH",
        raw_code="600000",
        exchange="SH",
        company_name="浦发银行",
        trade_date="2026-08-24",
        strategy_sources=[strategy],
        signal_breakdown=[evidence],
        trigger_reason="test",
        initial_confidence=80,
        screening_score=85,
        data_source_verified=True,
    )


def _fresh(source: str, status: str = "fresh", trade_date: str | None = "2026-08-24") -> DataFreshness:
    return DataFreshness(
        source=source,
        trade_date=trade_date,
        fetched_at="2026-08-24T17:00:00",
        status=status,
    )


def test_recommendation_mode_drops_card_missing_required_evidence():
    card = _card("technical", [_fresh("hist_fetch")])

    retained, dropped = merge_signal_cards(
        [card],
        config={"output_purpose": "recommendation", "candidates": {"max_output": 3}},
    )

    assert retained == []
    assert "missing_required_evidence" in dropped[0]["reasons"]
    assert dropped[0]["missing_required_modules"] == ["fund_flow"]


def test_optional_degradation_does_not_block_complete_smart_money_strategy():
    card = _card(
        "smart_money",
        [_fresh("hist_fetch"), _fresh("tick_data", status="missing", trade_date=None)],
    )

    retained, _ = merge_signal_cards(
        [card],
        config={"output_purpose": "recommendation", "candidates": {"max_output": 3}},
    )

    assert len(retained) == 1
    assert retained[0].recommendation_eligible is True
    assert retained[0].degraded_modules == ["tick_data"]


def test_required_freshness_summary_records_oldest_date_and_lag():
    card = _card(
        "technical",
        [_fresh("hist_fetch", trade_date="2026-08-23"), _fresh("fund_flow")],
    )

    retained, _ = merge_signal_cards(
        [card],
        config={"output_purpose": "research", "candidates": {"max_output": 3}},
    )

    assert retained[0].latest_required_data_date == "2026-08-23"
    assert retained[0].max_required_data_lag_days == 1
    assert retained[0].stale_required_sources == ["hist_fetch"]
    assert retained[0].recommendation_eligible is False


def test_qualification_is_exposed_in_json_and_markdown_outputs():
    card = _card("smart_money", [_fresh("hist_fetch")])
    retained, _ = merge_signal_cards(
        [card],
        config={"output_purpose": "recommendation", "candidates": {"max_output": 3}},
    )
    result = ScreeningResult(
        run_id="qualification-output",
        mode="CUSTOM",
        trade_date="2026-08-24",
        started_at="2026-08-24T17:00:00",
        completed_at="2026-08-24T17:01:00",
        universe_size=1,
        candidates=retained,
        run_status="COMPLETED",
    )

    payload = _serialize_for_output(result)
    markdown = render_markdown_report(result, [])

    assert payload["run_status"] == "COMPLETED"
    assert payload["candidates"][0]["recommendation_eligible"] is True
    assert "正式推荐资格" in markdown
    assert "关键数据最大滞后" in markdown
