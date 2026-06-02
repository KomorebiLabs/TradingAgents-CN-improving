# DIAG: Check if garbling is a display issue or data issue
import akshare as ak

df = ak.stock_info_a_code_name()

# Check the first name's Unicode codepoints
first_name = df['name'].iloc[0]
print('Raw repr:', repr(first_name))
print('First 3 chars codepoints:')
for ch in first_name[:3]:
    print(f'  char={ch!r}  unicode={ord(ch):#06x}')

# Also check the akshare file it downloads
import os, glob
akshare_dir = glob.glob(os.path.expanduser('~/.akshare/') + '**/*stock*a*code*name*', recursive=True)
print('\nAkshare cache files:', akshare_dir)

# Check the raw bytes of the first entry
name_bytes = first_name.encode('utf-8')
print('\nUTF-8 bytes:', name_bytes.hex())

# What encoding produces the garbled output?
# 贵州茅台 in GBK: \xb9\xf3\xd6\xdd\xc3\xa9\xcc\xa8
gbk_bytes = b'\xb9\xf3\xd6\xdd\xc3\xa9\xcc\xa8'
print('\nGBK decoded:', gbk_bytes.decode('gbk'))
print('GBK bytes hex:', gbk_bytes.hex())

# Check: is the data in memory correct but display wrong?
# The 'repr' should show the actual memory content
if '平' in repr(first_name) or '\u5e73' in repr(first_name):
    print('\n==> Data in memory IS CORRECT (contains real Unicode for 平安)')
else:
    print('\n==> Data in memory IS GARBLED (does not contain real Unicode)')

# Print with ascii escapes to avoid console encoding issues
print('\nASCII safe:', ascii(first_name))
