import json

with open('.tmp_screener_test/screener_2026-05-05_4d7113b4.json', encoding='utf-8') as f:
    d = json.load(f)

print('name_resolver_source:', d['metrics'].get('name_resolver_source'))
print('name_resolver_warnings:', d['metrics'].get('name_resolver_warnings'))
print()

for c in d['candidates']:
    print('candidate:', c['ticker'], 'name=', c.get('company_name', 'N/A'), 'score=', c.get('overall_score'))

for c in d['dropped_candidates']:
    name = c.get('company_name', 'N/A')
    reason = c.get('reason', '')
    print('dropped:', c.get('ticker'), 'name=', name, 'reason=', reason[:100])
