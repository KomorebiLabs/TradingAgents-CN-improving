from tradingagents.screener.deep_analyzer import DeepAnalyzer
from tradingagents.screener.models import ScreeningResult, SignalCard
from tradingagents.screener.report import render_markdown_report


def _card():
    return SignalCard(
        ticker="600000.SH",
        raw_code="600000",
        exchange="SH",
        company_name="浦发银行",
        trade_date="2026-08-24",
        strategy_sources=["technical"],
        trigger_reason="test",
        initial_confidence=80,
        screening_score=85,
    )


def test_nested_explicit_disable_beats_environment(monkeypatch):
    monkeypatch.setenv("TRADINGAGENTS_DEEP_ANALYSIS_ENABLED", "true")
    analyzer = DeepAnalyzer({"deep_analyzer": {"enable_real_deep_analysis": False}})

    assert analyzer._enable_real_analysis is False

    result = analyzer.analyze(_card(), "2026-08-24")

    assert result.execution_status == "DRY_RUN_REQUESTED"
    assert result.final_state_summary["analysis_mode"] == "dry_run_requested"


def test_graph_success_has_graph_completed_status(monkeypatch):
    class Graph:
        def __init__(self, **kwargs):
            pass

        def propagate(self, ticker, trade_date):
            return {"company_of_interest": ticker, "final_trade_decision": "HOLD"}, "HOLD"

    monkeypatch.setattr("tradingagents.screener.deep_analyzer.TradingAgentsGraph", Graph)
    analyzer = DeepAnalyzer({"deep_analyzer": {"enable_real_deep_analysis": True}})

    result = analyzer.analyze(_card(), "2026-08-24")

    assert result.execution_status == "GRAPH_COMPLETED"
    assert result.success is True


def test_graph_exception_has_fallback_completed_status(monkeypatch):
    class BrokenGraph:
        def __init__(self, **kwargs):
            raise RuntimeError("graph unavailable")

    monkeypatch.setattr("tradingagents.screener.deep_analyzer.TradingAgentsGraph", BrokenGraph)
    analyzer = DeepAnalyzer({"deep_analyzer": {"enable_real_deep_analysis": True}})

    result = analyzer.analyze(_card(), "2026-08-24")

    assert result.execution_status == "FALLBACK_COMPLETED"
    assert result.final_state_summary["analysis_mode"] == "fallback"
    assert result.final_state_summary["fallback_used"] is True


def test_fallback_failure_returns_structured_failed_status(monkeypatch):
    class BrokenGraph:
        def __init__(self, **kwargs):
            raise RuntimeError("graph unavailable")

    monkeypatch.setattr("tradingagents.screener.deep_analyzer.TradingAgentsGraph", BrokenGraph)
    analyzer = DeepAnalyzer({"deep_analyzer": {"enable_real_deep_analysis": True}})
    monkeypatch.setattr(analyzer, "_dry_run", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("fallback failed")))

    result = analyzer.analyze(_card(), "2026-08-24")

    assert result.execution_status == "FAILED"
    assert result.success is False
    assert "fallback failed" in result.error


def test_pre_graph_context_failure_is_structured(monkeypatch):
    analyzer = DeepAnalyzer({"deep_analyzer": {"enable_real_deep_analysis": True}})
    monkeypatch.setattr(analyzer, "_build_semantic_context", lambda _card: (_ for _ in ()).throw(ValueError("context failed")))

    result = analyzer.analyze(_card(), "2026-08-24")

    assert result.execution_status == "FAILED"
    assert result.success is False
    assert "context failed" in result.error


def test_legacy_top_level_flag_is_compatible_but_warned(monkeypatch):
    monkeypatch.delenv("TRADINGAGENTS_DEEP_ANALYSIS_ENABLED", raising=False)
    analyzer = DeepAnalyzer({"enable_real_deep_analysis": False})

    assert analyzer._enable_real_analysis is False
    assert any("DEPRECATED" in warning for warning in analyzer.config_warnings)


def test_markdown_exposes_same_execution_status_as_json(monkeypatch):
    analyzer = DeepAnalyzer({"deep_analyzer": {"enable_real_deep_analysis": False}})
    deep_result = analyzer.analyze(_card(), "2026-08-24")
    screening = ScreeningResult(
        run_id="deep-status",
        mode="CUSTOM",
        trade_date="2026-08-24",
        started_at="2026-08-24T17:00:00",
        completed_at="2026-08-24T17:01:00",
        universe_size=1,
        candidates=[_card()],
    )

    markdown = render_markdown_report(screening, [deep_result])

    assert "Execution Status: DRY_RUN_REQUESTED" in markdown


def test_cli_summary_counts_execution_statuses(capsys):
    analyzer = DeepAnalyzer(
        {"deep_analyzer": {"enable_real_deep_analysis": False, "max_stocks": 1}}
    )

    analyzer.analyze_top_candidates([_card()], "2026-08-24")

    assert "DRY_RUN_REQUESTED=1" in capsys.readouterr().out
