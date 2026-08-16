---
name: commands
description: "Skill for the Commands area of TradingAgents-CN-improving. 53 symbols across 7 files."
---

# Commands

53 symbols | 7 files | Cohesion: 79%

## When to Use

- Working with code in `reference/`
- Understanding how get_data_dir, get_feedback_dir, get_feedback_log_path work
- Modifying commands-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `reference/openharness/commands/registry.py` | _copy_to_clipboard, _last_message_text, _copy_handler, _feedback_handler, _init_handler (+25) |
| `tradingagents/screener/cli/commands/run_impl.py` | _get_last_trading_day, _load_tickers_from_file, _resolve_tickers, _build_cli_config, _resolve_output_dir (+6) |
| `reference/openharness/config/paths.py` | get_data_dir, get_feedback_dir, get_feedback_log_path, get_project_config_dir, get_project_issue_file (+1) |
| `reference/openharness/engine/query_engine.py` | load_messages, clear, has_pending_continuation |
| `reference/openharness/channels/impl/mochat.py` | __init__ |
| `reference/openharness/utils/helpers.py` | get_data_path |
| `reference/openharness/config/settings.py` | display_model_setting |

## Entry Points

Start here when exploring this area:

- **`get_data_dir`** (Function) — `reference/openharness/config/paths.py:36`
- **`get_feedback_dir`** (Function) — `reference/openharness/config/paths.py:84`
- **`get_feedback_log_path`** (Function) — `reference/openharness/config/paths.py:91`
- **`get_data_path`** (Function) — `reference/openharness/utils/helpers.py:18`
- **`get_project_config_dir`** (Function) — `reference/openharness/config/paths.py:101`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `get_data_dir` | Function | `reference/openharness/config/paths.py` | 36 |
| `get_feedback_dir` | Function | `reference/openharness/config/paths.py` | 84 |
| `get_feedback_log_path` | Function | `reference/openharness/config/paths.py` | 91 |
| `get_data_path` | Function | `reference/openharness/utils/helpers.py` | 18 |
| `get_project_config_dir` | Function | `reference/openharness/config/paths.py` | 101 |
| `get_project_issue_file` | Function | `reference/openharness/config/paths.py` | 108 |
| `get_project_pr_comments_file` | Function | `reference/openharness/config/paths.py` | 113 |
| `run` | Function | `tradingagents/screener/cli/commands/run_impl.py` | 221 |
| `display_model_setting` | Function | `reference/openharness/config/settings.py` | 283 |
| `create_default_command_registry` | Function | `reference/openharness/commands/registry.py` | 261 |
| `load_messages` | Method | `reference/openharness/engine/query_engine.py` | 358 |
| `register` | Method | `reference/openharness/commands/registry.py` | 134 |
| `help_text` | Method | `reference/openharness/commands/registry.py` | 152 |
| `clear` | Method | `reference/openharness/engine/query_engine.py` | 244 |
| `has_pending_continuation` | Method | `reference/openharness/engine/query_engine.py` | 376 |
| `_copy_to_clipboard` | Function | `reference/openharness/commands/registry.py` | 182 |
| `_last_message_text` | Function | `reference/openharness/commands/registry.py` | 198 |
| `_copy_handler` | Function | `reference/openharness/commands/registry.py` | 499 |
| `_feedback_handler` | Function | `reference/openharness/commands/registry.py` | 830 |
| `_init_handler` | Function | `reference/openharness/commands/registry.py` | 648 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Spawn → Get_config_dir` | cross_community | 6 |
| `Run_card → Get_project_config_dir` | cross_community | 5 |
| `Add_memory_entry → Get_config_dir` | cross_community | 5 |
| `Remove_memory_entry → Get_config_dir` | cross_community | 5 |
| `Save_session_snapshot → Get_config_dir` | cross_community | 5 |
| `Delete_cron_job → Get_config_dir` | cross_community | 5 |
| `Mark_job_run → Get_config_dir` | cross_community | 5 |
| `Run → Print_progress_bar` | cross_community | 4 |
| `Run → Clear_progress_line` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Auth | 10 calls |
| Config | 4 calls |
| Ui | 2 calls |
| Screener | 1 calls |
| Impl | 1 calls |

## How to Explore

1. `gitnexus_context({name: "get_data_dir"})` — see callers and callees
2. `gitnexus_query({query: "commands"})` — find related execution flows
3. Read key files listed above for implementation details
