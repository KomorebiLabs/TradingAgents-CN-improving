---
name: impl
description: "Skill for the Impl area of TradingAgents-CN-improving. 214 symbols across 13 files."
---

# Impl

214 symbols | 13 files | Cohesion: 85%

## When to Use

- Working with code in `reference/`
- Understanding how connect, disconnect, on_session_events work
- Modifying impl-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `reference/openharness/channels/impl/mochat.py` | _str_field, _make_synthetic_event, start, _seed_targets_from_config, _normalize_id_list (+47) |
| `reference/openharness/channels/impl/matrix.py` | MatrixChannel, stop, _set_typing, _start_typing_keepalive, loop (+43) |
| `reference/openharness/channels/impl/feishu.py` | _extract_share_card_content, _extract_interactive_content, _extract_element_content, _extract_post_content, _parse_block (+17) |
| `reference/openharness/channels/impl/email.py` | start, _validate_config, EmailChannel, __init__, _fetch_new_messages (+10) |
| `reference/openharness/channels/impl/telegram.py` | _sender_id, _forward_command, _on_message, _flush_media_group, _get_extension (+9) |
| `reference/openharness/channels/impl/discord.py` | DiscordChannel, __init__, _handle_message_create, _should_respond_in_group, _start_typing (+9) |
| `reference/openharness/channels/impl/dingtalk.py` | _on_message, DingTalkChannel, __init__, _get_access_token, _is_http_url (+8) |
| `reference/openharness/channels/impl/slack.py` | SlackChannel, __init__, _on_socket_request, _is_allowed, _should_respond_in_channel (+4) |
| `reference/openharness/channels/impl/qq.py` | on_c2c_message_create, on_direct_message_create, _on_message, QQChannel, __init__ (+3) |
| `reference/openharness/channels/impl/base.py` | _handle_message, resolve_channel_media_dir, BaseChannel, __init__, is_allowed (+1) |

## Entry Points

Start here when exploring this area:

- **`connect`** (Function) — `reference/openharness/channels/impl/mochat.py:367`
- **`disconnect`** (Function) — `reference/openharness/channels/impl/mochat.py:375`
- **`on_session_events`** (Function) — `reference/openharness/channels/impl/mochat.py:387`
- **`on_panel_events`** (Function) — `reference/openharness/channels/impl/mochat.py:391`
- **`handler`** (Function) — `reference/openharness/channels/impl/mochat.py:420`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `BaseChannel` | Class | `reference/openharness/channels/impl/base.py` | 33 |
| `DingTalkChannel` | Class | `reference/openharness/channels/impl/dingtalk.py` | 92 |
| `DiscordChannel` | Class | `reference/openharness/channels/impl/discord.py` | 23 |
| `EmailChannel` | Class | `reference/openharness/channels/impl/email.py` | 26 |
| `FeishuChannel` | Class | `reference/openharness/channels/impl/feishu.py` | 242 |
| `MatrixChannel` | Class | `reference/openharness/channels/impl/matrix.py` | 145 |
| `MochatChannel` | Class | `reference/openharness/channels/impl/mochat.py` | 216 |
| `QQChannel` | Class | `reference/openharness/channels/impl/qq.py` | 50 |
| `SlackChannel` | Class | `reference/openharness/channels/impl/slack.py` | 20 |
| `TelegramChannel` | Class | `reference/openharness/channels/impl/telegram.py` | 86 |
| `WhatsAppChannel` | Class | `reference/openharness/channels/impl/whatsapp.py` | 16 |
| `connect` | Function | `reference/openharness/channels/impl/mochat.py` | 367 |
| `disconnect` | Function | `reference/openharness/channels/impl/mochat.py` | 375 |
| `on_session_events` | Function | `reference/openharness/channels/impl/mochat.py` | 387 |
| `on_panel_events` | Function | `reference/openharness/channels/impl/mochat.py` | 391 |
| `handler` | Function | `reference/openharness/channels/impl/mochat.py` | 420 |
| `normalize_mochat_content` | Function | `reference/openharness/channels/impl/mochat.py` | 108 |
| `extract_mention_ids` | Function | `reference/openharness/channels/impl/mochat.py` | 139 |
| `resolve_was_mentioned` | Function | `reference/openharness/channels/impl/mochat.py` | 157 |
| `resolve_require_mention` | Function | `reference/openharness/channels/impl/mochat.py` | 174 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Start → _str_field` | cross_community | 6 |
| `Start → _post_json` | intra_community | 6 |
| `Start → _socket_call` | cross_community | 5 |
| `Start → _stop_fallback_workers` | intra_community | 4 |
| `Send → _is_http_url` | intra_community | 4 |
| `Send → _guess_filename` | intra_community | 4 |
| `Send → _guess_upload_type` | intra_community | 4 |
| `Send → Start` | intra_community | 4 |
| `Send → Split` | intra_community | 4 |
| `Fetch_messages_between_dates → _html_to_text` | intra_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Commands | 1 calls |

## How to Explore

1. `gitnexus_context({name: "connect"})` — see callers and callees
2. `gitnexus_query({query: "impl"})` — find related execution flows
3. Read key files listed above for implementation details
