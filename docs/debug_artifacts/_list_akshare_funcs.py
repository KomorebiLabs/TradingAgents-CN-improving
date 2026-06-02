"""
List ALL functions in akshare that might contain 'stock' and 'board' or 'concept' or 'member' or 'cons'.
"""
import akshare as ak

all_funcs = [f for f in dir(ak) if not f.startswith('_')]
print("=== All akshare functions (board/concept/member/cons related) ===")
for f in sorted(all_funcs):
    if any(k in f.lower() for k in ['board', 'concept', 'member', 'cons', 'classify', 'industry']):
        print(f"  {f}")

# Also check if there's a ths module with different functions
print("\n=== Checking submodules ===")
import pkgutil
for importer, modname, ispkg in pkgutil.iter_modules(ak.__path__):
    if any(k in modname.lower() for k in ['ths', 'board', 'concept', 'stock']):
        print(f"  {modname}")
