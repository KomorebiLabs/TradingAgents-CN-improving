with open('ast_refined_results.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print('First 10 lines:')
for i, l in enumerate(lines[:10]):
    print('Line ' + str(i) + ': ' + repr(l))
print()
print('Last 10 lines:')
for i, l in enumerate(lines[-10:]):
    print('Line ' + str(len(lines)-10+i) + ': ' + repr(l))