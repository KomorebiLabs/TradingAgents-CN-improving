"""Backtest report generation (R1): markdown summary + equity-curve plot + csv."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Any

import pandas as pd

from tradingagents.backtest.engine import BacktestResult

_METRIC_LABELS: Dict[str, str] = {
    "total_return": "Total Return",
    "annualized_return": "Annualized Return",
    "annualized_vol": "Annualized Volatility",
    "sharpe": "Sharpe (RF=0)",
    "max_drawdown": "Max Drawdown",
    "win_rate": "Daily Win Rate",
    "excess_return": "Excess vs CSI300",
    "periods": "Trading Days",
}


def fmt_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def format_metric(key: str, value: Any) -> str:
    if key == "periods":
        return str(value)
    if key == "sharpe":
        return f"{value:.2f}"
    return fmt_pct(value)


def build_markdown(result: BacktestResult) -> str:
    cfg = result.config
    p = result.performance
    lines: list[str] = []
    lines.append("# Backtest Report — Screener Technical Signal\n")
    lines.append(f"- Run ID: `{result.run_id}`")
    lines.append(f"- Window: {cfg.start_date} → {cfg.end_date} ({p.get('periods', 0)} trading days)")
    lines.append(f"- Pool: CSI300 constituents, capped at {len(result.pool)} (seed={cfg.seed})")
    lines.append(f"- Selection: real `TechnicalStrategy.run` top {cfg.top_k}, rebalanced every {cfg.rebalance_days} days")
    lines.append("- Execution: signal at T close, filled after T+1 close; returns begin on the following interval")
    lines.append(
        f"- Costs: commission {cfg.commission_rate:.4%} each side, "
        f"stamp duty {cfg.stamp_duty_sell:.4%} on sells, slippage {cfg.slippage:.4%} each side"
    )
    lines.append("")

    lines.append("## Execution audit\n")
    lines.append(f"- Turnover: {p.get('turnover', 0.0):.4f}")
    lines.append(f"- Transaction cost deducted: {fmt_pct(p.get('transaction_cost', 0.0))}")
    lines.append(f"- Executed orders: {p.get('executed_orders', 0)}")
    lines.append(f"- Unfilled orders: {p.get('unfilled_orders', 0)}")
    lines.append("")

    lines.append("## Performance\n")
    lines.append("| Metric | Strategy |")
    lines.append("|---|---|")
    for key in ("total_return", "annualized_return", "annualized_vol", "sharpe", "max_drawdown", "win_rate"):
        lines.append(f"| {_METRIC_LABELS.get(key, key)} | {format_metric(key, p.get(key, 0.0))} |")
    bench = " — benchmark unavailable" if result.benchmark is None else " vs CSI300"
    lines.append(f"| {_METRIC_LABELS['excess_return']} | {fmt_pct(p.get('excess_return', 0.0))}{bench} |")
    lines.append("")

    lines.append("## Signals (top holdings per rebalance)\n")
    for log in result.signal_log:
        lines.append(f"- **{log['date']}**: " + ", ".join(log["top"]))
    lines.append("")

    lines.append("## Files\n")
    lines.append("- `equity_curve.csv` — daily normalized strategy nav (and benchmark if available)")
    lines.append("- `equity_curve.png` — strategy vs benchmark equity curves")
    lines.append("- `backtest_artifact.json` — reproducibility metadata and execution audit")
    lines.append("")

    lines.append("## Limitations (documented honestly)\n")
    lines.append(
        "- Only the **technical factor** is backtested (it is the only one reconstructable "
        "from point-in-time OHLCV). Policy / Smart-Money factors need historical concept / "
        "fund-flow snapshots that free vendors do not provide."
    )
    lines.append("- Limit-touch orders are blocked, but suspension checks require historical volume data not yet supplied by this engine.")
    lines.append("- Stock pool uses currently fetched CSI300 constituents; historical constituent snapshots are unavailable, so survivorship bias applies.")
    lines.append("- Historical results are NOT indicative of future returns.")
    return "\n".join(lines)


def plot_equity_curve(result: BacktestResult, out_path: Path) -> None:
    """Matplotlib equity curve (English labels to avoid CJK font issues)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(result.nav.index, result.nav.values, label="Strategy (technical top-k)", linewidth=1.8)
    if result.benchmark is not None:
        bench = result.benchmark.reindex(result.nav.index).ffill()
        bench_norm = bench / bench.iloc[0]
        ax.plot(bench_norm.index, bench_norm.values, label="CSI300", linewidth=1.2, alpha=0.8)
    ax.set_title("Backtest Equity Curve — Screener Technical Signal")
    ax.set_ylabel("Normalized NAV (start = 1)")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def save_report(result: BacktestResult, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.md").write_text(build_markdown(result), encoding="utf-8")

    frame = pd.DataFrame({"strategy": result.nav})
    if result.benchmark is not None:
        bench = result.benchmark.reindex(result.nav.index).ffill()
        if len(bench) >= 2:
            frame["benchmark"] = bench / bench.iloc[0]
    frame.to_csv(out_dir / "equity_curve.csv")

    artifact = {
        "run_id": result.run_id,
        "config": asdict(result.config),
        "metadata": result.artifact_metadata,
        "performance": result.performance,
        "signals": result.signal_log,
        "executions": result.execution_log,
    }
    (out_dir / "backtest_artifact.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    try:
        plot_equity_curve(result, out_dir / "equity_curve.png")
    except Exception:
        pass  # plot optional; csv + md remain

    return out_dir
