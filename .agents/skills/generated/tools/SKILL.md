---
name: tools
description: "Skill for the Tools area of TradingAgents-CN-improving. 103 symbols across 45 files."
---

# Tools

103 symbols | 45 files | Cohesion: 97%

## When to Use

- Working with code in `reference/`
- Understanding how get_docker_sandbox, validate_http_url, ensure_public_http_url work
- Modifying tools-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `reference/openharness/tools/grep_tool.py` | GrepTool, execute, _display_base, _python_grep_files, _resolve_path (+8) |
| `reference/openharness/tools/bash_tool.py` | BashTool, execute, _terminate_process, _read_remaining_output, _drain_available_output (+6) |
| `reference/openharness/tools/glob_tool.py` | GlobTool, execute, _resolve_path, _resolve_glob_request, _has_glob_magic (+3) |
| `reference/openharness/tools/notebook_edit_tool.py` | NotebookEditTool, execute, _resolve_path, _load_notebook, _empty_cell (+1) |
| `reference/openharness/tools/web_search_tool.py` | WebSearchTool, execute, _parse_search_results, _normalize_result_url, _clean_html |
| `reference/openharness/utils/network_guard.py` | validate_http_url, ensure_public_http_url, fetch_public_http_response, _resolve_host_addresses, _parse_ip_literal |
| `reference/openharness/tools/enter_worktree_tool.py` | EnterWorktreeTool, execute, _git_output, _resolve_worktree_path |
| `reference/openharness/tools/mcp_tool.py` | McpToolAdapter, __init__, _input_model_from_schema, _sanitize_tool_segment |
| `reference/openharness/tools/web_fetch_tool.py` | WebFetchTool, execute, _html_to_text, _validate_url |
| `reference/openharness/tools/file_edit_tool.py` | FileEditTool, execute, _resolve_path |

## Entry Points

Start here when exploring this area:

- **`get_docker_sandbox`** (Function) — `reference/openharness/sandbox/session.py:18`
- **`validate_http_url`** (Function) — `reference/openharness/utils/network_guard.py:23`
- **`ensure_public_http_url`** (Function) — `reference/openharness/utils/network_guard.py:34`
- **`fetch_public_http_response`** (Function) — `reference/openharness/utils/network_guard.py:52`
- **`validate_sandbox_path`** (Function) — `reference/openharness/sandbox/path_validator.py:7`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `AgentTool` | Class | `reference/openharness/tools/agent_tool.py` | 37 |
| `AskUserQuestionTool` | Class | `reference/openharness/tools/ask_user_question_tool.py` | 20 |
| `BaseTool` | Class | `reference/openharness/tools/base.py` | 34 |
| `BashTool` | Class | `reference/openharness/tools/bash_tool.py` | 26 |
| `BriefTool` | Class | `reference/openharness/tools/brief_tool.py` | 16 |
| `ConfigTool` | Class | `reference/openharness/tools/config_tool.py` | 18 |
| `CronCreateTool` | Class | `reference/openharness/tools/cron_create_tool.py` | 25 |
| `CronDeleteTool` | Class | `reference/openharness/tools/cron_delete_tool.py` | 16 |
| `CronListTool` | Class | `reference/openharness/tools/cron_list_tool.py` | 15 |
| `CronToggleTool` | Class | `reference/openharness/tools/cron_toggle_tool.py` | 17 |
| `EnterPlanModeTool` | Class | `reference/openharness/tools/enter_plan_mode_tool.py` | 15 |
| `EnterWorktreeTool` | Class | `reference/openharness/tools/enter_worktree_tool.py` | 22 |
| `ExitPlanModeTool` | Class | `reference/openharness/tools/exit_plan_mode_tool.py` | 15 |
| `ExitWorktreeTool` | Class | `reference/openharness/tools/exit_worktree_tool.py` | 18 |
| `FileEditTool` | Class | `reference/openharness/tools/file_edit_tool.py` | 20 |
| `FileReadTool` | Class | `reference/openharness/tools/file_read_tool.py` | 19 |
| `FileWriteTool` | Class | `reference/openharness/tools/file_write_tool.py` | 19 |
| `GlobTool` | Class | `reference/openharness/tools/glob_tool.py` | 24 |
| `GrepTool` | Class | `reference/openharness/tools/grep_tool.py` | 25 |
| `ImageToTextTool` | Class | `reference/openharness/tools/image_to_text_tool.py` | 61 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Execute → Detect_platform` | cross_community | 6 |
| `Spawn → Get_docker_sandbox` | cross_community | 6 |
| `Run_query → Get_docker_sandbox` | cross_community | 5 |
| `Execute → _format_path` | intra_community | 4 |
| `Spawn → Get_docker_sandbox` | cross_community | 4 |
| `Execute → _looks_like_interactive_scaffold` | cross_community | 3 |
| `Execute → Get_docker_sandbox` | cross_community | 3 |
| `Execute → _cleanup_after_exit` | cross_community | 3 |
| `Execute → Get_docker_sandbox` | intra_community | 3 |
| `Execute → _timeout_marker` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Bridge | 1 calls |

## How to Explore

1. `gitnexus_context({name: "get_docker_sandbox"})` — see callers and callees
2. `gitnexus_query({query: "tools"})` — find related execution flows
3. Read key files listed above for implementation details
