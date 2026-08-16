---
name: graph
description: "Skill for the Graph area of TradingAgents-CN-improving. 57 symbols across 9 files."
---

# Graph

57 symbols | 9 files | Cohesion: 76%

## When to Use

- Working with code in `tradingagents/`
- Understanding how create_orchestration_event, append_orchestration_event, build_orchestration_event work
- Modifying graph-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tradingagents/graph/reflection.py` | _extract_event_trail, _format_event_trail, _analyze_route_patterns, generate_route_insight, get_route_summary (+21) |
| `tests/test_reflection_observability.py` | test_get_route_summary_returns_structured_data, test_log_state_writes_orchestration_summary, test_extract_orchestration_context_structured, test_extract_orchestration_context_structured_with_compression, test_extract_orchestration_context_structured_mixed_route (+2) |
| `tradingagents/graph/conditional_logic.py` | _get_route_decision, _resolve_debate_rounds, _debate_route_reason, _resolve_risk_rounds, _risk_route_reason (+1) |
| `tradingagents/graph/trading_graph.py` | propagate, _create_fallback_state, _synchronize_structured_state, _log_state, process_signal |
| `tests/test_orchestration_logic.py` | test_speculative_debate_limit_shortens_bull_bear_cycle, test_policy_top_stock_high_quality_gets_extra_research_round, test_multi_concept_overlap_extends_debate_route, test_risk_debate_exit_stage_skips_repeat_handoff_when_notes_exist |
| `tradingagents/agents/utils/state_helpers.py` | create_orchestration_event, append_orchestration_event, build_orchestration_event, determine_risk_debate_exit_stage |
| `tradingagents/graph/setup.py` | router_node, handoff_node, finalize_node |
| `tests/test_screener_deep_analyzer.py` | test_route_summary_can_be_reflected_into_graph_state |
| `tests/test_harness_state.py` | test_synchronize_structured_state_backfills_blocks |

## Entry Points

Start here when exploring this area:

- **`create_orchestration_event`** (Function) — `tradingagents/agents/utils/state_helpers.py:121`
- **`append_orchestration_event`** (Function) — `tradingagents/agents/utils/state_helpers.py:162`
- **`build_orchestration_event`** (Function) — `tradingagents/agents/utils/state_helpers.py:182`
- **`determine_risk_debate_exit_stage`** (Function) — `tradingagents/agents/utils/state_helpers.py:430`
- **`router_node`** (Function) — `tradingagents/graph/setup.py:89`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `create_orchestration_event` | Function | `tradingagents/agents/utils/state_helpers.py` | 121 |
| `append_orchestration_event` | Function | `tradingagents/agents/utils/state_helpers.py` | 162 |
| `build_orchestration_event` | Function | `tradingagents/agents/utils/state_helpers.py` | 182 |
| `determine_risk_debate_exit_stage` | Function | `tradingagents/agents/utils/state_helpers.py` | 430 |
| `router_node` | Function | `tradingagents/graph/setup.py` | 89 |
| `handoff_node` | Function | `tradingagents/graph/setup.py` | 161 |
| `finalize_node` | Function | `tradingagents/graph/setup.py` | 262 |
| `get_event_position` | Function | `tradingagents/graph/reflection.py` | 559 |
| `test_speculative_debate_limit_shortens_bull_bear_cycle` | Method | `tests/test_orchestration_logic.py` | 397 |
| `test_policy_top_stock_high_quality_gets_extra_research_round` | Method | `tests/test_orchestration_logic.py` | 412 |
| `test_multi_concept_overlap_extends_debate_route` | Method | `tests/test_orchestration_logic.py` | 433 |
| `should_continue_debate` | Method | `tradingagents/graph/conditional_logic.py` | 294 |
| `test_risk_debate_exit_stage_skips_repeat_handoff_when_notes_exist` | Method | `tests/test_orchestration_logic.py` | 557 |
| `test_get_route_summary_returns_structured_data` | Method | `tests/test_reflection_observability.py` | 276 |
| `test_route_summary_can_be_reflected_into_graph_state` | Method | `tests/test_screener_deep_analyzer.py` | 292 |
| `generate_route_insight` | Method | `tradingagents/graph/reflection.py` | 930 |
| `get_route_summary` | Method | `tradingagents/graph/reflection.py` | 980 |
| `reflect_portfolio_manager` | Method | `tradingagents/graph/reflection.py` | 1076 |
| `test_synchronize_structured_state_backfills_blocks` | Method | `tests/test_harness_state.py` | 61 |
| `test_log_state_writes_orchestration_summary` | Method | `tests/test_reflection_observability.py` | 74 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Reflect_portfolio_manager → _safe_int` | cross_community | 6 |
| `Reflect_portfolio_manager → _safe_float` | cross_community | 6 |
| `Reflect_portfolio_manager → _extract_route_decision` | cross_community | 4 |
| `Reflect_portfolio_manager → Get_event_position` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Screener | 4 calls |
| Tests | 3 calls |

## How to Explore

1. `gitnexus_context({name: "create_orchestration_event"})` — see callers and callees
2. `gitnexus_query({query: "graph"})` — find related execution flows
3. Read key files listed above for implementation details
