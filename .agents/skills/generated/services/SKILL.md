---
name: services
description: "Skill for the Services area of TradingAgents-CN-improving. 55 symbols across 15 files."
---

# Services

55 symbols | 15 files | Cohesion: 74%

## When to Use

- Working with code in `reference/`
- Understanding how cron_list_cmd, cron_toggle_cmd, get_cron_registry_path work
- Modifying services-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `reference/openharness/services/cron_scheduler.py` | read_pid, is_scheduler_running, stop_scheduler, start_daemon, get_history_path (+8) |
| `reference/openharness/services/cron.py` | _cron_lock_path, load_cron_jobs, save_cron_jobs, validate_cron_expression, next_run_time (+4) |
| `reference/openharness/services/session_storage.py` | _sanitize_metadata, _persistable_tool_metadata, get_project_session_dir, save_session_snapshot, list_session_snapshots (+1) |
| `reference/openharness/cli.py` | cron_list_cmd, cron_toggle_cmd, cron_start, cron_stop, cron_history_cmd |
| `reference/openharness/services/tool_outputs.py` | _read_positive_int_env, tool_output_inline_chars, tool_output_preview_chars, microcompact_tool_result_chars, is_microcompactable_tool_result |
| `reference/openharness/utils/file_lock.py` | exclusive_file_lock, _exclusive_posix_lock, _exclusive_windows_lock |
| `reference/openharness/engine/query.py` | _tool_artifact_dir, _safe_tool_artifact_name, _offload_tool_output_if_needed |
| `reference/openharness/services/session_backend.py` | load_latest, list_snapshots, load_by_id |
| `reference/openharness/config/paths.py` | get_cron_registry_path, get_sessions_dir |
| `reference/openharness/tools/cron_create_tool.py` | execute |

## Entry Points

Start here when exploring this area:

- **`cron_list_cmd`** (Function) — `reference/openharness/cli.py:917`
- **`cron_toggle_cmd`** (Function) — `reference/openharness/cli.py:938`
- **`get_cron_registry_path`** (Function) — `reference/openharness/config/paths.py:96`
- **`load_cron_jobs`** (Function) — `reference/openharness/services/cron.py:21`
- **`save_cron_jobs`** (Function) — `reference/openharness/services/cron.py:33`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `cron_list_cmd` | Function | `reference/openharness/cli.py` | 917 |
| `cron_toggle_cmd` | Function | `reference/openharness/cli.py` | 938 |
| `get_cron_registry_path` | Function | `reference/openharness/config/paths.py` | 96 |
| `load_cron_jobs` | Function | `reference/openharness/services/cron.py` | 21 |
| `save_cron_jobs` | Function | `reference/openharness/services/cron.py` | 33 |
| `validate_cron_expression` | Function | `reference/openharness/services/cron.py` | 41 |
| `next_run_time` | Function | `reference/openharness/services/cron.py` | 46 |
| `upsert_cron_job` | Function | `reference/openharness/services/cron.py` | 52 |
| `delete_cron_job` | Function | `reference/openharness/services/cron.py` | 72 |
| `set_job_enabled` | Function | `reference/openharness/services/cron.py` | 91 |
| `mark_job_run` | Function | `reference/openharness/services/cron.py` | 103 |
| `exclusive_file_lock` | Function | `reference/openharness/utils/file_lock.py` | 26 |
| `tool_output_inline_chars` | Function | `reference/openharness/services/tool_outputs.py` | 25 |
| `tool_output_preview_chars` | Function | `reference/openharness/services/tool_outputs.py` | 33 |
| `microcompact_tool_result_chars` | Function | `reference/openharness/services/tool_outputs.py` | 41 |
| `is_microcompactable_tool_result` | Function | `reference/openharness/services/tool_outputs.py` | 49 |
| `cron_start` | Function | `reference/openharness/cli.py` | 882 |
| `cron_stop` | Function | `reference/openharness/cli.py` | 894 |
| `read_pid` | Function | `reference/openharness/services/cron_scheduler.py` | 82 |
| `is_scheduler_running` | Function | `reference/openharness/services/cron_scheduler.py` | 113 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Auto_compact_if_needed → _read_positive_int_env` | cross_community | 6 |
| `Save_session_snapshot → Get_config_dir` | cross_community | 5 |
| `Auth_logout → _exclusive_windows_lock` | cross_community | 5 |
| `Auth_logout → _exclusive_posix_lock` | cross_community | 5 |
| `Delete_cron_job → Get_config_dir` | cross_community | 5 |
| `Delete_cron_job → _resolve_target_mode` | cross_community | 5 |
| `Delete_cron_job → _apply_mode` | cross_community | 5 |
| `Mark_job_run → Get_config_dir` | cross_community | 5 |
| `Main → _exclusive_windows_lock` | cross_community | 4 |
| `Main → _exclusive_posix_lock` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Commands | 7 calls |
| Autopilot | 3 calls |
| Openharness | 2 calls |
| Compact | 2 calls |
| Bridge | 1 calls |

## How to Explore

1. `gitnexus_context({name: "cron_list_cmd"})` — see callers and callees
2. `gitnexus_query({query: "services"})` — find related execution flows
3. Read key files listed above for implementation details
