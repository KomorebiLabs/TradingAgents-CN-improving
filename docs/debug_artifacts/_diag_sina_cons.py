"""
Test Sina board constituents API.
"""
import akshare as ak

# Check Sina functions that might give constituent info
funcs = [f for f in dir(ak) if 'sina' in f.lower()]
print('All Sina functions:')
for f in sorted(funcs):
    if 'concept' in f.lower() or 'board' in f.lower() or 'classify' in f.lower():
        print(f'  {f}')

# Try Sina board concept constituents
try:
    df = ak.stock_board_concept_cons(symbol='AI PC')
    print(f'\nSina board concept cons: shape={df.shape if df is not None else None}')
    if df is not None and not df.empty:
        print(f'Columns: {df.columns.tolist()}')
        print(df.head(3).to_string())
except Exception as e:
    print(f'\nSina cons ERROR: {type(e).__name__}: {e}')

# Also check if there's any function that gives concept + constituent
try:
    df = ak.stock_board_concept_name_sina()
    print(f'\nSina concept name: shape={df.shape if df is not None else None}')
    if df is not None and not df.empty:
        print(f'Columns: {df.columns.tolist()}')
        print(df.head(3).to_string())
except Exception as e:
    print(f'\nSina concept name ERROR: {type(e).__name__}: {e}')
