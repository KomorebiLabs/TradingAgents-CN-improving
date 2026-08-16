"""DEPRECATED legacy alias: `python -m cli.main` now launches the new Analyzer.

The old implementation in tradingagents/commands/analyze/ is retired.
Prefer the unified entry point:

    python -m tradingagents analyze
"""

from cli.analyze.app import run as _run_analyze

if __name__ == "__main__":
    _run_analyze()
