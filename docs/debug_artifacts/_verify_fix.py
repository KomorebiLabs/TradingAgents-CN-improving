"""
Verification test for the board_rank_unconfirmed fix.
Tests that fetch_concept_constituents returns actual stock codes for hot concepts.
"""
import sys
sys.path.insert(0, '.')

from tradingagents.screener.data_access import ScreenerDataAccess
from tradingagents.screener.strategies.policy import PolicyStrategy

da = ScreenerDataAccess()

test_concepts = ["AI PC", "AI语料", "人工智能"]

print("=" * 70)
print("Testing fetch_concept_constituents after fix")
print("=" * 70)

for concept_name in test_concepts:
    print(f"\n{concept_name}:")
    df = da.fetch_concept_constituents(concept_name)
    
    if df is None:
        print("  Result: None")
    elif getattr(df, 'empty', True):
        print("  Result: Empty DataFrame")
    else:
        print(f"  Shape: {df.shape}")
        print(f"  Columns: {df.columns.tolist()}")
        print(f"  Source: {df['source'].iloc[0] if 'source' in df.columns else 'N/A'}")
        
        # Check for code column
        code_cols = [c for c in df.columns if c.lower() in ['code', '代码']]
        if code_cols:
            print(f"  First 5 codes: {df[code_cols[0]].head(5).tolist()}")

print("\n" + "=" * 70)
print("Testing _normalize_constituent_rows")
print("=" * 70)

for concept_name in test_concepts:
    print(f"\n{concept_name}:")
    df = da.fetch_concept_constituents(concept_name)
    if df is None:
        print("  Constituents: None/empty")
        continue
    
    rows = PolicyStrategy._normalize_constituent_rows(df, max_stocks=5)
    if not rows:
        print("  Normalized rows: empty")
    else:
        print(f"  Normalized rows: {len(rows)}")
        for row in rows:
            print(f"    {row['code']} | {row['name']} | change={row['change_pct']} | turnover={row['turnover']}")

print("\n" + "=" * 70)
print("Testing universe code matching")
print("=" * 70)

# Test if universe codes match constituent codes
test_universe = ["000002", "002056", "000429", "002032", "000001"]
concept_name = "AI PC"

df = da.fetch_concept_constituents(concept_name)
if df is not None:
    rows = PolicyStrategy._normalize_constituent_rows(df, max_stocks=20)
    constituent_codes = {row['code'] for row in rows}
    print(f"\nAI PC constituent codes: {sorted(constituent_codes)}")
    
    for code in test_universe:
        padded = code.zfill(6)
        if padded in constituent_codes:
            print(f"  {code} -> {padded}: MATCH FOUND")
        else:
            print(f"  {code} -> {padded}: NOT FOUND")

print("\n" + "=" * 70)
print("Testing _compute_member_rank_metrics")
print("=" * 70)

for concept_name in ["AI PC", "AI语料"]:
    df = da.fetch_concept_constituents(concept_name)
    if df is None:
        continue
    
    rows = PolicyStrategy._normalize_constituent_rows(df, max_stocks=20)
    concept_constituents = {concept_name: rows}
    
    # Test with a constituent stock
    if rows:
        test_code = rows[0]['code']
        metrics = PolicyStrategy._compute_member_rank_metrics(
            raw_code=test_code,
            concept_name=concept_name,
            concept_constituents=concept_constituents,
        )
        print(f"\n{concept_name} - Testing code {test_code}:")
        print(f"  is_member: {metrics['is_member']}")
        print(f"  rank_position: {metrics['rank_position']}")
        print(f"  top_tier_hit: {metrics['top_tier_hit']}")
        print(f"  board_rank_bucket: {PolicyStrategy._build_board_rank_bucket(metrics)}")
