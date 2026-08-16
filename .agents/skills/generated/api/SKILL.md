---
name: api
description: "Skill for the Api area of TradingAgents-CN-improving. 47 symbols across 7 files."
---

# Api

47 symbols | 7 files | Cohesion: 90%

## When to Use

- Working with code in `reference/`
- Understanding how assistant_message_from_api, get_claude_code_session_id, claude_oauth_betas work
- Modifying api-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `reference/openharness/api/codex_client.py` | _extract_account_id, _build_codex_headers, _convert_messages_to_codex, _convert_tools_to_codex, _usage_from_response (+11) |
| `reference/openharness/api/openai_client.py` | _token_limit_param_for_model, _convert_tools_to_openai, _convert_messages_to_openai, _convert_user_content_to_openai, _convert_assistant_message (+7) |
| `reference/openharness/api/client.py` | _is_retryable, _get_retry_delay, stream_message, _stream_once, _translate_api_error (+3) |
| `reference/openharness/api/errors.py` | OpenHarnessApiError, AuthenticationFailure, RateLimitFailure, RequestFailure |
| `reference/openharness/auth/external.py` | get_claude_code_session_id, claude_oauth_betas, claude_oauth_headers |
| `reference/openharness/tools/image_to_text_tool.py` | execute, _resolve_image, _call_vision_model |
| `reference/openharness/engine/messages.py` | assistant_message_from_api |

## Entry Points

Start here when exploring this area:

- **`assistant_message_from_api`** (Function) — `reference/openharness/engine/messages.py:556`
- **`get_claude_code_session_id`** (Function) — `reference/openharness/auth/external.py:379`
- **`claude_oauth_betas`** (Function) — `reference/openharness/auth/external.py:387`
- **`claude_oauth_headers`** (Function) — `reference/openharness/auth/external.py:401`
- **`OpenHarnessApiError`** (Class) — `reference/openharness/api/errors.py:5`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `OpenHarnessApiError` | Class | `reference/openharness/api/errors.py` | 5 |
| `AuthenticationFailure` | Class | `reference/openharness/api/errors.py` | 9 |
| `RateLimitFailure` | Class | `reference/openharness/api/errors.py` | 13 |
| `RequestFailure` | Class | `reference/openharness/api/errors.py` | 17 |
| `assistant_message_from_api` | Function | `reference/openharness/engine/messages.py` | 556 |
| `get_claude_code_session_id` | Function | `reference/openharness/auth/external.py` | 379 |
| `claude_oauth_betas` | Function | `reference/openharness/auth/external.py` | 387 |
| `claude_oauth_headers` | Function | `reference/openharness/auth/external.py` | 401 |
| `stream_message` | Method | `reference/openharness/api/client.py` | 159 |
| `stream_message` | Method | `reference/openharness/api/openai_client.py` | 243 |
| `execute` | Method | `reference/openharness/tools/image_to_text_tool.py` | 72 |
| `stream_message` | Method | `reference/openharness/api/codex_client.py` | 215 |
| `_extract_account_id` | Function | `reference/openharness/api/codex_client.py` | 29 |
| `_build_codex_headers` | Function | `reference/openharness/api/codex_client.py` | 60 |
| `_convert_messages_to_codex` | Function | `reference/openharness/api/codex_client.py` | 76 |
| `_convert_tools_to_codex` | Function | `reference/openharness/api/codex_client.py` | 119 |
| `_usage_from_response` | Function | `reference/openharness/api/codex_client.py` | 131 |
| `_stop_reason_from_response` | Function | `reference/openharness/api/codex_client.py` | 141 |
| `_format_error_message` | Function | `reference/openharness/api/codex_client.py` | 154 |
| `_format_codex_stream_error` | Function | `reference/openharness/api/codex_client.py` | 174 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Stream_message → Claude_oauth_betas` | cross_community | 5 |
| `Stream_message → Get_claude_code_version` | cross_community | 5 |
| `Stream_message → Get_claude_code_session_id` | cross_community | 5 |
| `Stream_message → _extract_account_id` | cross_community | 4 |
| `Stream_message → _convert_assistant_message` | cross_community | 4 |
| `Stream_message → _convert_user_content_to_openai` | cross_community | 4 |
| `Stream_message → _translate_api_error` | intra_community | 3 |
| `Stream_message → Assistant_message_from_api` | intra_community | 3 |
| `Stream_message → _iter_sse_events` | cross_community | 3 |
| `Stream_message → _convert_messages_to_codex` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Auth | 2 calls |

## How to Explore

1. `gitnexus_context({name: "assistant_message_from_api"})` — see callers and callees
2. `gitnexus_query({query: "api"})` — find related execution flows
3. Read key files listed above for implementation details
