from tradingagents.screener.engine import ScreenerEngine
from types import SimpleNamespace


def test_prepare_stagea_input_deduplicates_before_applying_budget():
    engine = ScreenerEngine()

    selected = engine._prepare_stagea_input(
        ["600000", "600000", "000001", "300750"],
        max_input=2,
    )

    assert selected == ["600000", "000001"]


def test_prepare_stagea_input_with_zero_budget_selects_nothing():
    engine = ScreenerEngine()

    assert engine._prepare_stagea_input(["600000"], max_input=0) == []


def test_select_stageb_candidates_uses_score_not_source_order():
    engine = ScreenerEngine()
    candidates = [
        SimpleNamespace(ticker="600000", stage_a_score=55.0),
        SimpleNamespace(ticker="000001", stage_a_score=91.0),
        SimpleNamespace(ticker="300750", stage_a_score=72.0),
    ]

    selected = engine._select_stageb_candidates(candidates, max_input=2)

    assert [candidate.ticker for candidate in selected] == ["000001", "300750"]


def test_select_stageb_candidates_breaks_score_ties_by_ticker():
    engine = ScreenerEngine()
    candidates = [
        SimpleNamespace(ticker="600000", stage_a_score=80.0),
        SimpleNamespace(ticker="000001", stage_a_score=80.0),
    ]

    selected = engine._select_stageb_candidates(candidates, max_input=2)

    assert [candidate.ticker for candidate in selected] == ["000001", "600000"]
