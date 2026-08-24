"""B3: user portfolio context loader (~/.tradingagents/portfolio.json).

Schema:
    {"holdings": [{"ticker": "600519", "weight": 0.08}, ...],
     "constraints": {"max_single": 0.10, "max_industry": 0.30, "cash_ratio": 0.2}}

Weights are fractions of portfolio value; total must not exceed 1.0.
Returns None when the file is absent (single-stock mode, behavior unchanged).
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


def load_portfolio() -> Optional[Dict[str, Any]]:
    config_dir = Path.home() / ".tradingagents"
    yaml_path = config_dir / "portfolio.yaml"
    json_path = config_dir / "portfolio.json"
    path = yaml_path if yaml_path.is_file() else json_path
    if not path.is_file():
        return None
    try:
        if path.suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        logger.warning("[portfolio] unreadable, continuing without portfolio context: %s", exc)
        return None
    if not isinstance(data, dict):
        logger.warning("[portfolio] top-level config must be an object")
        return None

    holdings = []
    for raw in data.get("holdings") or []:
        if not isinstance(raw, dict) or not raw.get("ticker"):
            continue
        try:
            weight = float(raw.get("weight", 0.0))
        except (TypeError, ValueError):
            logger.warning("[portfolio] invalid weight for %s", raw.get("ticker"))
            return None
        if not math.isfinite(weight) or weight < 0:
            logger.warning("[portfolio] negative or non-finite weight for %s", raw.get("ticker"))
            return None
        holding = {"ticker": str(raw["ticker"]).strip(), "weight": weight}
        if raw.get("industry"):
            holding["industry"] = str(raw["industry"]).strip()
        holdings.append(holding)
    constraints_raw = data.get("constraints") or {}
    constraints = {}
    for key in ("max_single", "max_industry", "cash_ratio"):
        v = constraints_raw.get(key)
        if isinstance(v, (int, float)) and 0 < float(v) <= 1:
            constraints[key] = float(v)

    total = sum(h["weight"] for h in holdings)
    if total > 1.0 + 1e-9:
        logger.warning("[portfolio] holdings sum %.2f > 100%%; file rejected", total)
        return None
    return {"holdings": holdings, "constraints": constraints}
