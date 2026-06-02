# Verify engine output quality
import json
from pathlib import Path

out = Path.home() / '.tradingagents' / 'cache' / 'screener' / '_engine_check.txt'
out.parent.mkdir(parents=True, exist_ok=True)

with open(out, 'w', encoding='utf-8') as f:
    def log(msg):
        f.write(msg + '\n')

    output_dir = Path(r'd:\cursor\HarmonyOS\Github project\TradingAgents-main\.tmp_screener_test')

    log("=== Checking ALL screener output files ===\n")

    for json_file in sorted(output_dir.glob('screener_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:3]:
        log(f"File: {json_file.name}")
        with open(json_file, 'r', encoding='utf-8') as jf:
            data = json.load(jf)

        log(f"  mode: {data['mode']}")
        log(f"  date: {data['trade_date']}")
        log(f"  universe_size: {data['universe_size']}")
        log(f"  candidates: {len(data['candidates'])}")
        log(f"  dropped: {len(data['dropped_candidates'])}")
        log(f"  strategy_status: {data['strategy_status']}")

        # Check names in dropped candidates (these are where we see if names are real)
        for i, item in enumerate(data.get('dropped_candidates', [])[:5]):
            ticker = item.get('ticker', '?')
            company = item.get('company_name', 'MISSING')
            company_hex = company.encode('utf-8', errors='replace').hex()
            f.write(f"  Dropped[{i}] {ticker}: company_name={company!r} (hex: {company_hex})\n")

        # Check if any candidates have names
        for i, item in enumerate(data.get('candidates', [])[:5]):
            ticker = item.get('ticker', '?')
            name = item.get('name', 'MISSING')
            company = item.get('company_name', 'MISSING')
            name_hex = name.encode('utf-8', errors='replace').hex() if len(name) < 20 else 'too_long'
            f.write(f"  Candidate[{i}] {ticker}: name={name!r} (hex: {name_hex}), company={company!r}\n")

        log("")

    log("=== Summary ===")
    log("If company_name hex is NOT 'e8b4b5e5b79ee88c85e58fb0' (for 贵州茅台), there's an issue.")
    log("If it's 'e8b4b5e5b79ee88c85e58fb0', names ARE correct!")

print("Written to:", out)
