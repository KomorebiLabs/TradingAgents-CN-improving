"""Terminal mascot for TradingAgents brand identity."""

from __future__ import annotations

import os
import random

# ASCII art mascot for TradingAgents / Komo
KOMO_MASCOT = r"""
[bold cyan]╔══════════════════════════════════════════╗[/bold cyan]
[bold cyan]║[/bold cyan]        🐍 [bold]Komo[/bold] — TradingAgents 🐍        [bold cyan]║[/bold cyan]
[bold cyan]╚══════════════════════════════════════════╝[/bold cyan]
"""


def print_komo() -> None:
    """Print the Komo mascot banner once per session."""
    if not should_show_komo():
        return
    try:
        from rich.console import Console
        console = Console()
        console.print(KOMO_MASCOT)
    except Exception:
        print("[Komo mascot]")


def should_show_komo() -> bool:
    """Determine whether to show the mascot (once per session)."""
    env = os.environ.get("TRADINGAGENTS_SHOW_KOMO", "").lower()
    if env == "0" or env == "false":
        return False
    # Always show by default
    return True
