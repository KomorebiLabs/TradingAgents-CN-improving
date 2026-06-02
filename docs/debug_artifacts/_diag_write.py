# DIAG: Write akshare data to JSON file (bypass console encoding)
import akshare as ak
import json
from pathlib import Path

# Write output to file instead of stdout
out_file = Path.home() / '.tradingagents' / 'cache' / 'screener' / '_diag_akshare.txt'
out_file.parent.mkdir(parents=True, exist_ok=True)

with open(out_file, 'w', encoding='utf-8') as out:
    try:
        df = ak.stock_info_a_code_name()
        out.write(f"Columns: {list(df.columns)}\n")
        out.write(f"Shape: {df.shape}\n\n")

        # Check first few rows
        for i in range(min(5, len(df))):
            row = df.iloc[i]
            code = str(row['code'])
            name = str(row['name'])
            # Write both raw and escaped
            out.write(f"Row {i}: code={code!r}, name={name!r}\n")

        # Filter for target stocks
        for _, row in df.iterrows():
            code = str(row['code'])
            if code in ['600519', '000001']:
                name = str(row['name'])
                out.write(f"\nTARGET: {code} => name={name!r}\n")
                # Check what bytes are in the name
                name_bytes = name.encode('utf-8')
                out.write(f"  UTF-8 bytes: {name_bytes.hex()}\n")
                # Try decoding as GBK
                try:
                    gbk_bytes = name.encode('latin1')
                    out.write(f"  Latin1 bytes: {gbk_bytes.hex()}\n")
                    out.write(f"  As GBK: {gbk_bytes.decode('gbk')!r}\n")
                except:
                    pass

        out.write("\n=== SUCCESS ===\n")
    except Exception as e:
        out.write(f"ERROR: {e}\n")
        import traceback
        traceback.print_exc(file=out)

print("Written to:", out_file)
