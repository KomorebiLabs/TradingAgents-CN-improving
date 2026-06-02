# Ultimate diagnostic: instrument engine.py to log exactly what's happening during injection
import sys
from pathlib import Path

out = Path.home() / '.tradingagents' / 'cache' / 'screener' / '_ultimate_diag.txt'
out.parent.mkdir(parents=True, exist_ok=True)

# Read the actual engine.py source
import tradingagents.screener.engine as eng_mod
import inspect

src = inspect.getsource(eng_mod.ScreenerEngine.run)

# Find the injection section
lines = src.split('\n')
for i, line in enumerate(lines):
    if 'resolver' in line.lower() or 'inject' in line.lower() or 'company_name' in line.lower():
        print(f"  Line offset {i}: {line}", file=sys.stderr)

print("stderr output done", file=sys.stderr)

# Now write all the results to the output file
with open(out, 'w', encoding='utf-8') as f:
    def log(msg):
        f.write(msg + '\n')
        print(msg, file=sys.stderr)

    # Step 1: Check resolver in isolation
    log("=== Step 1: Resolver in isolation ===")
    from tradingagents.screener.name_resolver import NameResolver
    resolver = NameResolver(trade_date='2026-05-08')
    resolver.load()
    log(f"source: {resolver.source}, size: {len(resolver._cache)}")
    log(f"resolve('600519'): {resolver.resolve('600519')!r}")
    log(f"resolve('600519.SH'): {resolver.resolve('600519.SH')!r}")

    # Step 2: Run engine and intercept with a more detailed patch
    log("\n=== Step 2: Engine run with interception ===")
    import tradingagents.screener.engine as mod
    from tradingagents.screener.engine import ScreenerEngine

    # Save original run
    orig_run = ScreenerEngine.run

    def debug_run(self, mode, trade_date=None, enable_deep_analysis=True, persist_outputs=True):
        log("  [PATCH] Entering run(), creating engine instance...")
        result = orig_run(self, mode, trade_date, enable_deep_analysis, persist_outputs)

        log("  [PATCH] After orig_run(), checking results:")
        for i, item in enumerate(result.dropped_candidates):
            if isinstance(item, dict):
                cn = item.get('company_name', 'MISSING')
                rc = item.get('raw_code', 'NO_KEY')
                tick = item.get('ticker', '?')
                log(f"  [PATCH] dropped[{i}]: ticker={tick!r}, raw_code={rc!r}, company={cn!r}")

        log("  [PATCH] Checking result.metrics:")
        log(f"  [PATCH]   name_resolver_source = {result.metrics.get('name_resolver_source', 'NOT_SET')!r}")

        return result

    ScreenerEngine.run = debug_run

    engine = ScreenerEngine(config={
        'mode': 'MVP',
        'run_time': {'allow_weekend': True, 'earliest_run_time': '16:30'},
        'universe': {'profile': 'CUSTOM', 'custom_tickers': ['600519', '000001']},
        'candidates': {'max_output': 5},
        'deep_analyzer': {'enable_real_deep_analysis': False},
    })

    result = engine.run(mode='MVP', trade_date='2026-05-08', enable_deep_analysis=False, persist_outputs=False)

    log("\n=== Step 3: Final check ===")
    for i, item in enumerate(result.dropped_candidates):
        if isinstance(item, dict):
            cn = item.get('company_name', 'MISSING')
            rc = item.get('raw_code', 'NO_KEY')
            tick = item.get('ticker', '?')
            hex_val = cn.encode('utf-8', errors='replace').hex()
            log(f"  dropped[{i}]: ticker={tick!r}, raw_code={rc!r}, company={cn!r}, hex={hex_val}")

    log("\n=== Done ===")

print(f"\nWritten to: {out}")
