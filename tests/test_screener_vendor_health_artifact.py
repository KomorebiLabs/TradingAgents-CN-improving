import json

from tradingagents.screener.models import ScreeningResult
from tradingagents.screener.report import write_run_artifacts


def test_vendor_health_is_written_and_rendered_with_redacted_errors(tmp_path, monkeypatch):
    monkeypatch.setattr("tradingagents.screener.report._resolve_output_dir", lambda _config: tmp_path)
    result = ScreeningResult(
        run_id="health-run",
        mode="CUSTOM",
        trade_date="2026-08-24",
        started_at="2026-08-24T17:00:00",
        completed_at="2026-08-24T17:01:00",
        universe_size=1,
        metrics={
            "capability_summary": {
                "vendor_health": {
                    "tencent.hist": {
                        "calls": 4,
                        "failures": 1,
                        "failure_rate": 0.25,
                        "avg_seconds": 0.2,
                        "last_status": "ok",
                        "last_error": "token=super-secret",
                    }
                }
            }
        },
    )

    paths = write_run_artifacts(result, [])

    assert "vendor_health" in paths
    health = json.loads((tmp_path / "health-run" / "vendor_health.json").read_text(encoding="utf-8"))
    assert health["tencent.hist"]["last_error"] == "token=[REDACTED]"
    markdown = (tmp_path / "health-run" / "daily_gold_stocks_report.md").read_text(encoding="utf-8")
    assert "## 供应商健康状态" in markdown
    assert "calls=4" in markdown
    assert "failure_rate=25.0%" in markdown
    assert "super-secret" not in markdown
