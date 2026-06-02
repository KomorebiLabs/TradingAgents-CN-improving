# Check if the engine injection is actually running
from pathlib import Path
from tradingagents.screener.engine import ScreenerEngine

out = Path.home() / '.tradingagents' / 'cache' / 'screener' / '_line_by_line.txt'
out.parent.mkdir(parents=True, exist_ok=True)

with open(out, 'w', encoding='utf-8') as f:
    def log(msg):
        f.write(msg + '\n')

    engine = ScreenerEngine(config={
        'mode': 'MVP',
        'run_time': {'allow_weekend': True, 'earliest_run_time': '16:30'},
        'universe': {'profile': 'CUSTOM', 'custom_tickers': ['600519', '000001']},
        'candidates': {'max_output': 5},
        'deep_analyzer': {'enable_real_deep_analysis': False},
    })

    result = engine.run(mode='MVP', trade_date='2026-05-08', enable_deep_analysis=False, persist_outputs=False)

    log("=== Checking the result object directly ===")
    dropped = result.dropped_candidates
    for i, item in enumerate(dropped):
        company = item.get('company_name', 'MISSING')
        raw = item.get('raw_code', 'NO_KEY')
        ticker = item.get('ticker', '?')
        hex_val = company.encode('utf-8', errors='replace').hex()
        log(f"[{i}] ticker={ticker!r}, raw_code={raw!r}, company={company!r}, hex={hex_val}")

    log("\n=== What SHOULD resolver.resolve() return ===")
    from tradingagents.screener.name_resolver import NameResolver
    resolver = NameResolver(trade_date='2026-05-08')
    resolver.load()

    for ticker in ['600519', '000001', '600519.SH', '000001.SZ']:
        result_name = resolver.resolve(ticker)
        result_hex = result_name.encode('utf-8', errors='replace').hex()
        log(f"resolver.resolve({ticker!r}) = {result_name!r} (hex={result_hex})")

    log("\n=== Is '600519' in cache? ===")
    log(f"'600519' in cache: {'600519' in resolver._cache}")
    log(f"'000001' in cache: {'000001' in resolver._cache}")
    log(f"cache['600519']: {resolver._cache.get('600519', 'NOT_FOUND')!r}")

    log("\n=== DIAGNOSIS ===")
    log("If company_name='Proxy 600519' but resolver.resolve('600519')='贵州茅台',")
    log("then the injection code in engine.py is NOT executing!")

print("Written to:", out)
