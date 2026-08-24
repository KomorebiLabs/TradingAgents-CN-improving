from tradingagents.screener.models import ScreeningResult
from tradingagents.screener.runtime_guard import check_data_consistency


def _result(*, strategy_status=None, metrics=None):
    return ScreeningResult(
        run_id="run-test",
        mode="CUSTOM",
        trade_date="2026-08-24",
        started_at="2026-08-24T17:00:00",
        completed_at="2026-08-24T17:01:00",
        universe_size=3,
        candidates=[],
        strategy_status=strategy_status or {},
        metrics=metrics or {},
    )


def test_normal_empty_result_is_valid_no_candidate():
    result = _result(strategy_status={"technical": "ready", "policy": "ready"})

    issues = check_data_consistency(result)

    assert result.run_status == "NO_CANDIDATE_VALID"
    assert not any("[FATAL]" in issue for issue in issues)


def test_empty_status_is_available_before_artifact_rendering():
    result = _result(strategy_status={"technical": "ready"})

    assert result.run_status == "NO_CANDIDATE_VALID"


def test_degraded_empty_result_is_distinguished():
    result = _result(strategy_status={"technical": "degraded"})

    issues = check_data_consistency(result)

    assert result.run_status == "NO_CANDIDATE_DEGRADED"
    assert any("[WARN]" in issue for issue in issues)
    assert not any("[FATAL]" in issue for issue in issues)


def test_pipeline_failure_is_the_only_fatal_empty_state():
    result = _result(metrics={"pipeline_failed": True})

    issues = check_data_consistency(result)

    assert result.run_status == "PIPELINE_FAILED"
    assert any("[FATAL]" in issue for issue in issues)
