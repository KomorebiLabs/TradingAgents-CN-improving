---
name: auth
description: "Skill for the Auth area of TradingAgents-CN-improving. 148 symbols across 22 files."
---

# Auth

148 symbols | 22 files | Cohesion: 85%

## When to Use

- Working with code in `reference/`
- Understanding how copilot_api_base, save_copilot_auth, load_copilot_auth work
- Modifying auth-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `reference/openharness/commands/registry.py` | _coerce_setting_value, _status_handler, _context_handler, _cost_handler, _stats_handler (+23) |
| `reference/openharness/cli.py` | mcp_add, mcp_remove, plugin_list, _default_credential_slot_for_profile, _ensure_preset_profile (+15) |
| `reference/openharness/auth/external.py` | load_external_credential, _load_codex_credential, describe_external_binding, is_credential_expired, is_third_party_anthropic_endpoint (+14) |
| `reference/openharness/auth/manager.py` | _provider_from_settings, get_active_provider, get_active_profile, list_profiles, get_auth_source_statuses (+13) |
| `reference/openharness/auth/storage.py` | load_credential, load_external_binding, _creds_lock_path, _creds_path, _load_creds_file (+10) |
| `reference/openharness/api/copilot_auth.py` | copilot_api_base, api_base, _auth_file_path, save_copilot_auth, load_copilot_auth (+4) |
| `reference/openharness/auth/flows.py` | run, _try_open_browser, run, run, AuthFlow (+3) |
| `reference/openharness/config/settings.py` | builtin_provider_profile_names, auth_source_provider_name, auth_source_uses_api_key, credential_storage_provider_name, resolve_api_key (+3) |
| `reference/openharness/services/session_backend.py` | get_session_dir, save_snapshot, export_markdown |
| `reference/openharness/api/provider.py` | detect_provider, auth_status |

## Entry Points

Start here when exploring this area:

- **`copilot_api_base`** (Function) — `reference/openharness/api/copilot_auth.py:47`
- **`save_copilot_auth`** (Function) — `reference/openharness/api/copilot_auth.py:96`
- **`load_copilot_auth`** (Function) — `reference/openharness/api/copilot_auth.py:110`
- **`load_github_token`** (Function) — `reference/openharness/api/copilot_auth.py:133`
- **`clear_github_token`** (Function) — `reference/openharness/api/copilot_auth.py:139`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `AuthFlow` | Class | `reference/openharness/auth/flows.py` | 20 |
| `ApiKeyFlow` | Class | `reference/openharness/auth/flows.py` | 33 |
| `DeviceCodeFlow` | Class | `reference/openharness/auth/flows.py` | 54 |
| `BrowserFlow` | Class | `reference/openharness/auth/flows.py` | 166 |
| `copilot_api_base` | Function | `reference/openharness/api/copilot_auth.py` | 47 |
| `save_copilot_auth` | Function | `reference/openharness/api/copilot_auth.py` | 96 |
| `load_copilot_auth` | Function | `reference/openharness/api/copilot_auth.py` | 110 |
| `load_github_token` | Function | `reference/openharness/api/copilot_auth.py` | 133 |
| `clear_github_token` | Function | `reference/openharness/api/copilot_auth.py` | 139 |
| `detect_provider` | Function | `reference/openharness/api/provider.py` | 41 |
| `auth_status` | Function | `reference/openharness/api/provider.py` | 96 |
| `detect_provider_from_registry` | Function | `reference/openharness/api/registry.py` | 407 |
| `load_external_credential` | Function | `reference/openharness/auth/external.py` | 115 |
| `describe_external_binding` | Function | `reference/openharness/auth/external.py` | 294 |
| `is_credential_expired` | Function | `reference/openharness/auth/external.py` | 344 |
| `is_third_party_anthropic_endpoint` | Function | `reference/openharness/auth/external.py` | 557 |
| `load_credential` | Function | `reference/openharness/auth/storage.py` | 146 |
| `load_external_binding` | Function | `reference/openharness/auth/storage.py` | 207 |
| `mcp_add` | Function | `reference/openharness/cli.py` | 800 |
| `mcp_remove` | Function | `reference/openharness/cli.py` | 821 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Execute → Default_provider_profiles` | cross_community | 8 |
| `Execute → _slugify_profile_name` | cross_community | 7 |
| `Get_all_agent_definitions → _slugify_profile_name` | cross_community | 7 |
| `Execute → Get_config_dir` | cross_community | 6 |
| `Execute → Default_auth_source_for_provider` | cross_community | 6 |
| `Execute → Strip_ansi_escape_sequences` | cross_community | 6 |
| `Execute → _parse_bool_env` | cross_community | 6 |
| `Spawn → Get_config_dir` | cross_community | 6 |
| `Get_all_agent_definitions → Default_provider_profiles` | cross_community | 6 |
| `Get_all_agent_definitions → Default_auth_source_for_provider` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Config | 11 calls |
| Openharness | 6 calls |
| Commands | 6 calls |
| Ui | 5 calls |
| Services | 4 calls |
| Autopilot | 4 calls |

## How to Explore

1. `gitnexus_context({name: "copilot_api_base"})` — see callers and callees
2. `gitnexus_query({query: "auth"})` — find related execution flows
3. Read key files listed above for implementation details
