# Monkey-patch the engine to log every step of name injection
from pathlib import Path
import sys

out = Path.home() / '.tradingagents' / 'cache' / 'screener' / '_monkey_debug.txt'
out.parent.mkdir(parents=True, exist_ok=True)

# Patch the engine module BEFORE importing ScreenerEngine
import tradingagents.screener.engine as eng_module
from tradingagents.screener.engine import ScreenerEngine

original_run = ScreenerEngine.run

def patched_run(self, mode, trade_date=None, enable_deep_analysis=True, persist_outputs=True):
    with open(out, 'w', encoding='utf-8') as f:
        f.write("=== Monkey patch: entering run() ===\n")

    # Call the original method
    result = original_run(self, mode, trade_date, enable_deep_analysis, persist_outputs)

    with open(out, 'a', encoding='utf-8') as f:
        f.write(f"=== After original run() ===\n")
        f.write(f"dropped type: {type(result.dropped_candidates)}\n")
        f.write(f"dropped len: {len(result.dropped_candidates)}\n")

        for i, item in enumerate(result.dropped_candidates):
            f.write(f"  [{i}] type={type(item).__name__}\n")
            if isinstance(item, dict):
                f.write(f"      keys: {list(item.keys())}\n")
                for k, v in item.items():
                    v_repr = repr(v)[:100]
                    f.write(f"      {k} = {v_repr}\n")
            elif hasattr(item, '__dict__'):
                f.write(f"      __dict__: {item.__dict__}\n")

        f.write(f"\nMetrics name_resolver_source: {result.metrics.get('name_resolver_source', 'NOT_SET')}\n")
        f.write(f"Metrics name_resolver_warnings: {result.metrics.get('name_resolver_warnings', [])}\n")

    return result

ScreenerEngine.run = patched_run

# Now run the engine
with open(out, 'a', encoding='utf-8') as f:
    f.write("\n=== Running ScreenerEngine ===\n")

engine = ScreenerEngine(config={
    'mode': 'MVP',
    'run_time': {'allow_weekend': True, 'earliest_run_time': '16:30'},
    'universe': {'profile': 'CUSTOM', 'custom_tickers': ['600519', '000001']},
    'candidates': {'max_output': 5},
    'deep_analyzer': {'enable_real_deep_analysis': False},
})

result = engine.run(mode='MVP', trade_date='2026-05-08', enable_deep_analysis=False, persist_outputs=False)

with open(out, 'a', encoding='utf-8') as f:
    f.write("\n=== FINAL RESULT ===\n")
    for i, item in enumerate(result.dropped_candidates):
        company = item.get('company_name', 'MISSING')
        raw = item.get('raw_code', 'NO_KEY')
        hex_val = company.encode('utf-8', errors='replace').hex()
        f.write(f"  [{i}] company={company!r}, hex={hex_val}, raw_code={raw!r}\n")

print("Written to:", out)
