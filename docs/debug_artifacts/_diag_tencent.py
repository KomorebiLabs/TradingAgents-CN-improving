# DIAG: Test Tencent GBK directly
import requests

print("=== Tencent raw bytes ===")
url = 'https://qt.gtimg.cn/q=sh600519'
resp = requests.get(url, timeout=10)
raw = resp.content
print('Raw:', raw[:100])

# Decode with GBK explicitly
text_gbk = raw.decode('gbk')
print('Decoded (GBK):', repr(text_gbk[:100]))

# Split
parts = text_gbk.split('~')
print('Name field:', repr(parts[1]))
print('Decoded name:', parts[1])

# Also try with encoding parameter
print("\n=== With encoding=gbk ===")
resp2 = requests.get(url, timeout=10, headers={'Accept-Charset': 'gbk'})
text2 = resp2.text
parts2 = text2.split('~')
print('Name field:', repr(parts2[1]))
