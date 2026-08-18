---
name: tests
description: "Skill for the Tests area of TradingAgents-CN-improving. 400 symbols across 67 files."
---

# Tests

400 symbols | 67 files | Cohesion: 84%

## When to Use

- Working with code in `tests/`
- Understanding how portfolio_manager_node, research_manager_node, bear_node work
- Modifying tests-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tests/test_orchestration_logic.py` | test_semantic_instruction_includes_graph_route_decision, test_research_manager_can_request_handoff, test_trader_can_request_handoff, test_risk_can_request_handoff, test_existing_compression_notes_skip_repeat_handoff (+24) |
| `tests/test_security.py` | test_validate_empty_query, test_validate_query_length, test_ignore_instructions_injection, test_system_prompt_injection, test_normal_query (+20) |
| `tradingagents/agents/utils/memory.py` | _tokenize, _get_index_text, _rebuild_index, _update_structured_index, _rebuild_structured_indexes (+19) |
| `tests/test_memory.py` | test_basic_add_and_retrieve, test_add_with_metadata, test_filter_by_field, test_export_and_import, test_structured_index_maintained (+15) |
| `tradingagents/agents/utils/agent_utils.py` | build_screener_semantic_instruction, build_semantic_execution_profile, build_conclusion_template_instruction, enforce_execution_profile_output, enforce_skill_usage (+12) |
| `tests/test_cn_financial_tools.py` | test_normalize_shanghai_symbol, test_normalize_shanghai_symbol_xshg, test_normalize_shenzhen_symbol, test_normalize_shenzhen_symbol_xshe, test_normalize_bj_symbol (+12) |
| `tests/test_memory_manager.py` | test_save_and_load_roundtrip, test_complex_summary_roundtrip, test_within_ttl_returns_entry, test_one_day_over_ttl, test_different_ticker_no_cross_contamination (+11) |
| `tests/test_historical_context_injection.py` | _make_mock_state, test_extracts_ticker_and_trade_date, test_confidence_high_for_buy_decision, test_confidence_low_for_sell_decision, test_confidence_medium_by_default (+8) |
| `tests/test_route_insight_integration.py` | test_route_pattern_learning, test_segment_specific_learning, test_add_situation_with_metadata, test_structured_index_creation, test_structured_query_by_segment (+7) |
| `tests/test_screener_universe.py` | test_build_mvp_universe, test_build_extended_universe, test_build_experimental_universe, test_universe_cache_uses_profile_cache_key, test_build_universe_fails_loudly_when_apis_all_fail (+7) |

## Entry Points

Start here when exploring this area:

- **`portfolio_manager_node`** (Function) — `tradingagents/agents/managers/portfolio_manager.py:147`
- **`research_manager_node`** (Function) — `tradingagents/agents/managers/research_manager.py:120`
- **`bear_node`** (Function) — `tradingagents/agents/researchers/bear_researcher.py:133`
- **`bull_node`** (Function) — `tradingagents/agents/researchers/bull_researcher.py:112`
- **`aggressive_node`** (Function) — `tradingagents/agents/risk_mgmt/aggressive_debater.py:130`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `SmartMoneyAccessReady` | Class | `tests/test_screener_strategy_smart_money.py` | 5 |
| `SmartMoneyAccessDegraded` | Class | `tests/test_screener_strategy_smart_money.py` | 70 |
| `SmartMoneyAccessSpeculative` | Class | `tests/test_screener_strategy_smart_money.py` | 134 |
| `ValuationAccessNoMatch` | Class | `tests/test_screener_strategy_smart_money.py` | 196 |
| `ValuationAccessNone` | Class | `tests/test_screener_strategy_smart_money.py` | 205 |
| `ValuationAccessEmpty` | Class | `tests/test_screener_strategy_smart_money.py` | 212 |
| `FakeAccess` | Class | `tests/test_screener_strategy_technical.py` | 6 |
| `TencentFirstAccess` | Class | `tests/test_screener_strategy_technical.py` | 68 |
| `RiskyStructureAccess` | Class | `tests/test_screener_strategy_technical.py` | 114 |
| `FailureTrendAccess` | Class | `tests/test_screener_strategy_technical.py` | 152 |
| `VolumeAwareAccess` | Class | `tests/test_screener_strategy_technical.py` | 180 |
| `PolicyAccessReady` | Class | `tests/test_screener_strategy_policy.py` | 5 |
| `PolicyAccessDegraded` | Class | `tests/test_screener_strategy_policy.py` | 70 |
| `TailMemberAccess` | Class | `tests/test_screener_strategy_policy.py` | 129 |
| `MultiConceptAccess` | Class | `tests/test_screener_strategy_policy.py` | 157 |
| `portfolio_manager_node` | Function | `tradingagents/agents/managers/portfolio_manager.py` | 147 |
| `research_manager_node` | Function | `tradingagents/agents/managers/research_manager.py` | 120 |
| `bear_node` | Function | `tradingagents/agents/researchers/bear_researcher.py` | 133 |
| `bull_node` | Function | `tradingagents/agents/researchers/bull_researcher.py` | 112 |
| `aggressive_node` | Function | `tradingagents/agents/risk_mgmt/aggressive_debater.py` | 130 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Research_manager_node → _parse_decision_types` | cross_community | 8 |
| `Trader_node → _parse_decision_types` | cross_community | 8 |
| `Aggressive_node → _parse_decision_types` | cross_community | 8 |
| `Aggressive_node → _parse_decision_types` | cross_community | 8 |
| `Bear_node → _parse_decision_types` | cross_community | 8 |
| `Bull_node → _parse_decision_types` | cross_community | 8 |
| `Conservative_node → _parse_decision_types` | cross_community | 8 |
| `Neutral_node → _parse_decision_types` | cross_community | 8 |
| `Portfolio_manager_node → Register` | cross_community | 6 |
| `Portfolio_manager_node → To_prompt_section` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Screener | 15 calls |
| Dataflows | 7 calls |
| Analysts | 6 calls |
| Graph | 3 calls |
| Skills | 1 calls |
| Rag | 1 calls |

## How to Explore

1. `gitnexus_context({name: "portfolio_manager_node"})` — see callers and callees
2. `gitnexus_query({query: "tests"})` — find related execution flows
3. Read key files listed above for implementation details
