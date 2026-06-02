"""
Minimal test script to diagnose fetch_concept_constituents issue.
Tests what columns each API returns for hot concepts like "AI PC".
"""
import sys
sys.path.insert(0, '.')

from tradingagents.screener.data_access import ScreenerDataAccess

da = ScreenerDataAccess()

test_concepts = ["AI PC", "AI语料", "人工智能"]

for concept_name in test_concepts:
    print(f"\n{'='*60}")
    print(f"Testing concept: {concept_name}")
    print('='*60)
    
    df = da.fetch_concept_constituents(concept_name)
    
    if df is None:
        print("Result: None")
    elif getattr(df, 'empty', True):
        print("Result: Empty DataFrame")
    else:
        print(f"Result: DataFrame with shape {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        print(f"\nSource: {df['source'].iloc[0] if 'source' in df.columns else 'N/A'}")
        print(f"\nFirst 3 rows:")
        print(df.head(3).to_string())
