---
name: compact
description: "Skill for the Compact area of TradingAgents-CN-improving. 54 symbols across 3 files."
---

# Compact

54 symbols | 3 files | Cohesion: 81%

## When to Use

- Working with code in `reference/`
- Understanding how sanitize_conversation_messages, estimate_message_tokens, estimate_conversation_tokens work
- Modifying compact-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `reference/openharness/services/compact/__init__.py` | estimate_message_tokens, estimate_conversation_tokens, _vision_token_budget_per_image, _replace_images_with_compaction_placeholders, _sanitize_metadata (+44) |
| `reference/openharness/engine/messages.py` | from_user_text, is_effectively_empty, sanitize_conversation_messages |
| `reference/openharness/services/token_estimation.py` | estimate_tokens, estimate_message_tokens |

## Entry Points

Start here when exploring this area:

- **`sanitize_conversation_messages`** (Function) — `reference/openharness/engine/messages.py:414`
- **`estimate_message_tokens`** (Function) — `reference/openharness/services/compact/__init__.py:115`
- **`estimate_conversation_tokens`** (Function) — `reference/openharness/services/compact/__init__.py:133`
- **`try_context_collapse`** (Function) — `reference/openharness/services/compact/__init__.py:301`
- **`truncate_head_for_ptl_retry`** (Function) — `reference/openharness/services/compact/__init__.py:345`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `sanitize_conversation_messages` | Function | `reference/openharness/engine/messages.py` | 414 |
| `estimate_message_tokens` | Function | `reference/openharness/services/compact/__init__.py` | 115 |
| `estimate_conversation_tokens` | Function | `reference/openharness/services/compact/__init__.py` | 133 |
| `try_context_collapse` | Function | `reference/openharness/services/compact/__init__.py` | 301 |
| `truncate_head_for_ptl_retry` | Function | `reference/openharness/services/compact/__init__.py` | 345 |
| `render_compact_attachment` | Function | `reference/openharness/services/compact/__init__.py` | 416 |
| `create_compact_boundary_message` | Function | `reference/openharness/services/compact/__init__.py` | 423 |
| `build_post_compact_messages` | Function | `reference/openharness/services/compact/__init__.py` | 457 |
| `microcompact_messages` | Function | `reference/openharness/services/compact/__init__.py` | 807 |
| `try_session_memory_compaction` | Function | `reference/openharness/services/compact/__init__.py` | 892 |
| `get_compact_prompt` | Function | `reference/openharness/services/compact/__init__.py` | 976 |
| `format_compact_summary` | Function | `reference/openharness/services/compact/__init__.py` | 985 |
| `build_compact_summary_message` | Function | `reference/openharness/services/compact/__init__.py` | 995 |
| `get_context_window` | Function | `reference/openharness/services/compact/__init__.py` | 1040 |
| `get_autocompact_threshold` | Function | `reference/openharness/services/compact/__init__.py` | 1055 |
| `should_autocompact` | Function | `reference/openharness/services/compact/__init__.py` | 1070 |
| `compact_conversation` | Function | `reference/openharness/services/compact/__init__.py` | 1094 |
| `auto_compact_if_needed` | Function | `reference/openharness/services/compact/__init__.py` | 1457 |
| `summarize_messages` | Function | `reference/openharness/services/compact/__init__.py` | 1642 |
| `compact_messages` | Function | `reference/openharness/services/compact/__init__.py` | 1658 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Auto_compact_if_needed → _read_positive_int_env` | cross_community | 6 |
| `Compact_conversation → _inject_arguments` | cross_community | 4 |
| `Compact_conversation → From_user_text` | cross_community | 4 |
| `Compact_conversation → _parse_hook_json` | cross_community | 4 |
| `Auto_compact_if_needed → _vision_token_budget_per_image` | intra_community | 4 |
| `Auto_compact_if_needed → Estimate_tokens` | intra_community | 4 |
| `Auto_compact_if_needed → Get_context_window` | intra_community | 4 |
| `Try_session_memory_compaction → Is_effectively_empty` | intra_community | 4 |
| `Run_query → From_user_text` | cross_community | 4 |
| `Compact_messages → Is_effectively_empty` | intra_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Hooks | 2 calls |
| Services | 1 calls |

## How to Explore

1. `gitnexus_context({name: "sanitize_conversation_messages"})` — see callers and callees
2. `gitnexus_query({query: "compact"})` — find related execution flows
3. Read key files listed above for implementation details
