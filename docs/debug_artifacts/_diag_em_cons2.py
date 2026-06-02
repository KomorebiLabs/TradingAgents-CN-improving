"""
Try to get Sina concept classification (Chinese concepts only).
Also try EM with the correct board code.
"""
import akshare as ak
import requests

# Try Sina concept classify with different approach
print("=== Sina concept classify (概念分类) ===")
try:
    df = ak.stock_classify_sina(symbol='概念分类')
    print(f"Shape: {df.shape}, Columns: {df.columns.tolist()}")
    if df is not None and not df.empty:
        print(df.head(5).to_string())
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Try EM constituents with AIPC (BK1164 from earlier search)
print("\n=== EM constituents with AIPC (BK1164) ===")
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
try:
    df = ak.stock_board_concept_cons_em(symbol='AIPC')
    print(f"Shape: {df.shape if df is not None else None}, Columns: {df.columns.tolist() if df is not None and not df.empty else 'N/A'}")
    if df is not None and not df.empty:
        print(df.head(3).to_string())
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Try direct HTTP to EM constituents API with BK1164
print("\n=== Direct HTTP EM constituents (BK1164) ===")
try:
    url = "https://29.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": 1, "pz": 50, "po": 1, "np": 1,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2, "invt": 2, "fid": "f3",
        "fs": "b:BK1164",  # AIPC board code
        "fields": "f2,f3,f12,f14,f5,f6",
    }
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    stocks = data.get("data", {}).get("diff", [])
    print(f"Stocks returned: {len(stocks)}")
    for s in stocks[:5]:
        print(f"  {s.get('f14')} ({s.get('f12')}) - change: {s.get('f3')}%")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
