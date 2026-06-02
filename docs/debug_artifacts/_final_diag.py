# DIAG: Final comprehensive check - write ALL results to file
import sys
import json
from pathlib import Path

out = Path.home() / '.tradingagents' / 'cache' / 'screener' / '_final_diag.txt'
out.parent.mkdir(parents=True, exist_ok=True)

with open(out, 'w', encoding='utf-8') as f:
    def log(msg):
        f.write(msg + '\n')

    # 1. Check what the name_resolver currently gives
    log("=== NameResolver Test ===")
    from tradingagents.screener.name_resolver import NameResolver
    resolver = NameResolver(trade_date='2026-05-08')
    resolver.load()
    log(f"source: {resolver.source}")
    log(f"cache_size: {len(resolver._cache)}")

    # Check specific entries
    for code in ['600519', '000001', '000002']:
        name = resolver.resolve(code)
        # Write hex bytes to avoid any encoding issues
        name_hex = name.encode('utf-8', errors='replace').hex()
        f.write(f"  resolve({code!r}) = {name!r} (UTF-8 hex: {name_hex})\n")

    # 2. Check what's in the cache file
    log("\n=== Cache File Content ===")
    cache_file = out.parent / 'names_20260508.json'
    if cache_file.exists():
        with open(cache_file, 'r', encoding='utf-8') as cf:
            data = json.load(cf)
        names = data.get('names', {})
        log(f"Cache file size: {len(names)} entries")
        for code in ['600519', '000001', '000002']:
            name = names.get(code, 'NOT_IN_FILE')
            name_hex = name.encode('utf-8', errors='replace').hex()
            f.write(f"  {code}: {name!r} (UTF-8 hex: {name_hex})\n")

    # 3. Does akshare give clean data RIGHT NOW?
    log("\n=== akshare.stock_info_a_code_name Test ===")
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        found = {}
        for _, row in df.iterrows():
            code = str(row['code']).strip()
            if code in ['600519', '000001']:
                name = str(row['name']).strip()
                name_hex = name.encode('utf-8', errors='replace').hex()
                f.write(f"  AKSHARE {code}: {name!r} (UTF-8 hex: {name_hex})\n")
    except Exception as e:
        f.write(f"  Error: {e}\n")

    log("\n=== Done ===")

print("Written to:", out)
