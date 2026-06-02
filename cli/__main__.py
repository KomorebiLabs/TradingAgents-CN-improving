"""TradingAgents CLI - Unified entry point.

Usage:
    python -m cli                  -- interactive main menu
    python -m tradingagents         -- same as above (routes through here)
"""
from cli.main_menu import run_main_menu

if __name__ == "__main__":
    run_main_menu()
