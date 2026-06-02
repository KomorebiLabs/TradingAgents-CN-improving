"""Minimal test: does engine.run() return the correct company names?"""
import json
import sys
from pathlib import Path
from datetime import datetime

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

# Step 1: Ensure cache is fresh
cache_file = Path.home() / ".tradingagents" / "cache" / "screener" / "names_20260508.json"
if cache_file.exists():
    cache_file.unlink()
    print(f"Cleared cache: {cache_file}")

# Step 2: Verify resolver works standalone
from tradingagents.screener.name_resolver import NameResolver
resolver = NameResolver(trade_date="2026-05-08")
resolver.load()
test = resolver.resolve("600519")
print(f"Standalone resolver: resolve('600519') = {test!r}")
assert test == "贵州茅台", f"Resolver broken! Got {test!r}"
print("Resolver verified OK")

# Step 3: Run engine with minimal config
from tradingagents.screener.engine import ScreenerEngine

config = {
    "runtime_guard": {
        "allow_weekend": True,
    },
    "universe": {
        "profile": "MVP",
        "custom_tickers": ["600519"],
    },
    "candidates": {"max_output": 5},
    "deep_analyzer": {
        "enable_real_deep_analysis": False,
        "max_stocks": 5,
    },
}

print("\nRunning engine.run() ...")
engine = ScreenerEngine(config=config)
result = engine.run(
    mode="MVP",
    trade_date="2026-05-08",
    enable_deep_analysis=False,
    persist_outputs=False,
)
print("engine.run() returned successfully!")

# Step 4: Check company names
print(f"\nresult.dropped_candidates count: {len(result.dropped_candidates)}")
for item in result.dropped_candidates:
    print(f"  ticker={item.get('ticker')!r} company_name={item.get('company_name')!r}")

# Step 5: Write result to file so we can inspect without encoding issues
out = {
    "candidates": [
        {
            "ticker": c.ticker,
            "company_name": getattr(c, "company_name", "NOT_SET"),
        }
        for c in result.candidates
    ],
    "dropped_candidates": result.dropped_candidates,
}
debug_out = Path.home() / ".tradingagents" / "logs" / "screener" / "_minimal_test.json"
debug_out.parent.mkdir(parents=True, exist_ok=True)
with open(debug_out, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"\nWritten to: {debug_out}")
print("DONE")
