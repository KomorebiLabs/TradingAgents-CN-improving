---
name: dataflows
description: "Skill for the Dataflows area of TradingAgents-CN-improving. 115 symbols across 20 files."
---

# Dataflows

115 symbols | 20 files | Cohesion: 70%

## When to Use

- Working with code in `tradingagents/`
- Understanding how get_cn_earnings_calendar, get_cn_ipo_data, get_cn_m_a_news work
- Modifying dataflows-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tradingagents/dataflows/akshare_interface.py` | _require_akshare, _render_macro_events, _prepare_sector_news, _prepare_macro_sector_news, get_akshare_cn_tech_sector_news (+39) |
| `tradingagents/dataflows/interface.py` | get_category_for_method, _is_rate_limit_error, route_to_vendor, _is_rag_enabled, _is_rag_supported_method (+7) |
| `tradingagents/dataflows/y_finance.py` | get_YFin_data_online, get_fundamentals, get_insider_transactions, get_stock_stats_indicators_window, _get_stock_stats_bulk (+4) |
| `tradingagents/agents/utils/cn_event_tools.py` | get_cn_earnings_calendar, get_cn_ipo_data, get_cn_m_a_news, get_cn_stock_pledge, get_cn_limit_up_stocks |
| `tradingagents/dataflows/alpha_vantage_fundamentals.py` | get_fundamentals, _filter_reports_by_date, get_balance_sheet, get_cashflow, get_income_statement |
| `tests/test_akshare_interface.py` | test_cn_policy_news_filters_for_policy_sensitive_events, test_fund_flow_output_is_labeled_as_cn_proxy, test_cn_market_flow_output_is_execution_focused, test_news_output_truncates_long_content_and_uses_bullets, test_fundamentals_snapshot_is_pruned_to_core_fields |
| `tradingagents/dataflows/stockstats_utils.py` | yf_retry, _clean_dataframe, load_ohlcv, get_stock_stats, filter_financials_by_date |
| `tradingagents/agents/utils/fundamental_data_tools.py` | get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement |
| `tradingagents/dataflows/alpha_vantage_common.py` | get_api_key, format_datetime_for_api, _make_api_request, _filter_csv_by_date_range |
| `tradingagents/agents/utils/cn_macro_tools.py` | get_cn_macro_data, get_cn_rate_outlook, get_cn_trade_data |

## Entry Points

Start here when exploring this area:

- **`get_cn_earnings_calendar`** (Function) — `tradingagents/agents/utils/cn_event_tools.py:26`
- **`get_cn_ipo_data`** (Function) — `tradingagents/agents/utils/cn_event_tools.py:58`
- **`get_cn_m_a_news`** (Function) — `tradingagents/agents/utils/cn_event_tools.py:88`
- **`get_cn_stock_pledge`** (Function) — `tradingagents/agents/utils/cn_event_tools.py:119`
- **`get_cn_limit_up_stocks`** (Function) — `tradingagents/agents/utils/cn_event_tools.py:151`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `DataSourceError` | Class | `tradingagents/dataflows/akshare_interface.py` | 1534 |
| `DataNotFoundError` | Class | `tradingagents/dataflows/akshare_interface.py` | 1539 |
| `InvalidParameterError` | Class | `tradingagents/dataflows/akshare_interface.py` | 1544 |
| `get_cn_earnings_calendar` | Function | `tradingagents/agents/utils/cn_event_tools.py` | 26 |
| `get_cn_ipo_data` | Function | `tradingagents/agents/utils/cn_event_tools.py` | 58 |
| `get_cn_m_a_news` | Function | `tradingagents/agents/utils/cn_event_tools.py` | 88 |
| `get_cn_stock_pledge` | Function | `tradingagents/agents/utils/cn_event_tools.py` | 119 |
| `get_cn_limit_up_stocks` | Function | `tradingagents/agents/utils/cn_event_tools.py` | 151 |
| `get_cn_macro_data` | Function | `tradingagents/agents/utils/cn_macro_tools.py` | 27 |
| `get_cn_rate_outlook` | Function | `tradingagents/agents/utils/cn_macro_tools.py` | 63 |
| `get_cn_trade_data` | Function | `tradingagents/agents/utils/cn_macro_tools.py` | 92 |
| `get_stock_data` | Function | `tradingagents/agents/utils/core_stock_tools.py` | 13 |
| `get_fundamentals` | Function | `tradingagents/agents/utils/fundamental_data_tools.py` | 13 |
| `get_balance_sheet` | Function | `tradingagents/agents/utils/fundamental_data_tools.py` | 38 |
| `get_cashflow` | Function | `tradingagents/agents/utils/fundamental_data_tools.py` | 67 |
| `get_income_statement` | Function | `tradingagents/agents/utils/fundamental_data_tools.py` | 96 |
| `get_insider_transactions` | Function | `tradingagents/agents/utils/news_data_tools.py` | 91 |
| `get_cn_market_flow` | Function | `tradingagents/agents/utils/news_data_tools.py` | 127 |
| `get_indicators` | Function | `tradingagents/agents/utils/technical_indicators_tools.py` | 12 |
| `get_category_for_method` | Function | `tradingagents/dataflows/interface.py` | 307 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Route_to_vendor_with_rag → Initialize_config` | cross_community | 5 |
| `Get_rag_news → Initialize_config` | cross_community | 5 |
| `Get_rag_sector_news → Initialize_config` | cross_community | 5 |
| `Route_to_vendor_with_rag → _normalize_vendor_name` | cross_community | 4 |
| `Get_rag_news → _normalize_vendor_name` | cross_community | 4 |
| `Get_rag_sector_news → _normalize_vendor_name` | cross_community | 4 |
| `Get_akshare_cn_tech_sector_news → _render_bullets` | cross_community | 3 |
| `Get_akshare_global_news → _truncate_text` | cross_community | 3 |
| `Get_akshare_global_news → _render_bullets` | cross_community | 3 |
| `Get_akshare_cn_new_energy_news → _truncate_text` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 20 calls |

## How to Explore

1. `gitnexus_context({name: "get_cn_earnings_calendar"})` — see callers and callees
2. `gitnexus_query({query: "dataflows"})` — find related execution flows
3. Read key files listed above for implementation details
