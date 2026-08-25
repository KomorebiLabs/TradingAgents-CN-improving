"""Aggregate auditable multi-day Screener acceptance evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _audit_run(path: Path) -> dict[str, Any]:
    failures: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"artifact": str(path), "failures": [f"invalid_json:{type(exc).__name__}"]}

    metrics = payload.get("metrics", {}) or {}
    capability = metrics.get("capability_summary", {}) or {}
    health = capability.get("vendor_health", {}) or {}
    config = metrics.get("effective_config_used", {}) or {}
    universe = payload.get("universe_metadata", {}) or {}
    candidates = payload.get("candidates", []) or []

    if not (path.parent / "vendor_health.json").exists() or not health:
        failures.append("vendor_health_missing")
    if not config:
        failures.append("config_snapshot_missing")
    if not (universe.get("cache_as_of") or universe.get("built_at") or universe.get("source")):
        failures.append("universe_as_of_missing")
    if any(
        item.get("recommendation_eligible") and item.get("stale_required_sources")
        for item in candidates
    ):
        failures.append("stale_formal_recommendation")

    return {
        "artifact": str(path),
        "run_id": payload.get("run_id", ""),
        "mode": payload.get("mode", ""),
        "trade_date": payload.get("trade_date", ""),
        "completed_at": payload.get("completed_at", ""),
        "elapsed_seconds": metrics.get("elapsed_seconds_total"),
        "candidate_count": len(candidates),
        "eligible_count": sum(bool(item.get("recommendation_eligible")) for item in candidates),
        "vendor_count": len(health),
        "failures": failures,
    }


def build_acceptance_summary(reports_dir: Path, required_days: int = 5) -> dict[str, Any]:
    """Audit the latest run for each distinct trade date under reports_dir."""
    audited = [_audit_run(path) for path in reports_dir.glob("*/screening_result.json")]
    valid = [item for item in audited if item.get("trade_date")]
    latest_by_day: dict[str, dict[str, Any]] = {}
    for item in valid:
        previous = latest_by_day.get(item["trade_date"])
        if previous is None or (item.get("completed_at", ""), item["artifact"]) > (
            previous.get("completed_at", ""),
            previous["artifact"],
        ):
            latest_by_day[item["trade_date"]] = item
    runs = [latest_by_day[key] for key in sorted(latest_by_day)]
    enough_days = len(runs) >= max(int(required_days), 1)
    passed = enough_days and all(not item["failures"] for item in runs)
    return {
        "schema_version": 1,
        "required_trade_days": max(int(required_days), 1),
        "distinct_trade_days": len(runs),
        "runs_checked": len(runs),
        "passed": passed,
        "failures": ([] if enough_days else ["insufficient_distinct_trade_days"]),
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit multi-day Screener artifacts")
    parser.add_argument("--reports-dir", type=Path, default=Path("reports/Screener"))
    parser.add_argument("--required-days", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = build_acceptance_summary(args.reports_dir, args.required_days)
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
