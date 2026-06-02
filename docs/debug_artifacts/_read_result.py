import json
from pathlib import Path
from datetime import datetime

log_dir = Path.home() / ".tradingagents" / "logs" / "screener"

print("=== All screener JSON files ===")
for p in sorted(log_dir.glob("screener_2026-05-08_*.json")):
    mtime = datetime.fromtimestamp(p.stat().st_mtime)
    print(f"  {p.name}  modified: {mtime}")

print("\n=== Debug files ===")
for p in sorted(log_dir.glob("_*.json")):
    mtime = datetime.fromtimestamp(p.stat().st_mtime)
    data = json.load(open(p, encoding="utf-8"))
    print(f"  {p.name}  modified: {mtime}")
    print(f"    content: {data}")
