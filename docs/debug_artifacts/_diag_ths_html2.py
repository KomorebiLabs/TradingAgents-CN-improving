"""
Verify THS HTML scraping gives correct stock codes for AI PC.
Check if 万科A (000002) and 横店东磁 (002056) are in the AI PC board.
"""
import requests
from tradingagents.screener.http_spoof import patch_requests_browser_headers
import re
import pandas as pd

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "http://q.10jqka.com.cn/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

url = "http://q.10jqka.com.cn/gn/detail/code/309121/"

print("Fetching THS page for AI PC (309121)...")
with patch_requests_browser_headers():
    resp = requests.get(url, headers=headers, timeout=15)
    content = resp.text

# Find all stock entries in the HTML
# The THS page has a table with stock info - let's find patterns
# Pattern: stock codes are in links like /thsf10/xxxxx.htm or in table data

# Method 1: Find all 6-digit codes
codes_found = re.findall(r'\b(\d{6})\b', content)
a_codes = sorted(set(c for c in codes_found if c.startswith(('0', '3', '6', '8')) and len(c) == 6))
print(f"\nTotal A-share codes found: {len(a_codes)}")

# Check for specific stocks
target_stocks = ['000002', '002056', '000429', '002032', '000001', '600519']
for code in target_stocks:
    if code in a_codes:
        print(f"  {code}: FOUND")
    else:
        print(f"  {code}: NOT FOUND")

# Method 2: Try to parse table rows
# Look for the stock list table
print("\n--- Trying to find stock table ---")
# The table often has specific class or id
table_patterns = [
    r'class="board-infos".*?<table>(.*?)</table>',
    r'<tbody>(.*?)</tbody>',
]
for pattern in table_patterns:
    match = re.search(pattern, content, re.DOTALL)
    if match:
        print(f"Found pattern: {pattern[:50]}")
        table_content = match.group(1)
        # Extract rows
        rows = re.findall(r'<tr>(.*?)</tr>', table_content, re.DOTALL)
        print(f"  Rows found: {len(rows)}")
        if rows:
            print(f"  First row: {rows[0][:200]}")

# Method 3: Look for JSON data embedded in the page
json_patterns = [
    r'stockList\s*=\s*(\[.*?\]);',
    r'"stockList"\s*:\s*(\[.*?\])',
    r'data\s*=\s*(\{.*?\})',
]
for pattern in json_patterns:
    match = re.search(pattern, content, re.DOTALL)
    if match:
        print(f"\nFound JSON pattern: {pattern[:40]}")
        try:
            import json
            data = json.loads(match.group(1))
            print(f"  Data type: {type(data)}, length: {len(data) if isinstance(data, list) else 'N/A'}")
            if isinstance(data, list) and data:
                print(f"  First item: {str(data[0])[:200]}")
        except:
            print(f"  Could not parse JSON")

# Method 4: Look for data in script tags
print("\n--- Looking for data in script tags ---")
scripts = re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
for i, script in enumerate(scripts):
    if 'stock' in script.lower() or 'code' in script.lower():
        # Find stock codes in script
        codes_in_script = re.findall(r'\b(\d{6})\b', script)
        if codes_in_script:
            a_in_script = [c for c in codes_in_script if c.startswith(('0', '3', '6', '8'))]
            print(f"  Script {i}: {len(a_in_script)} A-share codes, e.g., {a_in_script[:5]}")
            # Check for target stocks
            for code in target_stocks:
                if code in a_in_script:
                    # Find context
                    idx = script.find(code)
                    print(f"    {code} context: ...{script[max(0,idx-30):idx+50]}...")
