"""Historical conclusion memory manager — file-based persistence for cross-session memory."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

DEFAULT_MEMORY_DIR = Path.home() / ".tradingagents" / "memory"
DEFAULT_TTL_DAYS = 7


def _sanitize_ticker(ticker: str) -> str:
    """Remove path separators from ticker to prevent directory traversal."""
    return ticker.replace("/", "_").replace("\\", "_")


def _get_memory_path(
    ticker: str, trade_date: str, memory_dir: Path | None = None
) -> Path:
    """Compute the JSON file path for a given ticker and trade date.

    Filename format: {sanitized_ticker}_{trade_date}.json
    """
    safe_ticker = _sanitize_ticker(ticker)
    if memory_dir is None:
        memory_dir = DEFAULT_MEMORY_DIR
    memory_dir = Path(memory_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir / f"{safe_ticker}_{trade_date}.json"


def _get_latest_for_ticker(
    ticker: str,
    memory_dir: Path | None = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> Optional[Dict[str, Any]]:
    """Find the most recent non-expired memory entry for a ticker.

    Scans memory_dir for files matching "{ticker}_*.json".
    TTL is determined by comparing each file's embedded trade_date with today's date.
    Returns the most recent non-expired entry, or None.
    Silently skips expired and malformed entries.
    """
    if memory_dir is None:
        memory_dir = DEFAULT_MEMORY_DIR
    memory_dir = Path(memory_dir)
    if not memory_dir.exists():
        return None

    safe_ticker = _sanitize_ticker(ticker)
    today = date.today()

    candidates: list[tuple[date, int, Path]] = []
    for f in memory_dir.iterdir():
        if not f.name.startswith(safe_ticker + "_") or not f.name.endswith(".json"):
            continue
        try:
            trade_date_str = f.stem[len(safe_ticker) + 1 :]
            trade_date_obj = date.fromisoformat(trade_date_str)
            age_days = (today - trade_date_obj).days
            if age_days <= ttl_days:
                candidates.append((trade_date_obj, age_days, f))
        except ValueError:
            continue

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    _, _, path = candidates[0]
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_conclusion_summary(
    ticker: str,
    trade_date: str,
    summary: Dict[str, Any],
    memory_dir: Path | None = None,
) -> Path:
    """Write a conclusion summary JSON to disk.

    Returns the path where it was saved.
    """
    path = _get_memory_path(ticker, trade_date, memory_dir)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    return path


def load_historical_conclusion(
    ticker: str,
    ttl_days: int = DEFAULT_TTL_DAYS,
    memory_dir: Path | None = None,
) -> Optional[Dict[str, Any]]:
    """Load the most recent non-expired conclusion for ticker.

    Returns None if no valid entry exists (expired or never analyzed).
    Silently skips expired entries — caller receives None.

    TTL is computed from the file's embedded trade_date against today's date.
    """
    return _get_latest_for_ticker(ticker, memory_dir, ttl_days)
