import os

_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", os.path.join(_TRADINGAGENTS_HOME, "logs")),
    "data_cache_dir": os.getenv("TRADINGAGENTS_CACHE_DIR", os.path.join(_TRADINGAGENTS_HOME, "cache")),
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.4",
    "quick_think_llm": "gpt-5.4-mini",
    "backend_url": "https://api.openai.com/v1",
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    # Output language for analyst reports and final decision
    # Internal agent debate stays in English for reasoning quality
    "output_language": "English",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Experimental prompt controls
    "enable_confidence_score": False,
    # Instrument profiling and skill-mounting controls
    "instrument_skill_rules": {
        "cn_equity": ["cn_market_data", "cn_macro_news", "cn_fund_flow_proxy"],
        "cn_main_board_equity": ["cn_main_board_routing"],
        "cn_chinext_equity": ["chinext_growth_board"],
        "cn_star_equity": ["star_market_policy"],
        "cn_bse_equity": ["bse_liquidity_watch"],
        "dividend_style_candidate": ["dividend_factor_focus"],
        "growth_style_candidate": ["growth_factor_focus"],
        "us_equity": ["global_news", "us_financial_statements"],
    },
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "tencent_finance,sina_finance,baostock_data,legacy_yfinance",
        "technical_indicators": "legacy_yfinance,legacy_alpha_vantage",
        "fundamental_data": "ths_data,legacy_akshare,legacy_yfinance",
        "news_data": "ths_data,baidu_finance,legacy_akshare,legacy_yfinance",
        "cn_macro_data": "baidu_finance,legacy_akshare",
        "cn_event_data": "ths_data,legacy_akshare",
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
}
