import sys
from tradingagents.screener.name_resolver import NameResolver

_original_load = NameResolver.load

def _patched_load(self):
    import sys as _sys
    print(f"[DEBUG] load called, trade_date={self._trade_date}, source={self._source}", file=_sys.stderr)
    result = _original_load(self)
    print(f"[DEBUG] loaded, source={self._source}, cache_size={len(self._cache)}", file=_sys.stderr)
    print(f"[DEBUG] resolve_600519={self.resolve('600519')!r}", file=_sys.stderr)
    return result

NameResolver.load = _patched_load

# Now import engine (which will use the patched class)
from tradingagents.screener.engine import ScreenerEngine

engine = ScreenerEngine(config={
    'mode': 'MVP',
    'run_time': {'allow_weekend': True, 'allow_non_trading_day_override': False, 'earliest_run_time': '16:30', 'latest_next_day': '09:00', 'allow_experimental_intraday': False, 'max_data_age_days': 2},
    'universe': {'profile': 'CUSTOM', 'custom_tickers': ['600519', '000001']},
    'candidates': {'max_output': 5, 'max_output_extended': 7, 'same_sector_limit': 2},
    'deep_analyzer': {'enable_real_deep_analysis': False, 'max_stocks': 3, 'delay_between_stocks': 2.0, 'retry_on_failure': True, 'max_retries': 1},
})
print("[DEBUG] Engine created, running...", file=sys.stderr)
result = engine.run(mode='MVP', trade_date='2026-05-05', enable_deep_analysis=False, persist_outputs=False)
print(f"[DEBUG] dropped[0] company_name={result.dropped_candidates[0].get('company_name') if result.dropped_candidates else 'N/A'}", file=sys.stderr)
