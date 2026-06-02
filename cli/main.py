"""DEPRECATED: This module has been moved.

This file is kept for backwards compatibility only.
Running `python -m cli.main` redirects here, which immediately
forwards to the new location.

New location: tradingagents.commands.analyze.app
Recommended: python -m tradingagents analyze
"""

# Zero-dependency redirect: avoid importing anything from the old cli/ subtree
# that pulls in questionary. Just proxy to the real location.
import sys
import importlib.util

# Guard against questionary being missing in the target module
_spec = importlib.util.find_spec("questionary")
if _spec is None:
    sys.stderr.write(
        "\n"
        "=" * 60 + "\n"
        "[red]Missing dependency: questionary[/red]\n"
        "\n"
        "The 'python -m cli.main' entry point requires 'questionary'.\n"
        "\n"
        "[yellow]Recommended fix:[/yellow]\n"
        "  pip install questionary>=2.1.0\n"
        "\n"
        "[dim]Or use the new unified entry point:[/dim]\n"
        "  python -m tradingagents analyze\n"
        "\n"
        "=" * 60 + "\n"
    )
    sys.exit(1)

# Forward to the real implementation
from tradingagents.commands.analyze.app import app

# Execute the app directly (not the old cli/main.py code)
app()
