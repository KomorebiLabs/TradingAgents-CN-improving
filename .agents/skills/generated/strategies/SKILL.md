---
name: strategies
description: "Skill for the Strategies area of TradingAgents-CN-improving. 71 symbols across 6 files."
---

# Strategies

71 symbols | 6 files | Cohesion: 88%

## When to Use

- Working with code in `tradingagents/`
- Understanding how score_to_exchange, placeholder_name, get_test_context work
- Modifying strategies-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tradingagents/screener/strategies/policy.py` | run, _select_policy_concepts, _concept_heat_score, _build_universe_concept_hits, _pick_best_concept_for_code (+21) |
| `tradingagents/screener/strategies/smart_money.py` | run, _ticker_to_prefixed_symbol, _compute_tick_score, _compute_popularity_score, _compute_tick_persistence_score (+17) |
| `tradingagents/screener/strategies/technical.py` | score_to_exchange, placeholder_name, _technical_concept_tags, _technical_trigger_reason, run (+7) |
| `tests/test_screener_strategy_technical.py` | test_technical_strategy_attaches_yfinance_hist_fallback, test_technical_strategy_prefers_tencent_hist_when_available, test_technical_strategy_flags_extended_structure_risk, test_technical_strategy_exposes_trend_failure_semantics, test_technical_strategy_exposes_volume_quality_metrics |
| `tests/strategies/conftest.py` | ensure_data_dir, get_test_context, test_context, run, report |
| `tests/test_smoke.py` | test_run_all_smoke_tests |

## Entry Points

Start here when exploring this area:

- **`score_to_exchange`** (Function) — `tradingagents/screener/strategies/technical.py:27`
- **`placeholder_name`** (Function) — `tradingagents/screener/strategies/technical.py:37`
- **`get_test_context`** (Function) — `tests/strategies/conftest.py:123`
- **`test_context`** (Function) — `tests/strategies/conftest.py:142`
- **`test_run_all_smoke_tests`** (Function) — `tests/test_smoke.py:190`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `score_to_exchange` | Function | `tradingagents/screener/strategies/technical.py` | 27 |
| `placeholder_name` | Function | `tradingagents/screener/strategies/technical.py` | 37 |
| `get_test_context` | Function | `tests/strategies/conftest.py` | 123 |
| `test_context` | Function | `tests/strategies/conftest.py` | 142 |
| `test_run_all_smoke_tests` | Function | `tests/test_smoke.py` | 190 |
| `run` | Method | `tradingagents/screener/strategies/policy.py` | 41 |
| `run` | Method | `tradingagents/screener/strategies/smart_money.py` | 32 |
| `test_technical_strategy_attaches_yfinance_hist_fallback` | Method | `tests/test_screener_strategy_technical.py` | 36 |
| `test_technical_strategy_prefers_tencent_hist_when_available` | Method | `tests/test_screener_strategy_technical.py` | 67 |
| `test_technical_strategy_flags_extended_structure_risk` | Method | `tests/test_screener_strategy_technical.py` | 113 |
| `test_technical_strategy_exposes_trend_failure_semantics` | Method | `tests/test_screener_strategy_technical.py` | 151 |
| `test_technical_strategy_exposes_volume_quality_metrics` | Method | `tests/test_screener_strategy_technical.py` | 179 |
| `run` | Method | `tradingagents/screener/strategies/technical.py` | 78 |
| `ensure_data_dir` | Method | `tests/strategies/conftest.py` | 114 |
| `run` | Method | `tests/strategies/conftest.py` | 291 |
| `report` | Method | `tests/strategies/conftest.py` | 312 |
| `_technical_concept_tags` | Function | `tradingagents/screener/strategies/technical.py` | 46 |
| `_technical_trigger_reason` | Function | `tradingagents/screener/strategies/technical.py` | 57 |
| `_select_policy_concepts` | Method | `tradingagents/screener/strategies/policy.py` | 359 |
| `_concept_heat_score` | Method | `tradingagents/screener/strategies/policy.py` | 391 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Run → _count_recent_trend_failures` | cross_community | 4 |
| `Run → _safe_float` | intra_community | 4 |
| `Run → Guess_exchange_suffix` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Screener | 10 calls |

## How to Explore

1. `gitnexus_context({name: "score_to_exchange"})` — see callers and callees
2. `gitnexus_query({query: "strategies"})` — find related execution flows
3. Read key files listed above for implementation details
