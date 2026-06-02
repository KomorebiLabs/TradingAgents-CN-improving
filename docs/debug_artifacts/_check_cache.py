import sys
sys.stdout.reconfigure(encoding="utf-8")

# Test: After creating a ScreenerResult with dropped_candidates,
# if I mutate the dicts in dropped_candidates, do the changes persist?

from tradingagents.screener.models import SignalCard, ScreeningResult
from datetime import datetime

# Create a result with dropped_candidates
result = ScreeningResult(
    run_id="test-123",
    mode="MVP",
    trade_date="2026-05-08",
    started_at=datetime.now().isoformat(),
    completed_at=datetime.now().isoformat(),
    universe_size=3,
    candidates=[],
    dropped_candidates=[
        {"ticker": "600519.SH", "company_name": "PLACEHOLDER"},
        {"ticker": "000001.SZ", "company_name": "PLACEHOLDER"},
    ],
    strategy_status={},
    data_issues=[],
    metrics={},
)

print(f"Before mutation:")
for item in result.dropped_candidates:
    print(f"  {item.get('ticker')}: {item.get('company_name')!r}")

# Mutate the dropped_candidates (what engine.py does)
for item in result.dropped_candidates:
    item["company_name"] = "贵州茅台"

print(f"\nAfter mutation:")
for item in result.dropped_candidates:
    print(f"  {item.get('ticker')}: {item.get('company_name')!r}")

# Serialize (what _serialize_for_output does)
import json
output = {
    "dropped_candidates": [
        {
            "ticker": item.get("ticker", f"dropped_{i}"),
            "company_name": item.get("company_name", item.get("ticker", f"dropped_{i}")),
        }
        for i, item in enumerate(result.dropped_candidates, 1)
    ]
}
print(f"\nJSON output:")
print(json.dumps(output, ensure_ascii=False, indent=2))
