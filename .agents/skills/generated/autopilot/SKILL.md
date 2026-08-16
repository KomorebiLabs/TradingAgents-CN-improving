---
name: autopilot
description: "Skill for the Autopilot area of TradingAgents-CN-improving. 97 symbols across 5 files."
---

# Autopilot

97 symbols | 5 files | Cohesion: 66%

## When to Use

- Working with code in `reference/`
- Understanding how autopilot_journal_cmd, get_project_autopilot_policy_path, get_project_verification_policy_path work
- Modifying autopilot-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `reference/openharness/autopilot/service.py` | _shorten, _source_ref_number, update_status, append_journal, run_card (+76) |
| `reference/openharness/cli.py` | autopilot_journal_cmd, autopilot_status_cmd, autopilot_context_cmd, autopilot_add_cmd, autopilot_scan_cmd |
| `reference/openharness/utils/fs.py` | atomic_write_bytes, atomic_write_text, _resolve_target_mode, _apply_mode |
| `reference/openharness/commands/registry.py` | _shorten_text, _autopilot_handler, _render_card, _ship_handler |
| `reference/openharness/config/paths.py` | get_project_autopilot_policy_path, get_project_verification_policy_path, get_project_release_policy_path |

## Entry Points

Start here when exploring this area:

- **`autopilot_journal_cmd`** (Function) — `reference/openharness/cli.py:1093`
- **`get_project_autopilot_policy_path`** (Function) — `reference/openharness/config/paths.py:140`
- **`get_project_verification_policy_path`** (Function) — `reference/openharness/config/paths.py:145`
- **`get_project_release_policy_path`** (Function) — `reference/openharness/config/paths.py:150`
- **`atomic_write_bytes`** (Function) — `reference/openharness/utils/fs.py:38`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `autopilot_journal_cmd` | Function | `reference/openharness/cli.py` | 1093 |
| `get_project_autopilot_policy_path` | Function | `reference/openharness/config/paths.py` | 140 |
| `get_project_verification_policy_path` | Function | `reference/openharness/config/paths.py` | 145 |
| `get_project_release_policy_path` | Function | `reference/openharness/config/paths.py` | 150 |
| `atomic_write_bytes` | Function | `reference/openharness/utils/fs.py` | 38 |
| `atomic_write_text` | Function | `reference/openharness/utils/fs.py` | 68 |
| `autopilot_status_cmd` | Function | `reference/openharness/cli.py` | 995 |
| `autopilot_context_cmd` | Function | `reference/openharness/cli.py` | 1082 |
| `autopilot_add_cmd` | Function | `reference/openharness/cli.py` | 1049 |
| `autopilot_scan_cmd` | Function | `reference/openharness/cli.py` | 1110 |
| `update_status` | Method | `reference/openharness/autopilot/service.py` | 339 |
| `append_journal` | Method | `reference/openharness/autopilot/service.py` | 380 |
| `run_card` | Method | `reference/openharness/autopilot/service.py` | 643 |
| `load_journal` | Method | `reference/openharness/autopilot/service.py` | 366 |
| `rebuild_active_context` | Method | `reference/openharness/autopilot/service.py` | 404 |
| `load_policies` | Method | `reference/openharness/autopilot/service.py` | 491 |
| `export_dashboard` | Method | `reference/openharness/autopilot/service.py` | 1194 |
| `list_cards` | Method | `reference/openharness/autopilot/service.py` | 252 |
| `get_card` | Method | `reference/openharness/autopilot/service.py` | 258 |
| `pick_next_card` | Method | `reference/openharness/autopilot/service.py` | 333 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Run_card → Get_project_config_dir` | cross_community | 5 |
| `Tick → _load_registry` | cross_community | 5 |
| `Tick → _build_fingerprint` | cross_community | 5 |
| `Tick → _normalize_labels` | cross_community | 5 |
| `Tick → _merge_labels` | cross_community | 5 |
| `Delete_cron_job → _resolve_target_mode` | cross_community | 5 |
| `Delete_cron_job → _apply_mode` | cross_community | 5 |
| `Add_memory_entry → _resolve_target_mode` | cross_community | 4 |
| `Add_memory_entry → _apply_mode` | cross_community | 4 |
| `Autopilot_scan_cmd → _load_registry` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Swarm | 3 calls |
| Config | 3 calls |
| Ui | 1 calls |
| Services | 1 calls |

## How to Explore

1. `gitnexus_context({name: "autopilot_journal_cmd"})` — see callers and callees
2. `gitnexus_query({query: "autopilot"})` — find related execution flows
3. Read key files listed above for implementation details
