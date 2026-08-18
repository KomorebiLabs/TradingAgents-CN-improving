---
name: skills
description: "Skill for the Skills area of TradingAgents-CN-improving. 52 symbols across 16 files."
---

# Skills

52 symbols | 16 files | Cohesion: 79%

## When to Use

- Working with code in `tests/`
- Understanding how test_load_skill_registry_from_temp_dir, test_load_skill_registry_empty_dir, test_registry_register_and_get work
- Modifying skills-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tests/harness/skills/test_audit.py` | test_parses_single_skill_with_justification, test_parses_multiple_skills, test_no_skills_used, test_no_skills_block_returns_empty, test_ignores_comments_and_blank_lines (+6) |
| `tradingagents/harness/skills/loader.py` | load_skill_registry, load_skills_from_dirs, _parse_decision_types, _load_skill, _load_skill_from_directory (+1) |
| `tradingagents/harness/skills/registry.py` | register, get, list_skills, get_skills_for_analyst, get_skills_by_names |
| `reference/openharness/skills/loader.py` | load_skill_registry, get_user_skills_dir, load_user_skills, load_skills_from_dirs, _parse_skill_markdown |
| `tests/harness/skills/test_loader.py` | test_load_skill_registry_from_temp_dir, test_load_skill_registry_empty_dir, test_load_skill_without_frontmatter, test_load_skill_frontmatter_name_overrides_filename |
| `tradingagents/harness/skills/types.py` | to_prompt_section, to_prompt_section, to_core_section, to_full_section |
| `tests/harness/skills/test_registry.py` | test_registry_register_and_get, test_registry_get_skills_for_analyst, test_registry_get_skills_by_names |
| `tradingagents/harness/skills/audit.py` | parse_skill_usage, build_skill_audit_entry, build_skill_audit_summary |
| `reference/openharness/skills/bundled/__init__.py` | get_bundled_skills, _parse_frontmatter |
| `reference/openharness/skills/registry.py` | register, list_skills |

## Entry Points

Start here when exploring this area:

- **`test_load_skill_registry_from_temp_dir`** (Function) — `tests/harness/skills/test_loader.py:7`
- **`test_load_skill_registry_empty_dir`** (Function) — `tests/harness/skills/test_loader.py:44`
- **`test_registry_register_and_get`** (Function) — `tests/harness/skills/test_registry.py:6`
- **`test_registry_get_skills_for_analyst`** (Function) — `tests/harness/skills/test_registry.py:20`
- **`test_registry_get_skills_by_names`** (Function) — `tests/harness/skills/test_registry.py:44`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `test_load_skill_registry_from_temp_dir` | Function | `tests/harness/skills/test_loader.py` | 7 |
| `test_load_skill_registry_empty_dir` | Function | `tests/harness/skills/test_loader.py` | 44 |
| `test_registry_register_and_get` | Function | `tests/harness/skills/test_registry.py` | 6 |
| `test_registry_get_skills_for_analyst` | Function | `tests/harness/skills/test_registry.py` | 20 |
| `test_registry_get_skills_by_names` | Function | `tests/harness/skills/test_registry.py` | 44 |
| `load_skill_registry` | Function | `tradingagents/harness/skills/loader.py` | 99 |
| `load_skills_from_dirs` | Function | `tradingagents/harness/skills/loader.py` | 178 |
| `get_bundled_skills` | Function | `reference/openharness/skills/bundled/__init__.py` | 32 |
| `load_skill_registry` | Function | `reference/openharness/skills/loader.py` | 82 |
| `parse_skill_usage` | Function | `tradingagents/harness/skills/audit.py` | 22 |
| `build_skill_audit_entry` | Function | `tradingagents/harness/skills/audit.py` | 64 |
| `test_load_skill_without_frontmatter` | Function | `tests/harness/skills/test_loader.py` | 33 |
| `test_load_skill_frontmatter_name_overrides_filename` | Function | `tests/harness/skills/test_loader.py` | 51 |
| `get_user_skills_dir` | Function | `reference/openharness/skills/loader.py` | 53 |
| `load_user_skills` | Function | `reference/openharness/skills/loader.py` | 148 |
| `load_skills_from_dirs` | Function | `reference/openharness/skills/loader.py` | 174 |
| `build_skill_audit_summary` | Function | `tradingagents/harness/skills/audit.py` | 106 |
| `register` | Method | `tradingagents/harness/skills/registry.py` | 14 |
| `get` | Method | `tradingagents/harness/skills/registry.py` | 18 |
| `list_skills` | Method | `tradingagents/harness/skills/registry.py` | 22 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Research_manager_node → _parse_decision_types` | cross_community | 8 |
| `Trader_node → _parse_decision_types` | cross_community | 8 |
| `Aggressive_node → _parse_decision_types` | cross_community | 8 |
| `Aggressive_node → _parse_decision_types` | cross_community | 8 |
| `Bear_node → _parse_decision_types` | cross_community | 8 |
| `Bull_node → _parse_decision_types` | cross_community | 8 |
| `Conservative_node → _parse_decision_types` | cross_community | 8 |
| `Neutral_node → _parse_decision_types` | cross_community | 8 |
| `Fundamentals_analyst_node → _parse_decision_types` | cross_community | 7 |
| `Social_media_analyst_node → _parse_decision_types` | cross_community | 7 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Auth | 2 calls |
| Plugins | 1 calls |

## How to Explore

1. `gitnexus_context({name: "test_load_skill_registry_from_temp_dir"})` — see callers and callees
2. `gitnexus_query({query: "skills"})` — find related execution flows
3. Read key files listed above for implementation details
