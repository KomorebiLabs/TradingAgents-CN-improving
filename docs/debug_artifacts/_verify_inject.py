# Verify engine name injection for the LATEST run
import json
from pathlib import Path

out = Path.home() / '.tradingagents' / 'cache' / 'screener' / '_engine_inject_check.txt'
out.parent.mkdir(parents=True, exist_ok=True)

with open(out, 'w', encoding='utf-8') as f:
    def log(msg):
        f.write(msg + '\n')

    # Run engine with debug output
    from tradingagents.screener.engine import ScreenerEngine
    import datetime as dt

    # Force a weekday date
    engine = ScreenerEngine(config={
        'mode': 'MVP',
        'run_time': {'allow_weekend': True, 'earliest_run_time': '16:30'},
        'universe': {'profile': 'CUSTOM', 'custom_tickers': ['600519', '000001']},
        'candidates': {'max_output': 5},
        'deep_analyzer': {'enable_real_deep_analysis': False},
    })

    result = engine.run(
        mode='MVP',
        trade_date='2026-05-08',
        enable_deep_analysis=False,
        persist_outputs=False
    )

    log(f"Universe size: {result.universe_size}")
    log(f"Candidates: {len(result.candidates)}")
    log(f"Dropped: {len(result.dropped_candidates)}")
    log(f"Metrics name_source: {result.metrics.get('name_resolver_source', 'NOT_SET')}")
    log(f"Metrics name_warnings: {result.metrics.get('name_resolver_warnings', [])}")

    log("\n=== Dropped Candidates ===")
    for i, item in enumerate(result.dropped_candidates or []):
        ticker = item.get('ticker', '?')
        raw_code = item.get('raw_code', '?')
        company = item.get('company_name', 'MISSING')
        company_hex = company.encode('utf-8', errors='replace').hex()
        f.write(f"  [{i}] ticker={ticker!r}, raw_code={raw_code!r}, company={company!r}, hex={company_hex}\n")

    log("\n=== Candidates ===")
    for i, card in enumerate(result.candidates or []):
        ticker = card.ticker
        raw_code = card.raw_code
        company = card.company_name
        company_hex = company.encode('utf-8', errors='replace').hex()
        f.write(f"  [{i}] ticker={ticker!r}, raw_code={raw_code!r}, company={company!r}, hex={company_hex}\n")

    # Check debug file
    log("\n=== Debug File ===")
    debug_file = Path.home() / '.tradingagents' / 'logs' / 'screener' / '_name_debug.json'
    if debug_file.exists():
        with open(debug_file, 'r', encoding='utf-8') as df:
            debug_data = json.load(df)
        for k, v in debug_data.items():
            f.write(f"  {k}: {v!r}\n")
    else:
        log("  DEBUG FILE NOT FOUND")

print("Written to:", out)
