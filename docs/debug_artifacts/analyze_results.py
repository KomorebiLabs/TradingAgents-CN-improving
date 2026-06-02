from collections import Counter
import re

with open('ast_refined_results.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

results = []
for l in lines:
    l = l.strip()
    if 'undefined:' in l:
        results.append(l)

file_counts = Counter()
for r in results:
    parts = r.split(':')
    if len(parts) >= 6:
        # Get the file path - everything before the line number
        # Format: path/to/file:LINE [scope] undefined: name (ctx=...)
        line_num = parts[-5]
        if line_num.isdigit():
            filepath = ':'.join(parts[:-5])
            file_counts[filepath] += 1

print('ERRORS BY FILE:')
print('='*70)
for f, count in sorted(file_counts.items(), key=lambda x: -x[1]):
    if 'TradingAgents-main' in f:
        idx = f.find('TradingAgents-main')
        short_f = f[idx+21:]
    else:
        short_f = f
    print(str(count).rjust(4) + '  ' + short_f)

print()
print('='*70)
print('TOTAL: ' + str(len(results)) + ' undefined name errors')