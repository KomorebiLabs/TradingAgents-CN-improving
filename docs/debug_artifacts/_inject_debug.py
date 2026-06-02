# Check if engine injection actually changes the company_name
import sys
import json
from pathlib import Path

out = Path.home() / '.tradingagents' / 'cache' / 'screener' / '_inject_debug.txt'
out.parent.mkdir(parents=True, exist_ok=True)

with open(out, 'w', encoding='utf-8') as f:
    def log(msg):
        f.write(msg + '\n')

    from tradingagents.screener.engine import ScreenerEngine

    engine = ScreenerEngine(config={
        'mode': 'MVP',
        'run_time': {'allow_weekend': True, 'earliest_run_time': '16:30'},
        'universe': {'profile': 'CUSTOM', 'custom_tickers': ['600519', '000001']},
        'candidates': {'max_output': 5},
        'deep_analyzer': {'enable_real_deep_analysis': False},
    })

    # Patch the engine to inject debug output
    original_run = engine.run

    def debug_run(*args, **kwargs):
        result = original_run(*args, **kwargs)
        log("=== AFTER engine.run() ===")
        log(f"dropped_candidates count: {len(result.dropped_candidates)}")
        for i, item in enumerate(result.dropped_candidates):
            if isinstance(item, dict):
                log(f"  [{i}] ticker={item.get('ticker')!r}, company_name={item.get('company_name')!r}")
                log(f"      raw_code={item.get('raw_code')!r}")
        return result

    engine.run = debug_run
    result = engine.run(mode='MVP', trade_date='2026-05-08', enable_deep_analysis=False, persist_outputs=False)

    log("\n=== FINAL RESULT ===")
    for i, item in enumerate(result.dropped_candidates):
        if isinstance(item, dict):
            company = item.get('company_name', 'MISSING')
            hex_val = company.encode('utf-8', errors='replace').hex()
            log(f"  [{i}] ticker={item.get('ticker')!r}, company_name={company!r}, hex={hex_val}")

    # Check the actual resolved names
    from tradingagents.screener.name_resolver import NameResolver
    resolver = NameResolver(trade_date='2026-05-08')
    resolver.load()
    log(f"\nResolver cache['600519'] = {resolver._cache.get('600519', 'NOT_FOUND')!r}")
    log(f"Resolver resolve('600519') = {resolver.resolve('600519')!r}")

    log("\n=== DEBUG FILE ===")
    debug_file = Path.home() / '.tradingagents' / 'logs' / 'screener' / '_name_debug.json'
    if debug_file.exists():
        with open(debug_file, 'r', encoding='utf-8') as df:
            debug_data = json.load(df)
        for k, v in debug_data.items():
            log(f"  {k}: {v!r}")

print("Written to:", out)
