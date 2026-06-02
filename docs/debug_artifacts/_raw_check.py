"""Check raw bytes of current cache file."""
from pathlib import Path

cache_file = Path.home() / ".tradingagents" / "cache" / "screener" / "names_20260508.json"
raw = open(cache_file, "rb").read()

print(f"File size: {len(raw)} bytes")
print(f"\nFirst 200 bytes (hex):")
for i in range(0, min(200, len(raw)), 20):
    hex_part = raw[i:i+20].hex()
    print(f"  offset {i:4d}: {hex_part}")

# Try decoding the first ~50 bytes to see what language it looks like
text_utf8 = raw[:200].decode("utf-8", errors="replace")
print(f"\nFirst 200 chars as UTF-8 (replace errors):")
print(text_utf8[:200])

# Now let's see: the file contains Chinese chars in UTF-8 bytes
# e5b9b3 = 平 (U+5E73)
# e5ae89 = 安 (U+5B89)
# e993b6 = 银 (U+94F6)
# e8a18c = 行 (U+884C)
expected = "平 安 银 行".encode("utf-8").hex()
print(f"\nExpected hex for '平安银行': {expected}")
# Search for this pattern in the file
idx = raw.find(b'\xe5\xb9\xb3\xe5\xae\x89')  # 平安 in UTF-8
print(f"Found '平安' in file: {idx}")
