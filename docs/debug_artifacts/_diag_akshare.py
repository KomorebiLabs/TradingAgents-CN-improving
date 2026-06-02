# DIAG: Try akshare stock_info_a_code_name (clean UTF-8)
import akshare as ak

print("=== akshare stock_info_a_code_name ===")
try:
    df = ak.stock_info_a_code_name()
    print('Columns:', list(df.columns))
    print('Shape:', df.shape)
    # Filter for our target stocks
    filtered = df[df.iloc[:, 0].astype(str).str.contains('600519|000001', na=False)]
    print('Filtered:')
    print(filtered.to_string())
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()
