"""The one definitive test: verify engine's cache read vs current file content."""
import json
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

cache_file = Path.home() / ".tradingagents" / "cache" / "screener" / "names_20260508.json"
log_dir = Path.home() / ".tradingagents" / "logs" / "screener"

# 1. Check what the CURRENT cache file contains (on disk right now)
data_current = json.load(open(cache_file, encoding="utf-8"))
names_current = data_current.get("names", {})
print(f"[CURRENT FILE] 600519 = {names_current.get('600519')!r}")
print(f"[CURRENT FILE] 000001 = {names_current.get('000001')!r}")

# 2. Check what the _name_debug.json file says the engine read
debug_file = log_dir / "_name_debug.json"
if debug_file.exists():
    debug_data = json.load(open(debug_file, encoding="utf-8"))
    print(f"\n[ENGINE DEBUG] cache_600519 = {debug_data.get('cache_600519')!r}")
    print(f"[ENGINE DEBUG] cache_sh600519 = {debug_data.get('cache_sh600519')!r}")
    print(f"[ENGINE DEBUG] source = {debug_data.get('source')!r}")
else:
    print("\n[ENGINE DEBUG] No debug file found")

# 3. Check what the latest screener JSON contains
files = sorted(log_dir.glob("screener_2026-05-08_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
if files:
    latest = files[0]
    screener_data = json.load(open(latest, encoding="utf-8"))
    print(f"\n[SCREENER JSON] {latest.name} ({latest.stat().st_mtime}):")
    for d in screener_data.get("dropped_candidates", []):
        print(f"  {d.get('ticker')}: company_name={d.get('company_name')!r}")

# 4. Show all cached names for our tickers
print(f"\n[ALL CACHE] entries: {len(names_current)}")
for code in ["600519", "000001", "000858", "300750"]:
    print(f"  {code} = {names_current.get(code, 'NOT FOUND')!r}")
