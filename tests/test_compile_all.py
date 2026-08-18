"""Compile every active Python file — the cheapest full-repo syntax guard."""

from __future__ import annotations

import pathlib
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCAN_DIRS = [REPO_ROOT / "tradingagents", REPO_ROOT / "cli"]


def _collect_py_files():
    files = []
    for scan_dir in SCAN_DIRS:
        for path in scan_dir.rglob("*.py"):
            parts = set(path.parts)
            if "__pycache__" in parts:
                continue
            # Old commands/screener-cli layers are pending user deletion; skip them.
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel.startswith("tradingagents/commands/") or rel.startswith("tradingagents/screener/cli/"):
                continue
            files.append(path)
    assert files, "no Python files found — scan roots moved?"
    return sorted(files)


@pytest.mark.smoke
@pytest.mark.parametrize("path", _collect_py_files(), ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_file_compiles(path):
    source = path.read_bytes()
    compile(source, str(path), "exec")
