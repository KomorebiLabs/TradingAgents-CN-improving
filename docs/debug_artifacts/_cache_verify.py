# Verify cache files and akshare data quality
from pathlib import Path
import json

out = Path.home() / '.tradingagents' / 'cache' / 'screener' / '_cache_verify.txt'
out.parent.mkdir(parents=True, exist_ok=True)

with open(out, 'w', encoding='utf-8') as f:
    def log(msg):
        f.write(msg + '\n')

    cache = Path.home() / '.tradingagents' / 'cache' / 'screener'

    for cf in sorted(cache.glob('names_*.json')):
        if cf.stem.startswith('names_20'):
            log(f"=== {cf.name} ===")
            try:
                with open(cf, 'r', encoding='utf-8') as jf:
                    data = json.load(jf)
                names = data.get('names', {})
                log(f"  Size: {len(names)}")
                log(f"  Date tag: {data.get('date', 'NO_DATE')}")
                for code in ['600519', '000001', '000002']:
                    name = names.get(code, 'NOT_FOUND')
                    hex_val = name.encode('utf-8', errors='replace').hex()
                    log(f"  {code}: {name!r} (hex={hex_val})")
            except Exception as e:
                log(f"  ERROR: {e}")
            log("")

    # Now test akshare directly
    log("=== akshare.stock_info_a_code_name test ===")
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        log(f"  Fetched {len(df)} stocks")
        log(f"  Columns: {list(df.columns)}")
        for _, row in df.iterrows():
            code = str(row['code']).strip()
            if code in ['600519', '000001', '000002']:
                name = str(row['name']).strip()
                hex_val = name.encode('utf-8', errors='replace').hex()
                log(f"  {code}: {name!r} (hex={hex_val})")
    except Exception as e:
        log(f"  ERROR: {e}")
        import traceback
        traceback.print_exc(file=f)

    # And test the CSI API
    log("\n=== akshare CSI index API test ===")
    try:
        df_csi = ak.index_stock_cons_weight_csindex(symbol='000300')
        log(f"  Fetched {len(df_csi)} CSI300 stocks")
        log(f"  Columns: {list(df_csi.columns)}")
        for _, row in df_csi.head(2).iterrows():
            log(f"  row[4]={row.iloc[4]!r}, row[5]={row.iloc[5]!r}")
    except Exception as e:
        log(f"  ERROR: {e}")

print("Written to:", out)
