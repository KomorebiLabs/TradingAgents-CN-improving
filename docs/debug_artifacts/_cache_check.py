# Check what's actually in the current cache file
from pathlib import Path
import json

out = Path.home() / '.tradingagents' / 'cache' / 'screener' / '_cache_check.txt'

cache_file = Path.home() / '.tradingagents' / 'cache' / 'screener' / 'names_20260508.json'

with open(out, 'w', encoding='utf-8') as f:
    def log(msg):
        f.write(msg + '\n')

    log(f"Cache file exists: {cache_file.exists()}")
    log(f"Cache file size: {cache_file.stat().st_size} bytes")

    if cache_file.exists():
        with open(cache_file, 'r', encoding='utf-8') as cf:
            data = json.load(cf)
        names = data.get('names', {})
        log(f"Total entries: {len(names)}")

        # Check first 10 entries
        log("\nFirst 10 entries:")
        for i, (code, name) in enumerate(list(names.items())[:10]):
            hex_val = name.encode('utf-8', errors='replace').hex()
            log(f"  {code}: {name!r} (hex={hex_val})")

        # Check target entries
        log("\nTarget entries:")
        for code in ['600519', '000001', '000002']:
            name = names.get(code, 'NOT_FOUND')
            hex_val = name.encode('utf-8', errors='replace').hex()
            log(f"  {code}: {name!r} (hex={hex_val})")

        # Check validation function
        log("\nValidation function test:")
        from tradingagents.screener.name_resolver import _is_valid_chinese_name
        for code, name in list(names.items())[:10]:
            valid = _is_valid_chinese_name(name)
            log(f"  _is_valid_chinese_name({name!r}): {valid}")

        log(f"\nTotal valid: {sum(1 for n in names.values() if _is_valid_chinese_name(n))}")
        log(f"First 5 names: {[n for n in list(names.values())[:5]]}")

print("Written to:", out)
