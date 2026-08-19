"""CLI: python -m tradingagents.backtest [--start ...] [--end ...] ...

Runs the signal-driven backtest and writes its report to
<repo>/reports/backtest/<run_id>/ (summary.md + equity_curve.csv/.png).
"""

from __future__ import annotations

import argparse
import sys

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tradingagents.backtest", description="Screener technical-signal backtest")
    parser.add_argument("--start", default="2025-07-01", help="window start YYYY-MM-DD")
    parser.add_argument("--end", default="2026-06-30", help="window end YYYY-MM-DD")
    parser.add_argument("--pool-size", type=int, default=80, help="CSI300 slice size")
    parser.add_argument("--top-k", type=int, default=5, help="stocks held per rebalance")
    parser.add_argument("--rebalance-days", type=int, default=20, help="rebalance frequency (trading days)")
    parser.add_argument("--out", default=str(_PROJECT_ROOT / "reports" / "backtest"), help="output directory")
    parser.add_argument("--smoke", action="store_true", help="tiny pool + few days for a quick smoke run")
    args = parser.parse_args(argv)

    from tradingagents.backtest.engine import BacktestConfig, BacktestEngine
    from tradingagents.backtest.report import save_report
    from tradingagents.screener.data_access import ScreenerDataAccess

    da = ScreenerDataAccess({})
    cfg = BacktestConfig(
        start_date=args.start,
        end_date=args.end,
        pool_size=6 if args.smoke else args.pool_size,
        top_k=3 if args.smoke else args.top_k,
        rebalance_days=10 if args.smoke else args.rebalance_days,
    )
    print(f"[backtest] window={cfg.start_date}..{cfg.end_date} pool={cfg.pool_size} top_k={cfg.top_k} rebal={cfg.rebalance_days}d")
    result = BacktestEngine(da, cfg).run()
    p = result.performance
    print(f"[backtest] total_return={p['total_return']*100:.2f}% sharpe={p['sharpe']:.2f} "
          f"max_dd={p['max_drawdown']*100:.2f}% excess={p['excess_return']*100:.2f}% "
          f"periods={p['periods']}")
    out_dir = save_report(result, Path(args.out) / result.run_id)
    print(f"[backtest] report -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
