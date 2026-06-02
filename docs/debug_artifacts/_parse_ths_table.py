"""
Parse THS HTML table to extract stock constituents with change_pct and turnover.
"""
import requests
from tradingagents.screener.http_spoof import patch_requests_browser_headers
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "http://q.10jqka.com.cn/",
}

url = "http://q.10jqka.com.cn/gn/detail/code/309121/"

print("Fetching AI PC board page...")
with patch_requests_browser_headers():
    resp = requests.get(url, headers=headers, timeout=15)
    content = resp.text

# Find the stock table tbody
match = re.search(r'<tbody>(.*?)</tbody>', content, re.DOTALL)
if match:
    tbody = match.group(1)
    # Find all rows
    rows = re.findall(r'<tr>(.*?)</tr>', tbody, re.DOTALL)
    print(f"Rows: {len(rows)}")
    
    results = []
    for row_html in rows:
        # Extract cells
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
        if cells:
            # Clean HTML tags from cells
            cleaned = []
            for cell in cells:
                text = re.sub(r'<[^>]+>', '', cell).strip()
                cleaned.append(text)
            results.append(cleaned)
    
    print(f"\nExtracted {len(results)} stocks:")
    for row in results:
        print(f"  {row}")

# Now check the actual THS cons API for comparison
print("\n\n--- Comparing with THS info API ---")
import akshare as ak
try:
    df = ak.stock_board_concept_info_ths(symbol='AI PC')
    print(f"THS info shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")
    if df is not None and not df.empty:
        # Try to decode the garbled column names
        for col in df.columns:
            print(f"  Column: {repr(col)}")
        print(df.to_string())
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
