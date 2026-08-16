---
name: screener
description: "Skill for the Screener area of TradingAgents-CN-improving. 211 symbols across 25 files."
---

# Screener

211 symbols | 25 files | Cohesion: 85%

## When to Use

- Working with code in `tradingagents/`
- Understanding how clean_cell, patch_requests_browser_headers, print_probe_table work
- Modifying screener-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tradingagents/screener/data_access.py` | _safe_float, fetch_hist, fetch_tencent_hist, fetch_yfinance_hist, fetch_spot_snapshot (+59) |
| `tradingagents/screener/merger.py` | _find_signal_metrics, _pick_policy_selection_tag, _pick_capital_quality_tag, _pick_capital_quality_summary, _pick_technical_metrics (+23) |
| `tradingagents/screener/report.py` | _render_dropped_reason_card, _deep_route_summary, _render_trigger_route_card, _resolve_output_dir, render_markdown_report (+6) |
| `tradingagents/screener/engine.py` | _extract_strategy_thresholds, _summarize_drop_reasons, _build_strategies, _build_data_access, _build_deep_analyzer (+5) |
| `cli/screener/app.py` | _print_welcome, _print_step_progress, _print_step_header, _prompt_mode, _prompt_date (+5) |
| `tradingagents/screener/name_resolver.py` | _is_valid_chinese_name, _get_cache_root, _date_tag, _cache_path, _load_from_cache (+5) |
| `cli/screener/run_impl.py` | _load_tickers_from_file, _resolve_tickers, _build_cli_config, _resolve_output_dir, run_screener (+5) |
| `tests/test_screener_merger.py` | test_strong_policy_cannot_fully_override_severe_technical_and_speculative_conflict, test_strong_technical_but_weak_policy_fallback_loses_to_core_semantic_candidate, test_cross_strategy_alignment_bonus_beats_higher_but_divergent_raw_score, test_cross_strategy_conflict_is_written_into_drop_summary, test_weak_policy_under_technical_stress_is_explicitly_discounted (+4) |
| `tradingagents/screener/deep_analyzer.py` | analyze, analyze_top_candidates, _build_graph_config_snapshot, _build_semantic_context, _build_route_decision (+4) |
| `tradingagents/screener/universe.py` | get_screener_cache_dir, load_universe_cache, save_universe_cache, _get_da, _build_focused_universe (+4) |

## Entry Points

Start here when exploring this area:

- **`clean_cell`** (Function) — `tradingagents/screener/data_access.py:1061`
- **`patch_requests_browser_headers`** (Function) — `tradingagents/screener/http_spoof.py:24`
- **`print_probe_table`** (Function) — `tradingagents/ui/screener_console.py:133`
- **`test_st_flagged_when_name_is_placeholder`** (Function) — `tests/test_screener_merger.py:783`
- **`merge_signal_cards`** (Function) — `tradingagents/screener/merger.py:879`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `clean_cell` | Function | `tradingagents/screener/data_access.py` | 1061 |
| `patch_requests_browser_headers` | Function | `tradingagents/screener/http_spoof.py` | 24 |
| `print_probe_table` | Function | `tradingagents/ui/screener_console.py` | 133 |
| `test_st_flagged_when_name_is_placeholder` | Function | `tests/test_screener_merger.py` | 783 |
| `merge_signal_cards` | Function | `tradingagents/screener/merger.py` | 879 |
| `test_smoke_screener_end_to_end` | Function | `tests/test_integration_smoke.py` | 39 |
| `validate_screener_run` | Function | `tradingagents/screener/runtime_guard.py` | 78 |
| `check_data_consistency` | Function | `tradingagents/screener/runtime_guard.py` | 86 |
| `print_stage_header` | Function | `tradingagents/ui/screener_console.py` | 30 |
| `print_header_banner` | Function | `tradingagents/ui/screener_console.py` | 59 |
| `print_completion_banner` | Function | `tradingagents/ui/screener_console.py` | 74 |
| `run` | Function | `cli/screener/app.py` | 369 |
| `build_graph_config` | Function | `tradingagents/screener/config.py` | 343 |
| `render_markdown_report` | Function | `tradingagents/screener/report.py` | 177 |
| `write_run_artifacts` | Function | `tradingagents/screener/report.py` | 392 |
| `get_screener_cache_dir` | Function | `tradingagents/screener/universe.py` | 38 |
| `load_universe_cache` | Function | `tradingagents/screener/universe.py` | 56 |
| `save_universe_cache` | Function | `tradingagents/screener/universe.py` | 67 |
| `guess_exchange_suffix` | Function | `tradingagents/screener/universe.py` | 22 |
| `format_ticker` | Function | `tradingagents/screener/universe.py` | 33 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Reflect_portfolio_manager → _safe_int` | cross_community | 6 |
| `Reflect_portfolio_manager → _safe_float` | cross_community | 6 |
| `Main → _print_welcome` | cross_community | 5 |
| `Run → _print_step_progress` | intra_community | 4 |
| `Fetch_hist → _sleep_for_vendor` | intra_community | 4 |
| `Fetch_hist → _vendors_config` | intra_community | 4 |
| `Fetch_hist → Patch_requests_browser_headers` | intra_community | 4 |
| `Run → Print_progress_bar` | cross_community | 4 |
| `Run → Clear_progress_line` | cross_community | 4 |
| `Fetch_spot_snapshot → _sleep_for_vendor` | intra_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 6 calls |
| Ui | 1 calls |

## How to Explore

1. `gitnexus_context({name: "clean_cell"})` — see callers and callees
2. `gitnexus_query({query: "screener"})` — find related execution flows
3. Read key files listed above for implementation details
