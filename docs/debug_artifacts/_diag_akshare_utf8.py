# DIAG: Verify console encoding and check if data is correct
import sys
import json
from pathlib import Path

# Set console to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

print("Console encoding:", sys.stdout.encoding)

# Now use akshare to get names
import akshare as ak
df = ak.stock_info_a_code_name()
print("Fetched", len(df), "stocks")

names = {}
for _, row in df.iterrows():
    code = str(row['code']).strip()
    name = str(row['name']).strip()
    names[code] = name
    if len(names) >= 6000:
        break

# Save to cache
cache_dir = Path.home() / '.tradingagents' / 'cache' / 'screener'
cache_dir.mkdir(parents=True, exist_ok=True)
cache_file = cache_dir / 'names_akshare.json'
with open(cache_file, 'w', encoding='utf-8') as f:
    json.dump({'date': '2026-05-08', 'names': names}, f, ensure_ascii=False, indent=2)
print("Saved to:", cache_file)

# Check a few key stocks
for code in ['600519', '000001', '688981', 'sh600519']:
    name = names.get(code, 'NOT_FOUND')
    print(f"  {code}: {name}")
