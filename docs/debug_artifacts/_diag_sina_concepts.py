import akshare as ak

# Check Sina board concept functions
funcs = [f for f in dir(ak) if 'sina' in f.lower() and ('board' in f.lower() or 'concept' in f.lower() or 'classify' in f.lower())]
print('Sina board/concept functions:')
for f in funcs:
    print(f'  {f}')

# Try stock_classify_sina with a concept
try:
    df = ak.stock_classify_sina(symbol='AI PC')
    print(f'\nSina classify AI PC: shape={df.shape if df is not None else None}')
    if df is not None and not df.empty:
        print(f'Columns: {df.columns.tolist()}')
        print(df.head(3).to_string())
except Exception as e:
    print(f'\nSina classify ERROR: {type(e).__name__}: {e}')
