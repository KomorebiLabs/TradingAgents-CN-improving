# Check the actual JSON file written by the latest engine run
from pathlib import Path
import json

out = Path.home() / '.tradingagents' / 'cache' / 'screener' / '_json_check.txt'

with open(out, 'w', encoding='utf-8') as f:
    def log(msg):
        f.write(msg + '\n')

    # Check the most recent screener output
    screener_dir = Path(r'd:\cursor\HarmonyOS\Github project\TradingAgents-main\.tmp_screener_test')
    if screener_dir.exists():
        files = sorted(screener_dir.glob('screener_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            latest = files[0]
            log(f"Latest file: {latest.name}")
            log(f"Modified: {latest.stat().st_mtime}")

            with open(latest, 'rb') as jf:
                raw_bytes = jf.read()

            log(f"File size: {len(raw_bytes)} bytes")

            # Find '600519' in raw bytes
            pos = raw_bytes.find(b'600519')
            if pos > 0:
                snippet = raw_bytes[pos-5:pos+100]
                log(f"Raw bytes around '600519': {snippet}")
                log(f"Hex: {snippet.hex()}")

            # Decode as UTF-8 and search
            try:
                text = raw_bytes.decode('utf-8', errors='replace')
                # Find '贵州茅台' or the garbled version
                if '贵州茅台' in text:
                    log("JSON contains '贵州茅台' (correct Chinese) ✅")
                if 'Proxy 600519' in text:
                    log("JSON contains 'Proxy 600519' (placeholder) ❌")
                if 'Proxy' in text:
                    log(f"'Proxy' found in JSON: {text.count('Proxy')} occurrences")
            except Exception as e:
                log(f"UTF-8 decode error: {e}")

            # Also read as JSON
            with open(latest, 'r', encoding='utf-8') as jf:
                data = json.load(jf)

            for item in data.get('dropped_candidates', [])[:3]:
                ticker = item.get('ticker', '?')
                company = item.get('company_name', 'MISSING')
                # Check actual Unicode codepoints
                if company:
                    hex_val = company.encode('utf-8', errors='replace').hex()
                    has_chinese = any('\u4e00' <= c <= '\u9fff' for c in company)
                    log(f"  {ticker}: {company!r} hex={hex_val[:40]}... chinese={has_chinese}")

print("Written to:", out)
