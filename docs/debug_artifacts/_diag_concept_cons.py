"""
Test actual constituent APIs for concept boards.
"""
import akshare as ak

test_concepts = ["AI PC", "AI语料", "人工智能", "半导体", "机器人"]

print("=" * 70)
print("Testing stock_board_concept_cons_ths (THS constituents)")
print("=" * 70)
for concept in test_concepts:
    try:
        df = ak.stock_board_concept_cons_ths(symbol=concept)
        print(f"\n{concept}: shape={df.shape if df is not None else None}")
        if df is not None and not df.empty:
            print(f"  Columns: {df.columns.tolist()}")
            print(df.head(3).to_string())
    except AttributeError as e:
        print(f"\n{concept}: ATTR_ERROR - function not found: {e}")
    except Exception as e:
        print(f"\n{concept}: ERROR - {type(e).__name__}: {e}")

print("\n" + "=" * 70)
print("Testing stock_board_concept_cons_em (EastMoney constituents)")
print("=" * 70)
for concept in test_concepts:
    try:
        df = ak.stock_board_concept_cons_em(symbol=concept)
        print(f"\n{concept}: shape={df.shape if df is not None else None}")
        if df is not None and not df.empty:
            print(f"  Columns: {df.columns.tolist()}")
            print(df.head(3).to_string())
    except Exception as e:
        print(f"\n{concept}: ERROR - {type(e).__name__}: {e}")
