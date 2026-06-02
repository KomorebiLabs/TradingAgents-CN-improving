"""
Try to scrape THS HTML page for concept constituents.
THS URL pattern: http://q.10jqka.com.cn/gn/detail/code/309121/
"""
import requests
from tradingagents.screener.http_spoof import patch_requests_browser_headers
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "http://q.10jqka.com.cn/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# AI PC = 309121
url = "http://q.10jqka.com.cn/gn/detail/code/309121/"

print("Fetching THS page for AI PC...")
with patch_requests_browser_headers():
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        print(f"Status: {resp.status_code}")
        content = resp.text
        print(f"Content length: {len(content)}")
        
        # Look for stock codes in the HTML
        # THS typically uses patterns like: "000001", "600519"
        # Search for 6-digit stock codes
        stock_codes = re.findall(r'\b\d{6}\b', content)
        unique_codes = sorted(set(stock_codes))
        print(f"\n6-digit codes found: {len(unique_codes)}")
        # Filter to likely stock codes (A股 range)
        a_stock = [c for c in unique_codes if c.startswith(('0', '3', '6', '8'))]
        print(f"Likely A-share codes: {len(a_stock)}")
        print(f"Sample: {a_stock[:20]}")
        
        # Also look for table data patterns
        # THS stock table usually has rows with stock info
        # Look for patterns like "000002" near "万科"
        if '万科' in content:
            idx = content.find('万科')
            print(f"\n万科 context: {content[max(0,idx-50):idx+50]}")
            
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
