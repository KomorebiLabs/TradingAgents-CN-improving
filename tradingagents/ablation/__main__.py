"""CLI: python -m tradingagents.ablation --tickers 600519,000001 --repeat 2

Runs the ablation matrix with the REAL AnalysisService (needs an LLM API key —
OPENAI/GOOGLE/DEEPSEEK/etc.; consumes tokens). Writes a markdown report to
<repo>/reports/ablation/<timestamp>.md
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tradingagents.ablation", description="Multi-agent ablation experiment (R4)")
    parser.add_argument("--tickers", default="600519,000001,300750", help="comma-separated A-share codes")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="analysis date")
    parser.add_argument("--repeat", type=int, default=2, help="repeats per cell (consistency)")
    parser.add_argument("--provider", default="deepseek", help="llm provider (deepseek/openai/google/...)")
    parser.add_argument("--out", default=str(_PROJECT_ROOT / "reports" / "ablation"), help="output directory")
    args = parser.parse_args(argv)

    from tradingagents.ablation.configs import build_matrix
    from tradingagents.ablation.report import build_report
    from tradingagents.ablation.runner import run_configuration
    from tradingagents.application.service import AnalysisService

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    matrix = build_matrix(provider=args.provider)
    service = AnalysisService()

    print(f"[ablation] matrix={[c.name for c in matrix]} repeat={args.repeat} provider={args.provider}")
    cells = []
    for ticker in tickers:
        for cfg in matrix:
            print(f"[ablation] running {cfg.name} on {ticker} x{args.repeat} ...")
            cell = run_configuration(
                service, ticker, args.date, cfg,
                n_repeat=args.repeat, provider=args.provider,
            )
            cells.append(cell)
            print(f"   -> decisions: {cell['aggregate']['decisions']} "
                  f"consistency={cell['aggregate']['consistency']}")

    md = build_report(
        f"tickers={tickers} provider={args.provider}",
        cells,
        n_repeat=args.repeat,
        note="Real LLM runs — token costs apply.",
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"ablation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"[ablation] report -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
