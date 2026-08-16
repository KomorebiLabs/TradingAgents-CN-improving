---
name: openharness
description: "Skill for the Openharness area of TradingAgents-CN-improving. 46 symbols across 10 files."
---

# Openharness

46 symbols | 10 files | Cohesion: 65%

## When to Use

- Working with code in `reference/`
- Understanding how default_auth_source_for_provider, mcp_list, load_mcp_server_configs work
- Modifying openharness-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `reference/openharness/cli.py` | _can_use_questionary, _select_with_questionary, _text_prompt, _secret_prompt, _select_from_menu (+27) |
| `reference/openharness/services/session_storage.py` | _sanitize_snapshot_payload, load_session_snapshot, load_session_by_id |
| `reference/openharness/services/cron_scheduler.py` | _run_daemon, scheduler_status |
| `reference/openharness/platforms.py` | detect_platform, get_platform |
| `reference/openharness/utils/shell.py` | resolve_shell_command, _wrap_command_with_script |
| `reference/openharness/config/settings.py` | default_auth_source_for_provider |
| `reference/openharness/mcp/config.py` | load_mcp_server_configs |
| `reference/openharness/tools/base.py` | to_api_schema |
| `reference/openharness/config/paths.py` | get_logs_dir |
| `reference/openharness/auth/external.py` | default_binding_for_provider |

## Entry Points

Start here when exploring this area:

- **`default_auth_source_for_provider`** (Function) — `reference/openharness/config/settings.py:368`
- **`mcp_list`** (Function) — `reference/openharness/cli.py:782`
- **`load_mcp_server_configs`** (Function) — `reference/openharness/mcp/config.py:7`
- **`autopilot_list_cmd`** (Function) — `reference/openharness/cli.py:1029`
- **`main`** (Function) — `reference/openharness/cli.py:2057`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `default_auth_source_for_provider` | Function | `reference/openharness/config/settings.py` | 368 |
| `mcp_list` | Function | `reference/openharness/cli.py` | 782 |
| `load_mcp_server_configs` | Function | `reference/openharness/mcp/config.py` | 7 |
| `autopilot_list_cmd` | Function | `reference/openharness/cli.py` | 1029 |
| `main` | Function | `reference/openharness/cli.py` | 2057 |
| `load_session_snapshot` | Function | `reference/openharness/services/session_storage.py` | 122 |
| `load_session_by_id` | Function | `reference/openharness/services/session_storage.py` | 193 |
| `cron_status_cmd` | Function | `reference/openharness/cli.py` | 905 |
| `cron_logs_cmd` | Function | `reference/openharness/cli.py` | 976 |
| `get_logs_dir` | Function | `reference/openharness/config/paths.py` | 53 |
| `scheduler_status` | Function | `reference/openharness/services/cron_scheduler.py` | 344 |
| `default_binding_for_provider` | Function | `reference/openharness/auth/external.py` | 75 |
| `auth_codex_login` | Function | `reference/openharness/cli.py` | 1907 |
| `auth_claude_login` | Function | `reference/openharness/cli.py` | 1913 |
| `detect_platform` | Function | `reference/openharness/platforms.py` | 26 |
| `get_platform` | Function | `reference/openharness/platforms.py` | 49 |
| `resolve_shell_command` | Function | `reference/openharness/utils/shell.py` | 15 |
| `to_api_schema` | Method | `reference/openharness/tools/base.py` | 77 |
| `_can_use_questionary` | Function | `reference/openharness/cli.py` | 1252 |
| `_select_with_questionary` | Function | `reference/openharness/cli.py` | 1265 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Run_query → Detect_platform` | cross_community | 8 |
| `Spawn → Detect_platform` | cross_community | 7 |
| `Execute → Default_auth_source_for_provider` | cross_community | 6 |
| `Execute → Detect_platform` | cross_community | 6 |
| `Get_all_agent_definitions → Default_auth_source_for_provider` | cross_community | 6 |
| `Wrap_command_for_sandbox → Detect_platform` | cross_community | 5 |
| `Main → Get_config_dir` | cross_community | 4 |
| `Main → Default_provider_profiles` | cross_community | 4 |
| `Main → Default_auth_source_for_provider` | cross_community | 4 |
| `Main → Strip_ansi_escape_sequences` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Auth | 11 calls |
| Services | 7 calls |
| Ui | 5 calls |
| Config | 2 calls |
| Autopilot | 2 calls |
| Prompts | 1 calls |
| Commands | 1 calls |
| Compact | 1 calls |

## How to Explore

1. `gitnexus_context({name: "default_auth_source_for_provider"})` — see callers and callees
2. `gitnexus_query({query: "openharness"})` — find related execution flows
3. Read key files listed above for implementation details
