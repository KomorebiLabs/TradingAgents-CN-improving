"""Is dropped_candidates a mutable reference or frozen?"""
import json
from datetime import datetime
from tradingagents.screener.models import SignalCard, ScreeningResult

# Create result with dropped_candidates
dropped = [
    {"ticker": "600519.SH"},
    {"ticker": "000858.SZ"},
]

result = ScreeningResult(
    run_id="test-123",
    mode="MVP",
    trade_date="2026-05-08",
    started_at=datetime.now().isoformat(),
    completed_at=datetime.now().isoformat(),
    universe_size=3,
    candidates=[],
    dropped_candidates=dropped,  # PASS BY REFERENCE
    strategy_status={},
    data_issues=[],
    metrics={},
)

print(f"Before: result.dropped_candidates[0] = {result.dropped_candidates[0]}")

# Mutate what we think is the same reference
result.dropped_candidates[0]["company_name"] = "贵州茅台"

print(f"After: result.dropped_candidates[0] = {result.dropped_candidates[0]}")

# Check if the ORIGINAL 'dropped' list was also mutated
print(f"After: dropped[0] = {dropped[0]}")

# Serialize
payload = result.model_dump()
print(f"JSON: dropped_candidates[0]['company_name'] = {payload['dropped_candidates'][0].get('company_name')!r}")

# The real test: what does _serialize_for_output produce?
def _serialize_for_output(result):
    return {
        "dropped_candidates": [
            {
                "ticker": item.get("ticker", f"dropped_{i}"),
                "company_name": item.get("company_name", item.get("ticker", f"dropped_{i}")),
            }
            for i, item in enumerate(result.dropped_candidates, 1)
        ]
    }

out = _serialize_for_output(result)
print(f"_serialize_for_output: {json.dumps(out, ensure_ascii=False)}")
