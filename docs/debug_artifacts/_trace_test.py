"""Trace what happens to company_name through the full engine path."""
import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# Step 1: Check raw cache
cache_file = Path.home() / ".tradingagents" / "cache" / "screener" / "names_20260508.json"
data = json.load(open(cache_file, encoding="utf-8"))
names = data.get("names", {})
v = names.get("600519")
print(f"1. Cache read: {v!r}")

# Step 2: NameResolver
from tradingagents.screener.name_resolver import NameResolver
resolver = NameResolver(trade_date="2026-05-08")
resolver.load()
v2 = resolver.resolve("600519")
print(f"2. resolver.resolve('600519'): {v2!r}")

# Step 3: Create a SignalCard and check company_name
from tradingagents.screener.models import SignalCard
card = SignalCard(
    ticker="600519.SH",
    raw_code="600519",
    exchange="SH",
    company_name="PLACEHOLDER",
    trade_date="2026-05-08",
    trigger_reason="test",
    initial_confidence=80.0,
    screening_score=75.0,
)
print(f"3. card.company_name before: {card.company_name!r}")
card.company_name = v2
print(f"4. card.company_name after assign: {card.company_name!r}")

# Step 4: Serialize the card
serialized = card.model_dump()
print(f"5. card.model_dump()['company_name']: {serialized.get('company_name')!r}")

# Step 5: Check what merger creates
from tradingagents.screener.merger import merge_signal_cards
from tradingagents.screener.models import SignalCard
test_card = SignalCard(
    ticker="600519.SH",
    raw_code="600519",
    exchange="SH",
    company_name="STRATEGY_PLACEHOLDER",
    trade_date="2026-05-08",
    trigger_reason="test",
    initial_confidence=80.0,
    screening_score=75.0,
)
merged, dropped = merge_signal_cards([test_card], mode="MVP")
print(f"\n6. After merge:")
print(f"   merged count: {len(merged)}")
print(f"   dropped count: {len(dropped)}")
if dropped:
    first_drop = dropped[0]
    print(f"   dropped[0] type: {type(first_drop).__name__}")
    if isinstance(first_drop, dict):
        print(f"   dropped[0]['company_name']: {first_drop.get('company_name')!r}")

# Step 6: Check if merged cards have company_name modified
if merged:
    print(f"   merged[0].company_name: {merged[0].company_name!r}")
