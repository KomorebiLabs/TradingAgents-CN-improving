import json
import sys
from datetime import datetime

# Redirect stderr to a file to avoid mixing with progress bars
log_file = open('.tmp_resolver_log.txt', 'w', encoding='utf-8')
sys.stderr = log_file

from tradingagents.screener.engine import ScreenerEngine

engine = ScreenerEngine(config={
    'mode': 'MVP',
    'run_time': {'allow_weekend': True, 'allow_non_trading_day_override': False, 'earliest_run_time': '16:30', 'latest_next_day': '09:00', 'allow_experimental_intraday': False, 'max_data_age_days': 2},
    'universe': {'profile': 'CUSTOM', 'custom_tickers': ['600519', '000001']},
    'candidates': {'max_output': 5, 'max_output_extended': 7, 'same_sector_limit': 2},
    'deep_analyzer': {'enable_real_deep_analysis': False, 'max_stocks': 3, 'delay_between_stocks': 2.0, 'retry_on_failure': True, 'max_retries': 1},
})

result = engine.run(mode='MVP', trade_date='2026-05-05', enable_deep_analysis=False, persist_outputs=False)

log_file.close()
sys.stderr = sys.__stderr__

# Now read the log file
with open('.tmp_resolver_log.txt', encoding='utf-8') as f:
    content = f.read()

# Print just the important lines
for line in content.split('\n'):
    if 'resolver' in line.lower() or 'name' in line.lower() or '=== ' in line:
        print(line)
