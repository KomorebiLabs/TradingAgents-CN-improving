---
name: swarm
description: "Skill for the Swarm area of TradingAgents-CN-improving. 136 symbols across 13 files."
---

# Swarm

136 symbols | 13 files | Cohesion: 77%

## When to Use

- Working with code in `reference/`
- Understanding how get_permission_dir, read_pending_permissions, read_resolved_permission work
- Modifying swarm-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `reference/openharness/swarm/permission_sync.py` | to_dict, from_dict, get_permission_dir, _get_pending_dir, _get_resolved_dir (+29) |
| `reference/openharness/swarm/team_lifecycle.py` | from_dict, from_dict, to_dict, from_dict, save (+28) |
| `reference/openharness/swarm/mailbox.py` | _make_message, create_user_message, create_shutdown_request, create_permission_request_message, create_permission_response_message (+15) |
| `reference/openharness/swarm/registry.py` | _detect_tmux, _detect_iterm2, _is_it2_cli_available, _get_tmux_install_instructions, detect_backend (+9) |
| `reference/openharness/swarm/in_process.py` | request_cancel, _drain_mailbox, _run_query_loop, send_message, set_teammate_context (+7) |
| `reference/openharness/swarm/worktree.py` | validate_worktree_slug, _run_git, _remove_symlinks, remove_worktree, list_worktrees (+5) |
| `reference/openharness/swarm/spawn_utils.py` | is_tmux_available, is_inside_tmux, get_teammate_command, build_inherited_cli_flags, build_inherited_env_vars |
| `reference/openharness/swarm/types.py` | send_message, is_pane_backend |
| `reference/openharness/tools/send_message_tool.py` | execute, _send_swarm_message |
| `reference/openharness/platforms.py` | get_platform_capabilities |

## Entry Points

Start here when exploring this area:

- **`get_permission_dir`** (Function) — `reference/openharness/swarm/permission_sync.py:299`
- **`read_pending_permissions`** (Function) — `reference/openharness/swarm/permission_sync.py:425`
- **`read_resolved_permission`** (Function) — `reference/openharness/swarm/permission_sync.py:461`
- **`poll_for_response`** (Function) — `reference/openharness/swarm/permission_sync.py:652`
- **`get_team_file_path`** (Function) — `reference/openharness/swarm/team_lifecycle.py:293`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `get_permission_dir` | Function | `reference/openharness/swarm/permission_sync.py` | 299 |
| `read_pending_permissions` | Function | `reference/openharness/swarm/permission_sync.py` | 425 |
| `read_resolved_permission` | Function | `reference/openharness/swarm/permission_sync.py` | 461 |
| `poll_for_response` | Function | `reference/openharness/swarm/permission_sync.py` | 652 |
| `get_team_file_path` | Function | `reference/openharness/swarm/team_lifecycle.py` | 293 |
| `create_user_message` | Function | `reference/openharness/swarm/mailbox.py` | 252 |
| `create_shutdown_request` | Function | `reference/openharness/swarm/mailbox.py` | 257 |
| `create_permission_request_message` | Function | `reference/openharness/swarm/mailbox.py` | 276 |
| `create_permission_response_message` | Function | `reference/openharness/swarm/mailbox.py` | 305 |
| `create_sandbox_permission_response_message` | Function | `reference/openharness/swarm/mailbox.py` | 370 |
| `write_to_mailbox` | Function | `reference/openharness/swarm/mailbox.py` | 468 |
| `send_permission_request_via_mailbox` | Function | `reference/openharness/swarm/permission_sync.py` | 765 |
| `send_permission_response_via_mailbox` | Function | `reference/openharness/swarm/permission_sync.py` | 815 |
| `send_sandbox_permission_response_via_mailbox` | Function | `reference/openharness/swarm/permission_sync.py` | 937 |
| `read_team_file` | Function | `reference/openharness/swarm/team_lifecycle.py` | 303 |
| `write_team_file` | Function | `reference/openharness/swarm/team_lifecycle.py` | 318 |
| `remove_teammate_from_team_file` | Function | `reference/openharness/swarm/team_lifecycle.py` | 345 |
| `add_hidden_pane_id` | Function | `reference/openharness/swarm/team_lifecycle.py` | 383 |
| `remove_hidden_pane_id` | Function | `reference/openharness/swarm/team_lifecycle.py` | 399 |
| `remove_member_from_team` | Function | `reference/openharness/swarm/team_lifecycle.py` | 417 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Spawn → _require_task` | cross_community | 7 |
| `Spawn → _copy_output` | cross_community | 6 |
| `Spawn → _notify_completion_listeners` | cross_community | 6 |
| `Spawn → _close_process_stdin` | cross_community | 6 |
| `Spawn → Get_docker_sandbox` | cross_community | 6 |
| `Spawn → _cleanup_after_exit` | cross_community | 6 |
| `Spawn → Get_config_dir` | cross_community | 6 |
| `Send_permission_response_via_mailbox → Get_team_dir` | cross_community | 6 |
| `Send_sandbox_permission_response_via_mailbox → Get_team_dir` | cross_community | 6 |
| `Send_permission_request_via_mailbox → Get_team_dir` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tasks | 4 calls |
| Openharness | 3 calls |
| Compact | 1 calls |
| Sandbox | 1 calls |
| Engine | 1 calls |

## How to Explore

1. `gitnexus_context({name: "get_permission_dir"})` — see callers and callees
2. `gitnexus_query({query: "swarm"})` — find related execution flows
3. Read key files listed above for implementation details
