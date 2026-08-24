"""Per-analyst tool assembly (lazy imports over the dataflows layer)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from tradingagents.dataflows.config import get_config
from tradingagents.agents.utils.tools.instrument_profile import build_instrument_profile

# Lazy cache of per-analyst tool lists, filled on first assembly.
ANALYST_TOOLSETS: Dict[str, List] = {}

def _lazy_tool_imports():
    from tradingagents.agents.utils.core_stock_tools import get_stock_data
    from tradingagents.agents.utils.technical_indicators_tools import get_indicators
    from tradingagents.agents.utils.fundamental_data_tools import (
        get_fundamentals,
        get_balance_sheet,
        get_cashflow,
        get_income_statement,
    )
    from tradingagents.agents.utils.news_data_tools import (
        get_cn_market_flow,
        get_cn_policy_news,
        get_announcements,
        get_news,
        get_insider_transactions,
        get_global_news,
    )
    from tradingagents.agents.utils.cn_sector_news_tools import (
        get_cn_tech_sector_news,
        get_cn_new_energy_news,
        get_cn_pharma_news,
        get_cn_real_estate_news,
        get_cn_fintech_news,
        get_sector_tools_for_ticker,
    )
    from tradingagents.agents.utils.cn_macro_tools import (
        get_cn_macro_data,
        get_cn_rate_outlook,
        get_cn_trade_data,
        should_mount_macro_tools,
    )

    return {
        "get_stock_data": get_stock_data,
        "get_indicators": get_indicators,
        "get_fundamentals": get_fundamentals,
        "get_balance_sheet": get_balance_sheet,
        "get_cashflow": get_cashflow,
        "get_income_statement": get_income_statement,
        "get_cn_market_flow": get_cn_market_flow,
        "get_cn_policy_news": get_cn_policy_news,
        "get_announcements": get_announcements,
        "get_news": get_news,
        "get_insider_transactions": get_insider_transactions,
        "get_global_news": get_global_news,
        "get_cn_tech_sector_news": get_cn_tech_sector_news,
        "get_cn_new_energy_news": get_cn_new_energy_news,
        "get_cn_pharma_news": get_cn_pharma_news,
        "get_cn_real_estate_news": get_cn_real_estate_news,
        "get_cn_fintech_news": get_cn_fintech_news,
        "get_sector_tools_for_ticker": get_sector_tools_for_ticker,
        "get_cn_macro_data": get_cn_macro_data,
        "get_cn_rate_outlook": get_cn_rate_outlook,
        "get_cn_trade_data": get_cn_trade_data,
        "should_mount_macro_tools": should_mount_macro_tools,
    }


def _config_prefers_vendor(config: Dict, category: str, methods: List[str], vendor: str) -> bool:
    tool_vendors = config.get("tool_vendors", {})
    for method in methods:
        configured = tool_vendors.get(method)
        if configured and vendor in [item.strip() for item in configured.split(",")]:
            return True

    category_vendor = config.get("data_vendors", {}).get(category, "")
    return vendor in [item.strip() for item in category_vendor.split(",")]


def get_tools_for_analyst(analyst_type: str, ticker: str = "", config: Dict = None) -> List:
    lazy = _lazy_tool_imports()
    if not ANALYST_TOOLSETS:
        ANALYST_TOOLSETS.update(
            {
                "market": [lazy["get_stock_data"], lazy["get_indicators"]],
                "social": [lazy["get_news"]],
                "news": [lazy["get_news"], lazy["get_announcements"], lazy["get_global_news"], lazy["get_insider_transactions"], lazy["get_cn_policy_news"]],
                "fundamentals": [lazy["get_fundamentals"], lazy["get_balance_sheet"], lazy["get_cashflow"], lazy["get_income_statement"]],
            }
        )
    tools = list(ANALYST_TOOLSETS[analyst_type])
    config = config or get_config()
    instrument_profile = build_instrument_profile(ticker, config)
    skills = set(instrument_profile.get("skills", []))

    if analyst_type == "news" and "cn_macro_news" not in skills and instrument_profile["is_cn_equity"]:
        tools = [tool for tool in tools if tool.name != "get_global_news"]
    if analyst_type == "news":
        if instrument_profile["segment"] in {"cn_star_equity", "cn_chinext_equity"}:
            if all(tool.name != "get_cn_policy_news" for tool in tools):
                tools.append(lazy["get_cn_policy_news"])
        else:
            tools = [tool for tool in tools if tool.name != "get_cn_policy_news"]

    # ========================================
    # Sector-specific tools mounting (L2 深化)
    # ========================================
    if analyst_type == "news" and instrument_profile["is_cn_equity"]:
        # Get sector tools based on ticker segment/industry
        sector_tools = lazy["get_sector_tools_for_ticker"](ticker)

        for sector_tool in sector_tools:
            # Only add if not already present
            if all(tool.name != sector_tool.name for tool in tools):
                tools.append(sector_tool)

        # Mount macro tools if skill is enabled
        if lazy["should_mount_macro_tools"](list(skills)):
            macro_tools = [lazy["get_cn_macro_data"], lazy["get_cn_rate_outlook"], lazy["get_cn_trade_data"]]
            for macro_tool in macro_tools:
                if all(tool.name != macro_tool.name for tool in tools):
                    tools.append(macro_tool)

    if analyst_type == "fundamentals" and instrument_profile["segment"] in {"cn_chinext_equity", "cn_star_equity", "cn_bse_equity"}:
        tools = [tool for tool in tools if tool.name != "get_income_statement"]

    if analyst_type == "market":
        if instrument_profile["segment"] == "cn_bse_equity":
            tools = [tool for tool in tools if tool.name != "get_indicators"]
        if instrument_profile["segment"] == "cn_bse_equity" or "growth_factor_focus" in skills:
            if all(tool.name != "get_cn_market_flow" for tool in tools):
                tools.append(lazy["get_cn_market_flow"])
        else:
            tools = [tool for tool in tools if tool.name != "get_cn_market_flow"]

    if (
        analyst_type == "fundamentals"
        and instrument_profile["is_cn_equity"]
        and _config_prefers_vendor(config, "fundamental_data", ["get_fundamentals"], "akshare")
    ):
        # CN fundamentals currently have a pruned AkShare company snapshot only.
        return [lazy["get_fundamentals"]]

    return tools
