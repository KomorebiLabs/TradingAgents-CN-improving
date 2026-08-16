"""Smoke tests: imports must be side-effect free (no sys.exit, no stdout noise)."""

from __future__ import annotations

import contextlib
import importlib
import io
import sys

import pytest

CRITICAL_MODULES = [
    "tradingagents",
    "cli",
    "cli.main",
    "cli.main_menu",
    "cli.announcements",
    "cli.report_viewer",
    "cli.analyze.app",
    "cli.analyze.run_impl",
    "cli.screener.app",
    "cli.screener.run_impl",
    "tradingagents.__main__",
    "tradingagents.dataflows.interface",
    "tradingagents.dataflows.config",
    "tradingagents.graph.trading_graph",
    "tradingagents.agents.utils.state_helpers",
]


@pytest.mark.smoke
@pytest.mark.parametrize("module_name", CRITICAL_MODULES)
def test_import_without_side_effects(module_name):
    """Importing must not print, write stderr, or terminate the process."""
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            importlib.import_module(module_name)
    except SystemExit as exc:  # pragma: no cover - this is exactly the regression we guard
        pytest.fail(f"{module_name} called sys.exit({exc.code}) at import time")
    combined = (stdout.getvalue() + stderr.getvalue()).strip()
    assert not combined, f"{module_name} produced import-time output: {combined[:200]!r}"


@pytest.mark.smoke
def test_cli_main_is_importable_after_refactor():
    """The legacy `python -m cli.main` shim must not carry import-time exits."""
    import cli.main  # noqa: F401

    assert not hasattr(cli.main, "_spec"), "old find_spec-based questionary guard leaked back"


@pytest.mark.smoke
def test_unified_cli_registers_screener_subapp():
    """The unified typer app must expose analyze / screener / report commands."""
    from tradingagents.__main__ import app

    registered = {info.name for info in app.registered_commands}
    sub_groups = {info.name for info in app.registered_groups}
    assert "analyze" in registered
    assert "report" in registered
    assert "screener" in sub_groups
