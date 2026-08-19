"""CLI: python -m tradingagents.eval --tickers 600519,000001 --date 2025-06-02

Builds the known-outcome evaluation set from real history, runs the full
decision chain per case (REAL AnalysisService — needs an LLM API key), and
writes an accuracy + confusion-matrix report to
<repo>/reports/eval/<timestamp>.md
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tradingagents.eval", description="R10 decision-correctness evaluation")
    parser.add_argument("--tickers", default="600519,000001,300750,601318,000858", help="comma-separated A-share codes")
    parser.add_argument("--date", default="2025-06-02", help="evaluation (analysis) date")
    parser.add_argument("--horizon", type=int, default=20, help="forward-return horizon in trading days")
    parser.add_argument("--n", type=int, default=5, help="number of cases to evaluate (<= len(tickers))")
    parser.add_argument("--provider", default="deepseek", help="llm provider")
    parser.add_argument("--out", default=str(_PROJECT_ROOT / "reports" / "eval"), help="output directory")
    args = parser.parse_args(argv)

    from tradingagents.eval.cases import build_case_set
    from tradingagents.eval.report import build_report
    from tradingagents.eval.runner import run_case_set
    from tradingagents.application.service import AnalysisService
    from tradingagents.screener.data_access import ScreenerDataAccess

    da = ScreenerDataAccess({})
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    print(f"[eval] building {args.n} cases on {args.date} horizon={args.horizon}d ...", flush=True)
    cases = build_case_set(da, tickers, args.date, horizon_days=args.horizon, n=args.n)
    print(f"[eval] cases={len(cases)} labels: " +
          ", ".join(f"{c.ticker}:{c.label}({c.horizon_return*100:+.0f}%)" for c in cases))

    service = AnalysisService()
    results = run_case_set(service, cases, provider=args.provider)
    md = build_report(f"date={args.date} provider={args.provider}", results, horizon_days=args.horizon,
                      note="Real LLM runs — token costs apply.")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    out_path.write_text(md, encoding="utf-8")
    print(md)
    print(f"[eval] report -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
