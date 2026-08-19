"""Ablation stability analytics (R4): decision consistency + confidence spread."""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any, Dict, List


def aggregate_outcomes(outcomes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate repeated runs of one cell.

    - ``decisions``: {decision: count};
    - ``consistency``: fraction agreeing with the majority class (1.0 = fully
      stable across repeats, 0 = fully split);
    - ``confidence*``: mean / std when confidence is populated (real score);
    - ``avg_elapsed``: seconds per run;
    - ``avg_route_events`` / ``compression_rate``: pipeline depth + cost.
    """
    decisions = [o.get("decision") for o in outcomes if o.get("decision") and o["decision"] != "N/A"]
    counts = Counter(decisions)
    n = len(decisions)
    consistency = (max(counts.values()) / n) if n else 0.0

    confs = [float(o["confidence"]) for o in outcomes if o.get("confidence") is not None]
    elapseds = [float(o.get("elapsed", 0.0)) for o in outcomes]
    events = [int(o.get("route_events", 0)) for o in outcomes]
    comps = [int(o.get("compressions", 0)) for o in outcomes]

    return {
        "n": n,
        "decisions": dict(counts),
        "consistency": round(consistency, 3),
        "confidence_mean": round(statistics.mean(confs), 2) if confs else None,
        "confidence_std": round(statistics.pstdev(confs), 2) if len(confs) > 1 else None,
        "avg_elapsed": round(statistics.mean(elapseds), 1) if elapseds else 0.0,
        "avg_route_events": round(statistics.mean(events), 1) if events else 0,
        "compression_rate": round(sum(comps) / sum(events), 3) if sum(events) else 0.0,
    }
