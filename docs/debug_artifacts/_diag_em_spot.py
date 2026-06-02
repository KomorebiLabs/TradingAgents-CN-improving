"""
Test if EM spot API works (separate endpoint from cons).
"""
import akshare as ak
from tradingagents.screener.http_spoof import patch_requests_browser_headers
import time

# Test spot_em
print("=== Testing stock_board_concept_spot_em ===")
for concept in ['AI PC', 'AI', 'AIPC']:
    try:
        with patch_requests_browser_headers():
            time.sleep(1)
            df = ak.stock_board_concept_spot_em(symbol=concept)
            print(f"{concept}: shape={df.shape if df is not None else None}")
            if df is not None and not df.empty:
                print(f"  Columns: {df.columns.tolist()}")
                print(df.head(2).to_string())
    except Exception as e:
        print(f"{concept}: {type(e).__name__}: {e}")
    print()

# Test if THS info API returns stocks (it showed 10 rows)
print("=== THS info for AI PC (checking for stock columns) ===")
try:
    df = ak.stock_board_concept_info_ths(symbol='AI PC')
    print(f"Shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")
    print(df.to_string())
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
