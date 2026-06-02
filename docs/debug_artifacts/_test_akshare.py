import akshare as ak
import sys
sys.stdout.reconfigure(encoding="utf-8")

df = ak.index_stock_cons_weight_csindex(symbol="000300")
# Check what the DataFrame columns are
print("Columns (by name):", df.columns.tolist())
print("First row by position:")
for i, v in enumerate(df.iloc[0]):
    print(f"  [{i}] = {v!r} (type={type(v).__name__})")
print()
# Check the actual DataFrame dtypes and raw storage
print("Dtypes:", df.dtypes.tolist())
