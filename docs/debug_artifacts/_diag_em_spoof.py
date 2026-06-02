"""
Test EM constituents with http_spoof browser headers.
"""
import requests
from tradingagents.screener.http_spoof import patch_requests_browser_headers

url = "https://29.push2.eastmoney.com/api/qt/clist/get"
params = {
    "pn": 1, "pz": 50, "po": 1, "np": 1,
    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
    "fltt": 2, "invt": 2, "fid": "f3",
    "fs": "b:BK1164",  # AIPC board code
    "fields": "f2,f3,f12,f14,f5,f6",
}

print("Testing EM constituents with http_spoof headers...")
with patch_requests_browser_headers():
    try:
        resp = requests.get(url, params=params, timeout=15)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        stocks = data.get("data", {}).get("diff", [])
        print(f"Stocks returned: {len(stocks)}")
        for s in stocks[:5]:
            print(f"  {s.get('f14')} ({s.get('f12')}) - change: {s.get('f3')}%")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

# Also try the AkShare EM cons with spoof headers
print("\nTrying AkShare EM cons with spoof headers...")
import akshare as ak
from tradingagents.screener.http_spoof import patch_requests_browser_headers
with patch_requests_browser_headers():
    try:
        df = ak.stock_board_concept_cons_em(symbol='AIPC')
        print(f"Shape: {df.shape if df is not None else None}")
        if df is not None and not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(df.head(3).to_string())
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
