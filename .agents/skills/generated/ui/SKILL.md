---
name: ui
description: "Skill for the Ui area of TradingAgents-CN-improving. 122 symbols across 22 files."
---

# Ui

122 symbols | 22 files | Cohesion: 78%

## When to Use

- Working with code in `reference/`
- Understanding how is_coordinator_mode, match_session_mode, load_hook_registry work
- Modifying ui-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `reference/openharness/ui/backend_host.py` | run, _read_requests, _run_active_request, _interrupt_active_request, _process_line (+15) |
| `reference/openharness/ui/runtime.py` | _resolve_vision_config, build_runtime, start_runtime, close_runtime, current_settings (+12) |
| `reference/openharness/ui/textual_app.py` | on_mount, on_unmount, handle_submit, _process_line, _print_system (+9) |
| `tradingagents/ui/live_dashboard.py` | _stage_index, update_metrics, _build_layout, _build_progress_panel, _build_agent_panel (+8) |
| `reference/openharness/ui/output.py` | start_assistant_turn, render_event, print_system, _start_spinner, _stop_spinner (+6) |
| `reference/openharness/ui/protocol.py` | from_record, ready, state_snapshot, tasks_snapshot, status_snapshot (+2) |
| `reference/openharness/ui/react_launcher.py` | _resolve_theme, _resolve_npm, _resolve_tsx, get_frontend_dir, build_backend_command (+1) |
| `tradingagents/ui/summary.py` | print_analyzer_summary, _display_full_report, show_section, print_screener_summary, print_summary (+1) |
| `reference/openharness/ui/coordinator_drain.py` | _async_agent_task_entries, pending_async_agent_entries, wait_for_completed_async_agent_entries, submit_follow_up, drain_coordinator_async_agents |
| `reference/openharness/ui/app.py` | _decode_task_worker_line, run_task_worker, run_print_mode, run_repl |

## Entry Points

Start here when exploring this area:

- **`is_coordinator_mode`** (Function) — `reference/openharness/coordinator/coordinator_mode.py:309`
- **`match_session_mode`** (Function) — `reference/openharness/coordinator/coordinator_mode.py:325`
- **`load_hook_registry`** (Function) — `reference/openharness/hooks/loader.py:120`
- **`stop_docker_sandbox`** (Function) — `reference/openharness/sandbox/session.py:57`
- **`create_default_tool_registry`** (Function) — `reference/openharness/tools/__init__.py:46`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `is_coordinator_mode` | Function | `reference/openharness/coordinator/coordinator_mode.py` | 309 |
| `match_session_mode` | Function | `reference/openharness/coordinator/coordinator_mode.py` | 325 |
| `load_hook_registry` | Function | `reference/openharness/hooks/loader.py` | 120 |
| `stop_docker_sandbox` | Function | `reference/openharness/sandbox/session.py` | 57 |
| `create_default_tool_registry` | Function | `reference/openharness/tools/__init__.py` | 46 |
| `run_task_worker` | Function | `reference/openharness/ui/app.py` | 88 |
| `run_print_mode` | Function | `reference/openharness/ui/app.py` | 171 |
| `build_runtime` | Function | `reference/openharness/ui/runtime.py` | 198 |
| `start_runtime` | Function | `reference/openharness/ui/runtime.py` | 388 |
| `close_runtime` | Function | `reference/openharness/ui/runtime.py` | 396 |
| `sync_app_state` | Function | `reference/openharness/ui/runtime.py` | 478 |
| `handle_line` | Function | `reference/openharness/ui/runtime.py` | 521 |
| `fmt` | Function | `tradingagents/ui/live_dashboard.py` | 247 |
| `run_repl` | Function | `reference/openharness/ui/app.py` | 39 |
| `run_backend_host` | Function | `reference/openharness/ui/backend_host.py` | 789 |
| `get_frontend_dir` | Function | `reference/openharness/ui/react_launcher.py` | 58 |
| `build_backend_command` | Function | `reference/openharness/ui/react_launcher.py` | 80 |
| `launch_react_tui` | Function | `reference/openharness/ui/react_launcher.py` | 112 |
| `run_analysis` | Function | `cli/analyze/run_impl.py` | 80 |
| `print_reports_saved` | Function | `cli/analyze/run_impl.py` | 397 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → Update_agent_status` | cross_community | 6 |
| `Main → Add_message` | cross_community | 6 |
| `Run → _format_permission_mode` | intra_community | 5 |
| `On_mount → Current_settings` | cross_community | 5 |
| `On_mount → _inject_arguments` | cross_community | 5 |
| `Handle_line → Current_settings` | intra_community | 4 |
| `On_mount → Update_registry` | cross_community | 4 |
| `On_mount → _run_http_hook` | cross_community | 4 |
| `Run → _stage_index` | intra_community | 4 |
| `Run → Fmt` | intra_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Auth | 13 calls |
| Mcp | 7 calls |
| Analyze | 3 calls |
| Engine | 3 calls |
| Tasks | 3 calls |
| Graph | 2 calls |
| Hooks | 2 calls |
| Commands | 1 calls |

## How to Explore

1. `gitnexus_context({name: "is_coordinator_mode"})` — see callers and callees
2. `gitnexus_query({query: "ui"})` — find related execution flows
3. Read key files listed above for implementation details
