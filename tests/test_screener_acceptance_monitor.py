from __future__ import annotations

import json

from tradingagents.screener.acceptance import build_acceptance_summary


def _write_run(root, run_id, trade_date, *, stale_recommendation=False, completed_at="2026-08-24T10:00:00"):
    run_dir = root / run_id
    run_dir.mkdir()
    candidate = {
        "ticker": "600000.SH",
        "recommendation_eligible": True,
        "stale_required_sources": ["history"] if stale_recommendation else [],
    }
    payload = {
        "run_id": run_id,
        "mode": "FULL",
        "trade_date": trade_date,
        "completed_at": completed_at,
        "universe_metadata": {"cache_as_of": trade_date},
        "candidates": [candidate],
        "metrics": {
            "elapsed_seconds_total": 12.0,
            "effective_config_used": {"stagea_max_input": 5},
            "capability_summary": {"vendor_health": {"vendor": {"calls": 1, "failures": 0}}},
        },
    }
    (run_dir / "screening_result.json").write_text(json.dumps(payload), encoding="utf-8")
    (run_dir / "vendor_health.json").write_text("{}", encoding="utf-8")


def test_acceptance_requires_five_distinct_trade_dates_and_required_artifacts(tmp_path):
    for day in range(18, 23):
        _write_run(tmp_path, f"run-{day}", f"2026-08-{day}")

    summary = build_acceptance_summary(tmp_path, required_days=5)

    assert summary["passed"] is True
    assert summary["distinct_trade_days"] == 5
    assert summary["runs_checked"] == 5


def test_acceptance_fails_on_stale_formal_recommendation(tmp_path):
    _write_run(tmp_path, "bad-run", "2026-08-24", stale_recommendation=True)

    summary = build_acceptance_summary(tmp_path, required_days=1)

    assert summary["passed"] is False
    assert "stale_formal_recommendation" in summary["runs"][0]["failures"]


def test_acceptance_uses_latest_completed_run_for_each_trade_date(tmp_path):
    _write_run(tmp_path, "z-old", "2026-08-24", stale_recommendation=True, completed_at="2026-08-24T10:00:00")
    _write_run(tmp_path, "a-new", "2026-08-24", completed_at="2026-08-24T11:00:00")

    summary = build_acceptance_summary(tmp_path, required_days=1)

    assert summary["passed"] is True
    assert summary["runs"][0]["run_id"] == "a-new"
