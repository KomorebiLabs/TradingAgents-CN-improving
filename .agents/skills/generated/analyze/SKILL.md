---
name: analyze
description: "Skill for the Analyze area of TradingAgents-CN-improving. 52 symbols across 10 files."
---

# Analyze

52 symbols | 10 files | Cohesion: 85%

## When to Use

- Working with code in `tradingagents/`
- Understanding how create_layout, save_report_to_disk, display_complete_report work
- Modifying analyze-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tradingagents/commands/analyze/app.py` | init_for_analysis, add_message, add_tool_call, update_agent_status, update_report_section (+23) |
| `tradingagents/commands/analyze/utils.py` | _fetch_openrouter_models, select_openrouter_model, _prompt_custom_model_id, _select_model, select_shallow_thinking_agent (+5) |
| `cli/analyze/run_impl.py` | _classify_message, add_message, add_tool_call, stream_with_dashboard, _update_analyst_statuses (+1) |
| `tradingagents/commands/analyze/announcements.py` | fetch_announcements, display_announcements |
| `cli/stats_handler.py` | get_stats |
| `tradingagents/ui/live_dashboard.py` | add_tool_call |
| `cli/analyze/app.py` | run |
| `cli/main_menu.py` | _run_analyzer |
| `tradingagents/__main__.py` | analyze_cmd |
| `tradingagents/commands/analyze/__init__.py` | run_analyze |

## Entry Points

Start here when exploring this area:

- **`create_layout`** (Function) — `tradingagents/commands/analyze/app.py:235`
- **`save_report_to_disk`** (Function) — `tradingagents/commands/analyze/app.py:644`
- **`display_complete_report`** (Function) — `tradingagents/commands/analyze/app.py:734`
- **`update_research_team_status`** (Function) — `tradingagents/commands/analyze/app.py:795`
- **`update_analyst_statuses`** (Function) — `tradingagents/commands/analyze/app.py:818`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `create_layout` | Function | `tradingagents/commands/analyze/app.py` | 235 |
| `save_report_to_disk` | Function | `tradingagents/commands/analyze/app.py` | 644 |
| `display_complete_report` | Function | `tradingagents/commands/analyze/app.py` | 734 |
| `update_research_team_status` | Function | `tradingagents/commands/analyze/app.py` | 795 |
| `update_analyst_statuses` | Function | `tradingagents/commands/analyze/app.py` | 818 |
| `extract_content_string` | Function | `tradingagents/commands/analyze/app.py` | 859 |
| `is_empty` | Function | `tradingagents/commands/analyze/app.py` | 865 |
| `classify_message_type` | Function | `tradingagents/commands/analyze/app.py` | 901 |
| `run_analysis` | Function | `tradingagents/commands/analyze/app.py` | 934 |
| `save_message_decorator` | Function | `tradingagents/commands/analyze/app.py` | 981 |
| `save_tool_call_decorator` | Function | `tradingagents/commands/analyze/app.py` | 992 |
| `save_report_section_decorator` | Function | `tradingagents/commands/analyze/app.py` | 1003 |
| `analyze` | Function | `tradingagents/commands/analyze/app.py` | 1207 |
| `stream_with_dashboard` | Function | `cli/analyze/run_impl.py` | 215 |
| `fetch_announcements` | Function | `tradingagents/commands/analyze/announcements.py` | 8 |
| `display_announcements` | Function | `tradingagents/commands/analyze/announcements.py` | 29 |
| `get_user_selections` | Function | `tradingagents/commands/analyze/app.py` | 465 |
| `create_question_box` | Function | `tradingagents/commands/analyze/app.py` | 500 |
| `get_ticker` | Function | `tradingagents/commands/analyze/app.py` | 620 |
| `get_analysis_date` | Function | `tradingagents/commands/analyze/app.py` | 625 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → _print_welcome` | cross_community | 6 |
| `Main → Create_question_box` | cross_community | 6 |
| `Main → Ask_ticker` | cross_community | 6 |
| `Main → Ask_date` | cross_community | 6 |
| `Main → Update_agent_status` | cross_community | 6 |
| `Main → Add_message` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Ui | 4 calls |
| Cli | 3 calls |
| Graph | 2 calls |

## How to Explore

1. `gitnexus_context({name: "create_layout"})` — see callers and callees
2. `gitnexus_query({query: "analyze"})` — find related execution flows
3. Read key files listed above for implementation details
