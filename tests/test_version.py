"""Version consistency: pyproject.toml is the single source of truth."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _pyproject_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    try:
        import tomllib  # Python 3.11+

        return tomllib.loads(text)["project"]["version"]
    except ImportError:
        match = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
        assert match, "could not locate version in pyproject.toml"
        return match.group(1)


@pytest.mark.smoke
def test_package_version_matches_pyproject():
    import tradingagents

    assert tradingagents.__version__ == _pyproject_version(), (
        "tradingagents.__version__ must come from package metadata (pyproject.toml). "
        "Do not hardcode version constants."
    )


@pytest.mark.smoke
def test_no_hardcoded_version_drift():
    """No handwritten __version__ literals outside the metadata lookup."""
    import tradingagents

    pkg_init = Path(tradingagents.__file__).parent / "__init__.py"
    main_mod = Path(tradingagents.__file__).parent / "__main__.py"
    for path in (pkg_init, main_mod):
        text = path.read_text(encoding="utf-8")
        # "0.0.0+source" is the sanctioned not-installed fallback, not drift.
        assert not re.search(r'__version__\s*=\s*"(?!0\.0\.0\+source")[0-9]', text), (
            f"{path.name} contains a hardcoded __version__ literal"
        )
