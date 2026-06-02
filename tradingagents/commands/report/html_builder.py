"""HTML report generator for screener and analyze results.

Bloomberg Terminal inspired dark theme with data-rich tables.
"""

from pathlib import Path
from typing import Any
import json
from datetime import datetime


def generate_html_report(
    title: str,
    results: dict[str, Any],
    output_path: str | Path,
    template: str = "screener",
) -> Path:
    """Generate a self-contained HTML report from screener/analyze results.

    Args:
        title: Report title
        results: Dict containing report data (candidates, scores, signals, etc.)
        output_path: Where to save the HTML file
        template: "screener" or "analyze"
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    html_content = _build_html(title, results, template)
    output_path.write_text(html_content, encoding="utf-8")
    return output_path


def _build_html(title: str, results: dict, template: str) -> str:
    """Build Bloomberg-style HTML report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    css = """
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: #0d1117;
            color: #e6edf3;
            font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
            font-size: 13px;
            line-height: 1.6;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header {
            border-bottom: 2px solid #00d4ff;
            padding-bottom: 16px;
            margin-bottom: 24px;
        }
        .header h1 {
            color: #00d4ff;
            font-size: 24px;
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        .header .subtitle { color: #7d8590; margin-top: 4px; }
        .meta-bar {
            display: flex;
            gap: 24px;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 12px 16px;
            margin-bottom: 24px;
        }
        .meta-item { display: flex; flex-direction: column; }
        .meta-label { color: #7d8590; font-size: 11px; text-transform: uppercase; }
        .meta-value { color: #00d4ff; font-size: 15px; font-weight: bold; }
        .section { margin-bottom: 32px; }
        .section-title {
            color: #00d4ff;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-left: 3px solid #00d4ff;
            padding-left: 10px;
            margin-bottom: 16px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        th {
            background: #161b22;
            color: #f0883e;
            text-align: left;
            padding: 10px 12px;
            border-bottom: 2px solid #30363d;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #21262d;
        }
        tr:hover { background: #161b22; }
        .signal-buy { color: #3fb950; font-weight: bold; }
        .signal-hold { color: #d29922; font-weight: bold; }
        .signal-sell { color: #f85149; font-weight: bold; }
        .score { color: #00d4ff; font-weight: bold; }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        }
        .badge-bull { background: rgba(63, 185, 80, 0.15); color: #3fb950; }
        .badge-bear { background: rgba(248, 81, 73, 0.15); color: #f85149; }
        .badge-neutral { background: rgba(210, 153, 34, 0.15); color: #d29922; }
        .footer {
            border-top: 1px solid #30363d;
            padding-top: 16px;
            margin-top: 40px;
            color: #7d8590;
            font-size: 11px;
        }
    </style>
    """

    body = _build_screener_table(results)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - TradingAgents Report</title>
    <style>{css}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <div class="subtitle">TradingAgents Screener Report</div>
        </div>

        <div class="meta-bar">
            <div class="meta-item">
                <span class="meta-label">Generated</span>
                <span class="meta-value">{timestamp}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Candidates</span>
                <span class="meta-value">{len(results.get('candidates', []))}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Mode</span>
                <span class="meta-value">{results.get('mode', 'N/A')}</span>
            </div>
        </div>

        {body}

        <div class="footer">
            Generated by TradingAgents CLI &bull; Data may be delayed
        </div>
    </div>
</body>
</html>"""


def _build_screener_table(results: dict) -> str:
    """Build HTML table for screener results."""
    candidates = results.get("candidates", [])

    if not candidates:
        return '<div class="section"><div class="section-title">No candidates found</div></div>'

    rows = []
    for i, c in enumerate(candidates, 1):
        score = c.get("score", 0)
        signal = c.get("signal", "HOLD")
        ticker = c.get("ticker", "N/A")
        name = c.get("name", c.get("ticker", "N/A"))

        signal_class = {
            "BUY": "signal-buy",
            "HOLD": "signal-hold",
            "SELL": "signal-sell",
        }.get(signal, "signal-hold")

        reasons = c.get("key_reasons", [])
        if isinstance(reasons, list):
            reasons_html = "<br>".join(f"&bull; {r}" for r in reasons[:3])
        else:
            reasons_html = str(reasons)

        rows.append(f"""<tr>
            <td>{i}</td>
            <td><strong>{ticker}</strong></td>
            <td>{name}</td>
            <td class="{signal_class}">{signal}</td>
            <td class="score">{score:.1f}</td>
            <td style="max-width:400px">{reasons_html}</td>
        </tr>""")

    return f"""
    <div class="section">
        <div class="section-title">Top Candidates</div>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Ticker</th>
                    <th>Name</th>
                    <th>Signal</th>
                    <th>Score</th>
                    <th>Key Reasons</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
    </div>"""


def view_report(path: str):
    """Open HTML report in browser."""
    import webbrowser

    p = Path(path).expanduser().resolve()
    if not p.exists():
        print(f"[red]Report not found: {p}[/red]")
        return

    url = f"file://{p.absolute()}"
    print(f"[cyan]Opening report: {p.name}[/cyan]")
    webbrowser.open(url)
