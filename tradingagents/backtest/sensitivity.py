"""Parameter sensitivity analysis (R9), built on the R1 backtest engine.

Perturbs key TechnicalStrategy parameters one at a time and records how the
backtest performance responds — turning "feels right" weights/thresholds into
measured sensitivity evidence. Supports grid values around each baseline.

Convention: each perturbation is fed to TechnicalStrategy via
``{"strategies": {"technical": {"thresholds": {<param>: <value>}}}}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from tradingagents.backtest.engine import BacktestConfig, BacktestEngine, build_pool
from tradingagents.screener.data_access import ScreenerDataAccess

__all__ = ["SensitivitySpec", "DEFAULT_SPECS", "SensitivityRunner"]


@dataclass
class SensitivitySpec:
    param: str                 # threshold key inside strategies.technical.thresholds
    baseline: float
    values: List[float]
    label: str = ""


DEFAULT_SPECS: List[SensitivitySpec] = [
    SensitivitySpec("trend_alignment_weight", 0.22, [0.18, 0.22, 0.27]),
    SensitivitySpec("momentum_weight", 0.18, [0.14, 0.18, 0.23]),
    SensitivitySpec("hist_rows_minimum", 30, [20, 30, 45]),
    SensitivitySpec("drawdown_resilience_weight", 0.14, [0.10, 0.14, 0.19]),
]


def build_strategy_config(param: str, value: float) -> Dict[str, Any]:
    """One TechnicalStrategy config with a single parameter override."""
    return {"strategies": {"technical": {"thresholds": {param: value}}}}


class SensitivityRunner:
    """Runs mini backtrack tests for each (param, value) and aggregates metrics."""

    def __init__(
        self,
        data_access: ScreenerDataAccess,
        bt_config: Optional[BacktestConfig] = None,
        specs: Optional[List[SensitivitySpec]] = None,
    ):
        self.da = data_access
        # mini window/pool for tractable sensitivity scans
        self.bt_config = bt_config or BacktestConfig(
            start_date="2025-08-01",
            end_date="2026-06-30",
            pool_size=12,
            top_k=4,
            rebalance_days=20,
        )
        self.specs = specs or DEFAULT_SPECS

    def run_all(self, pool: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        pool = pool or build_pool(self.da, self.bt_config.index_symbol, self.bt_config.pool_size, self.bt_config.seed)
        engine = BacktestEngine(self.da, self.bt_config)
        rows: List[Dict[str, Any]] = []
        for spec in self.specs:
            for value in spec.values:
                result = engine.run(pool=pool, strategy_config=build_strategy_config(spec.param, value))
                p = result.performance
                rows.append(
                    {
                        "param": spec.param,
                        "value": value,
                        "baseline": spec.baseline,
                        "delta_pct": round((value - spec.baseline) / spec.baseline * 100, 1) if spec.baseline else None,
                        "total_return": p.get("total_return", 0.0),
                        "sharpe": p.get("sharpe", 0.0),
                        "max_drawdown": p.get("max_drawdown", 0.0),
                        "excess_return": p.get("excess_return", 0.0),
                    }
                )
        return rows

    def report(self, rows: List[Dict[str, Any]]) -> str:
        lines = [
            "# Parameter Sensitivity Report — Screener Technical Strategy (R9)",
            "",
            f"- Method: one-parameter-at-a-time perturbation around baseline, "
            f"mini backtest pool={self.bt_config.pool_size} window={self.bt_config.start_date}..{self.bt_config.end_date}",
            f"- Parameters perturbed ± ~20% of baseline (no joint interactions shaded).",
            "",
            "| Param | Value (Δ%) | Total Return | Sharpe | Max DD | Excess vs CSI300 |",
            "|---|---|---|---|---|---|",
        ]
        for row in rows:
            delta = f"{row['delta_pct']:+.0f}%" if row["delta_pct"] is not None else "—"
            lines.append(
                f"| {row['param']} | {row['value']} ({delta}) | "
                f"{row['total_return'] * 100:.1f}% | {row['sharpe']:.2f} | "
                f"{row['max_drawdown'] * 100:.1f}% | {row['excess_return'] * 100:.1f}% |"
            )
        lines.append("")
        lines.append(
            "## Reading\n\n- A parameter whose ±20% perturbation barely moves sharpe/return is **robust**; "
            "a parameter that swings them widely is **sensitive** and worth re-calibrating (or documenting the mechanism)."
        )
        lines.append("- Historical results are NOT indicative of future returns.")
        return "\n".join(lines)
