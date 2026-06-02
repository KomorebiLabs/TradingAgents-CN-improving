# Check what types are in dropped_candidates
import json
from pathlib import Path
from tradingagents.screener.engine import ScreenerEngine

out = Path.home() / '.tradingagents' / 'cache' / 'screener' / '_type_check.txt'
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

    result = engine.run(
        mode='MVP',
        trade_date='2026-05-08',
        enable_deep_analysis=False,
        persist_outputs=False
    )

    log("dropped_candidates type check:")
    dropped = result.dropped_candidates
    log(f"  type: {type(dropped)}")
    log(f"  len: {len(dropped) if dropped else 0}")
    for i, item in enumerate(dropped or []):
        log(f"  [{i}] type={type(item).__name__}")
        if hasattr(item, '__dict__'):
            log(f"      __dict__: {item.__dict__}")
        elif isinstance(item, dict):
            log(f"      keys: {list(item.keys())}")
        else:
            log(f"      repr: {repr(item)[:200]}")
        # Check what attributes/items exist
        if hasattr(item, 'raw_code'):
            log(f"      raw_code: {item.raw_code!r}")
        if hasattr(item, 'ticker'):
            log(f"      ticker: {item.ticker!r}")

        # The issue: is 'company_name' being set on SignalCard or dict?
        if hasattr(item, 'company_name'):
            log(f"      company_name BEFORE injection: {item.company_name!r}")

    # Now check: what does _strip_suffix return for "600519.SH"?
    def _strip_suffix(code):
        if "." in code:
            code = code.split(".")[0]
        return code

    log(f"\n_strip_suffix('600519.SH') = {_strip_suffix('600519.SH')!r}")
    log(f"_strip_suffix('000001.SZ') = {_strip_suffix('000001.SZ')!r}")

print("Written to:", out)
