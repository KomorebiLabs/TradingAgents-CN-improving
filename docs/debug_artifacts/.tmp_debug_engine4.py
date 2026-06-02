import sys
sys.path.insert(0, '.')

# Inject debug print redirection
import builtins
_original_print = builtins.print

from tradingagents.screener.engine import ScreenerEngine

engine = ScreenerEngine(config={
    'mode': 'MVP',
    'run_time': {'allow_weekend': True, 'allow_non_trading_day_override': False, 'earliest_run_time': '16:30', 'latest_next_day': '09:00', 'allow_experimental_intraday': False, 'max_data_age_days': 2},
    'universe': {'profile': 'CUSTOM', 'custom_tickers': ['600519', '000001']},
    'candidates': {'max_output': 5, 'max_output_extended': 7, 'same_sector_limit': 2},
    'deep_analyzer': {'enable_real_deep_analysis': False, 'max_stocks': 3, 'delay_between_stocks': 2.0, 'retry_on_failure': True, 'max_retries': 1},
})
result = engine.run(mode='MVP', trade_date='2026-05-05', enable_deep_analysis=False, persist_outputs=False)

_original_print('=== RESULTS ===')
for item in result.dropped_candidates:
    _original_print(f'  {item.get("ticker")}: company_name={item.get("company_name")!r}')
