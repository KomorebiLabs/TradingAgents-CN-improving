"""Root screener CLI app.

Entry points:
    python -m tradingagents.screener.cli           -- interactive wizard
    python -m tradingagents.screener.cli run        -- explicit subcommand

The `run` command logic lives in commands/run_impl.py so it can also be
imported and called programmatically.
"""

import logging
import sys

import typer

# Use Bloomberg-style theme
from tradingagents.ui.theme import TRADING_THEME
from rich.console import Console

# Override console to use themed console
console = Console(theme=TRADING_THEME)

# Configure logging to stdout so progress messages are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)

app = typer.Typer(
    name="screener",
    help="TradingAgents Screener CLI: Stage 1 candidate discovery for A-share stocks.",
    add_completion=True,
    no_args_is_help=False,
    rich_markup_mode="rich",
)

# Import the implementation so it can be registered as a command
from tradingagents.screener.cli.commands.run_impl import run as run_func
from tradingagents.screener.cli.interactive import interactive

app.command("run", help="Run the Screener to discover top stock candidates.")(run_func)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Run the interactive Screener wizard when no subcommand is provided."""
    if ctx.invoked_subcommand is not None or ctx.resilient_parsing:
        return
    interactive()


if __name__ == "__main__":
    app()
