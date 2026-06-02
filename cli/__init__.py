"""Redirect: use tradingagents.commands.analyze instead.

This package is kept for backwards compatibility.
Run: python -m tradingagents
Or:  python -m tradingagents.commands.analyze
"""

__all__ = []


def __getattr__(name: str):
    """Lazy-load everything to avoid eager import of questionary dependency."""
    if name in ("app", "run_analysis"):
        try:
            from tradingagents.commands.analyze import app, run_analysis
            globals()["app"] = app
            globals()["run_analysis"] = run_analysis
            return globals()[name]
        except ModuleNotFoundError as e:
            if "questionary" in str(e):
                import sys

                sys.stderr.write(
                    "\n"
                    "=" * 60 + "\n"
                    "[red]Missing dependency: questionary[/red]\n"
                    "\n"
                    "The analyze command requires 'questionary'.\n"
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
            raise
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
