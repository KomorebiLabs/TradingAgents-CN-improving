"""Check raw bytes of the actual screener JSON output."""
import json
from pathlib import Path

log_dir = Path.home() / ".tradingagents" / "logs" / "screener"

# Get all screener JSON files, sorted by modification time
files = sorted(log_dir.glob("screener_2026-05-08_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

latest = files[0]
print(f"Checking: {latest.name}")
print(f"Modified: {latest.stat().st_mtime}")

# Read raw bytes
raw = open(latest, "rb").read()

# Find '600519' and surrounding bytes
idx = raw.find(b"600519")
if idx >= 0:
    # Get context
    start = max(0, idx - 100)
    end = min(len(raw), idx + 200)
    context = raw[start:end]
    # Try to decode as UTF-8 with replace
    try:
        text = context.decode("utf-8")
        print(f"\nUTF-8 context around '600519':")
        print(text)
    except:
        print(f"\nUTF-8 decode FAILED for context")

    # Find the company_name for 600519
    # Pattern: "600519": { ... "company_name": "XXX"
    name_start = raw.find(b'"company_name"', idx)
    if name_start >= 0:
        # Get the value
        val_start = raw.find(b'"', name_start + len(b'"company_name"') + 1) + 1
        val_end = raw.find(b'"', val_start)
        val_bytes = raw[val_start:val_end]
        print(f"\ncompany_name bytes: {val_bytes}")
        print(f"company_name UTF-8: {val_bytes.decode('utf-8', errors='replace')!r}")
        print(f"company_name hex: {val_bytes.hex()}")

# Also check via json.load
data = json.load(open(latest, encoding="utf-8"))
for d in data.get("dropped_candidates", []):
    if "600519" in d.get("ticker", ""):
        print(f"\njson.load result:")
        print(f"  company_name = {d.get('company_name')!r}")
        v = d.get("company_name", "")
        print(f"  repr bytes: {repr(v.encode('utf-8'))}")
