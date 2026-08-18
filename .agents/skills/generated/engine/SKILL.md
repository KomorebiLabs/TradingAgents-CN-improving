---
name: engine
description: "Skill for the Engine area of TradingAgents-CN-improving. 48 symbols across 12 files."
---

# Engine

48 symbols | 12 files | Cohesion: 79%

## When to Use

- Working with code in `reference/`
- Understanding how run_query, is_model_multimodal, get_coordinator_user_context work
- Modifying engine-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `reference/openharness/engine/query.py` | _is_prompt_too_long_error, _bounded_completion_tokens, _extract_completion_token_limit, _is_completion_token_limit_error, run_query (+22) |
| `tests/harness/engine/test_callbacks.py` | test_callback_extracts_from_llm_output, test_callback_extracts_from_usage_metadata, test_callback_extracts_from_direct_attributes, test_callback_accumulates_across_calls |
| `reference/openharness/engine/query_engine.py` | continue_pending, _build_coordinator_context_message, submit_message |
| `reference/openharness/tools/base.py` | execute, is_read_only, get |
| `tests/harness/test_integration.py` | test_full_pipeline_cost_tracker, test_cost_tracker_with_legacy_llm_output |
| `tests/harness/engine/test_cost_tracker.py` | test_cost_tracker_add_single, test_cost_tracker_accumulates |
| `reference/openharness/engine/messages.py` | to_api_param, serialize_content_block |
| `reference/openharness/api/client.py` | stream_message |
| `reference/openharness/api/provider.py` | is_model_multimodal |
| `reference/openharness/coordinator/coordinator_mode.py` | get_coordinator_user_context |

## Entry Points

Start here when exploring this area:

- **`run_query`** (Function) — `reference/openharness/engine/query.py:1196`
- **`is_model_multimodal`** (Function) — `reference/openharness/api/provider.py:174`
- **`get_coordinator_user_context`** (Function) — `reference/openharness/coordinator/coordinator_mode.py:376`
- **`remember_user_goal`** (Function) — `reference/openharness/engine/query.py:488`
- **`test_callback_extracts_from_llm_output`** (Function) — `tests/harness/engine/test_callbacks.py:14`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `run_query` | Function | `reference/openharness/engine/query.py` | 1196 |
| `is_model_multimodal` | Function | `reference/openharness/api/provider.py` | 174 |
| `get_coordinator_user_context` | Function | `reference/openharness/coordinator/coordinator_mode.py` | 376 |
| `remember_user_goal` | Function | `reference/openharness/engine/query.py` | 488 |
| `test_callback_extracts_from_llm_output` | Function | `tests/harness/engine/test_callbacks.py` | 14 |
| `test_callback_extracts_from_usage_metadata` | Function | `tests/harness/engine/test_callbacks.py` | 25 |
| `test_callback_extracts_from_direct_attributes` | Function | `tests/harness/engine/test_callbacks.py` | 34 |
| `test_callback_accumulates_across_calls` | Function | `tests/harness/engine/test_callbacks.py` | 43 |
| `test_full_pipeline_cost_tracker` | Function | `tests/harness/test_integration.py` | 27 |
| `test_cost_tracker_with_legacy_llm_output` | Function | `tests/harness/test_integration.py` | 181 |
| `test_cost_tracker_add_single` | Function | `tests/harness/engine/test_cost_tracker.py` | 13 |
| `test_cost_tracker_accumulates` | Function | `tests/harness/engine/test_cost_tracker.py` | 21 |
| `serialize_content_block` | Function | `reference/openharness/engine/messages.py` | 497 |
| `stream_message` | Method | `reference/openharness/api/client.py` | 81 |
| `continue_pending` | Method | `reference/openharness/engine/query_engine.py` | 569 |
| `execute` | Method | `reference/openharness/tools/base.py` | 42 |
| `is_read_only` | Method | `reference/openharness/tools/base.py` | 45 |
| `get` | Method | `reference/openharness/tools/base.py` | 69 |
| `submit_message` | Method | `reference/openharness/engine/query_engine.py` | 412 |
| `on_llm_end` | Method | `tradingagents/harness/engine/callbacks.py` | 13 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Run_query → Detect_platform` | cross_community | 8 |
| `Run_query → Get_docker_sandbox` | cross_community | 5 |
| `Run_query → _cleanup_after_exit` | cross_community | 5 |
| `Run_query → _inject_arguments` | cross_community | 4 |
| `Run_query → From_user_text` | cross_community | 4 |
| `Run_query → _parse_hook_json` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Hooks | 4 calls |
| Compact | 3 calls |
| Openharness | 1 calls |
| Permissions | 1 calls |
| Services | 1 calls |
| Ui | 1 calls |

## How to Explore

1. `gitnexus_context({name: "run_query"})` — see callers and callees
2. `gitnexus_query({query: "engine"})` — find related execution flows
3. Read key files listed above for implementation details
