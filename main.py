from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# !!!这里修改了deepseek的api配置
# Create a custom config
config = DEFAULT_CONFIG.copy()

# === LLM Configuration ===
config["llm_provider"] = "deepseek"
config["deep_think_llm"] = "deepseek-v4-flash"
config["quick_think_llm"] = "deepseek-v4-flash"
config["max_debate_rounds"] = 1  # Increase debate rounds

# === Data Vendor Configuration ===
# Primary: AkShare (free, comprehensive CN stock data)
# Fallback: alpha_vantage (requires API key)
#
# Note: If AkShare fails due to network issues, the system will
# automatically fall back to alpha_vantage for stock data.
config["data_vendors"] = {
    "core_stock_apis": "akshare,alpha_vantage,yfinance",    # A-share: AkShare primary, fallback to AlphaVantage
    "technical_indicators": "alpha_vantage,akshare",        # Tech indicators: AlphaVantage primary
    "fundamental_data": "akshare,alpha_vantage",            # Fundamentals: AkShare primary, AlphaVantage fallback
    "news_data": "akshare,alpha_vantage",                   # News: AkShare primary, AlphaVantage fallback
}

# === Initialize with custom config ===
ta = TradingAgentsGraph(debug=True, config=config)

# forward propagate
_, decision = ta.propagate("000001", "2026-04-28")
print(decision)

# Memorize mistakes and reflect
# ta.reflect_and_remember(1000) # parameter is the position returns
