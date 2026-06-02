"""
Test the exact concept selection logic for Policy strategy.
Simulate _select_policy_concepts with the actual concept list.
"""
import sys
sys.path.insert(0, '.')

from tradingagents.screener.data_access import ScreenerDataAccess
from tradingagents.screener.strategies.policy import PolicyStrategy

da = ScreenerDataAccess()

# Get concept list
concept_df = da.fetch_concept_boards()
print(f"Concept list: shape={concept_df.shape}, columns={concept_df.columns.tolist()}")
print()

# Get news (if available)
news_df = da.fetch_policy_news_baidu("2026-06-02", look_back_days=7, limit=24)
print(f"News: shape={news_df.shape if news_df is not None else None}")
if news_df is not None and not news_df.empty:
    print(f"News columns: {news_df.columns.tolist()}")
    # Print news text
    for col in ['事件', '内容', '标题']:
        if col in news_df.columns:
            print(f"\nNews from column '{col}':")
            for i, val in enumerate(news_df[col].head(5)):
                print(f"  [{i}] {str(val)[:100]}")
            break

print("\n" + "="*70)
print("Testing _select_policy_concepts")
print("="*70)

# Manually simulate the concept selection
selected_concepts, keyword_mode = PolicyStrategy._select_policy_concepts(concept_df, news_df)
print(f"\nSelected concepts: {selected_concepts}")
print(f"Keyword mode: {keyword_mode}")

# Also check what keywords would match
if news_df is not None and not news_df.empty:
    text_columns = [col for col in news_df.columns if str(col) in {"事件", "内容", "标题", "event"}]
    joined = " ".join(
        str(value)
        for col in text_columns
        for value in news_df[col].astype(str).tolist()
    )
    print(f"\nNews text sample: {joined[:500]}...")
    
    # Check what POLICY_KEYWORDS match
    from tradingagents.screener.strategies.policy import POLICY_KEYWORDS
    print("\nPolicy keyword matches in news:")
    for concept_name, keywords in POLICY_KEYWORDS.items():
        hits = [kw for kw in keywords if kw in joined]
        if hits:
            print(f"  {concept_name}: {hits}")

# Now check if 万科A is in any concept's constituents
print("\n" + "="*70)
print("Checking constituent match for 万科A (000002)")
print("="*70)

# Load concept constituents for selected concepts
import time
concept_constituents = {}
for concept_name in selected_concepts[:5]:
    try:
        time.sleep(1)
        df = da.fetch_concept_constituents(concept_name)
        if df is not None and not df.empty:
            print(f"\n{concept_name}: shape={df.shape}, columns={df.columns.tolist()}")
            # Check what columns exist
            code_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['code', '代码', 'symbol'])]
            name_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['name', '名称'])]
            print(f"  Code columns: {code_cols}")
            print(f"  Name columns: {name_cols}")
        else:
            print(f"\n{concept_name}: empty/None")
    except Exception as e:
        print(f"\n{concept_name}: ERROR - {e}")
