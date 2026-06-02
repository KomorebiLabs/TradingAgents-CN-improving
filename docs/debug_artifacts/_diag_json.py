# DIAG: Write akshare data to JSON and read it back
import akshare as ak
import json
from pathlib import Path

df = ak.stock_info_a_code_name()

# Write to JSON file
test_file = Path.home() / '.tradingagents' / 'cache' / 'screener' / '_diag_names.json'
test_file.parent.mkdir(parents=True, exist_ok=True)

# Filter to target stocks
names = {}
for _, row in df.iterrows():
    code = str(row['code']).strip()
    name = str(row['name']).strip()
    names[code] = name
    if len(names) >= 5000:
        break

with open(test_file, 'w', encoding='utf-8') as f:
    json.dump({'date': 'test', 'names': names}, f, ensure_ascii=False, indent=2)

print('Written to:', test_file)

# Read back and check
with open(test_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

read_names = data['names']
print('Read back', len(read_names), 'names')
for code in ['600519', '000001']:
    print(f'  {code}: {read_names.get(code, "NOT_FOUND")!r}')

# Check raw bytes in file
with open(test_file, 'rb') as f:
    content = f.read()

# Find the bytes for '600519'
code_pos = content.find(b'600519')
if code_pos > 0:
    snippet = content[code_pos:code_pos+50]
    print('\nRaw bytes around 600519:', snippet)
    # Find the name value nearby
    name_pos = content.find(b'"name"', code_pos)
    if name_pos > 0:
        name_snippet = content[name_pos:name_pos+30]
        print('Name field:', name_snippet)
