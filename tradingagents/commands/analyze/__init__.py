"""TradingAgents analyze command (Stage 2: Deep multi-agent analysis)."""

from .app import app, run_analysis

__all__ = ["app", "run_analysis"]


def run_analyze(
    ticker: str | None = None,
    date: str | None = None,
    interactive: bool = True,
):
    """Programmatic entry point for the analyze command.

    Args:
        ticker: Ticker symbol (used in non-interactive mode).
        date: Analysis date YYYY-MM-DD (used in non-interactive mode).
        interactive: If True, launch the interactive wizard (questionary prompts).
                     If False, use provided ticker/date with defaults.
    """
    if interactive:
        from .app import run_analysis as _run
        _run()
    else:
        # Non-interactive mode: call run_analysis() - ticker/date are used via
        # the interactive prompts. For true non-interactive, set env or use CLI.
        import sys
        args = []
        if ticker:
            args.extend(["--ticker", ticker])
        if date:
            args.extend(["--date", date])
        old_argv = sys.argv
        sys.argv = ["analyze"] + args
        try:
            from .app import app as analyze_app
            analyze_app(standalone_mode=False)
        finally:
            sys.argv = old_argv
