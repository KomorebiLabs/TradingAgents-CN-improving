import sys
from tradingagents.screener.engine import ScreenerEngine

engine = ScreenerEngine(config={
    'mode': 'MVP',
    'run_time': {'allow_weekend': True, 'allow_non_trading_day_override': False, 'earliest_run_time': '16:30', 'latest_next_day': '09:00', 'allow_experimental_intraday': False, 'max_data_age_days': 2},
    'universe': {'profile': 'CUSTOM', 'custom_tickers': ['600519', '000001']},
    'candidates': {'max_output': 5, 'max_output_extended': 7, 'same_sector_limit': 2},
    'deep_analyzer': {'enable_real_deep_analysis': False, 'max_stocks': 3, 'delay_between_stocks': 2.0, 'retry_on_failure': True, 'max_retries': 1},
})

# Run without persist to avoid side effects
result = engine.run(mode='MVP', trade_date='2026-05-05', enable_deep_analysis=False, persist_outputs=False)

# Check the actual objects
print("=== Merged Candidates ===")
for card in result.candidates:
    print(f"  ticker={card.ticker!r}, company_name={card.company_name!r}, raw_code={card.raw_code!r}")

print("\n=== Dropped Candidates ===")
for item in result.dropped_candidates:
    print(f"  type={type(item).__name__}, ticker={item.get('ticker')!r}, company_name={item.get('company_name')!r}")

print("\n=== Serialization test ===")
import json
for card in result.candidates:
    d = card.model_dump()
    print(f"  model_dump company_name={d.get('company_name')!r}")

# Check if write_run_artifacts modifies things
print("\n=== Model fields ===")
if result.candidates:
    card = result.candidates[0]
    print(f"  model fields: {list(card.model_fields.keys())}")
    print(f"  __dict__: {card.__dict__.get('company_name')!r}")
