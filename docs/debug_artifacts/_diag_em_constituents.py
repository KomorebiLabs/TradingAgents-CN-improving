"""
Test EastMoney constituents API with proper headers and retry.
"""
import requests
import time
import random

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# First, get the board list to find AI PC code
board_url = "https://push2.eastmoney.com/api/qt/clist/get"
params = {
    "pn": 1,
    "pz": 50,
    "po": 1,
    "np": 1,
    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
    "fltt": 2,
    "invt": 2,
    "fid": "f3",
    "fs": "m:90+t:3",
    "fields": "f1,f2,f3,f12,f14,f3",
}

print("Getting EM concept board list...")
try:
    resp = requests.get(board_url, params=params, headers=headers, timeout=15)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    boards = data.get("data", {}).get("diff", [])
    print(f"Total boards: {len(boards)}")
    # Find AI PC
    for b in boards:
        name = b.get("f14", "")
        code = b.get("f12", "")
        if "AI" in name or "语料" in name:
            print(f"  Found: {name} ({code})")
except Exception as e:
    print(f"Board list ERROR: {type(e).__name__}: {e}")

# Now try to get constituents for a specific board
# AI PC might be BK06551 based on the URL we found earlier
print("\nTrying AI PC constituents (BK06551)...")
cons_url = "https://29.push2.eastmoney.com/api/qt/clist/get"
cons_params = {
    "pn": 1,
    "pz": 20,
    "po": 1,
    "np": 1,
    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
    "fltt": 2,
    "invt": 2,
    "fid": "f3",
    "fs": "b:BK06551",  # AI PC board
    "fields": "f2,f3,f12,f14,f5,f6",
}

for attempt in range(3):
    try:
        time.sleep(0.5 + random.random())
        resp = requests.get(cons_url, params=cons_params, headers=headers, timeout=15)
        print(f"Attempt {attempt+1} - Status: {resp.status_code}")
        data = resp.json()
        stocks = data.get("data", {}).get("diff", [])
        print(f"Stocks returned: {len(stocks)}")
        if stocks:
            for s in stocks[:5]:
                print(f"  {s.get('f14')} ({s.get('f12')}) - change: {s.get('f3')}%")
        break
    except Exception as e:
        print(f"Attempt {attempt+1} ERROR: {type(e).__name__}: {e}")
