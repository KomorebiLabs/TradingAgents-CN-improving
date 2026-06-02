# DIAG: Test EastMoney UTF-8 API properly
import requests

# EastMoney UTF-8 JSON API
print("=== EastMoney full A-share list ===")
try:
    # Use the full A-share list endpoint
    url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5000&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f12,f14'
    resp = requests.get(url, timeout=20)
    print('Status:', resp.status_code)
    print('Encoding:', resp.encoding)
    print('Apparent encoding:', resp.apparent_encoding)
    data = resp.json()
    items = data['data']['diff']
    print('Total fetched:', len(items))
    name_map = {item['f12']: item['f14'] for item in items}
    for code in ['600519', '000001', '688981', 'sh600519', 'sz000001']:
        print(f'  {code}: {name_map.get(code, "NOT_FOUND")}')
except Exception as e:
    print('EastMoney error:', e)
    import traceback
    traceback.print_exc()

# Also test Tencent with GBK decoding
print("\n=== Tencent with GBK decode ===")
try:
    url = 'https://qt.gtimg.cn/q=sh600519'
    resp = requests.get(url, timeout=10)
    raw = resp.content
    # The bytes after '~' separator: \xb9\xf3\xd6\xdd\xc3\xa9\xcc\xa8
    # In GBK: \xb9\xf3 = 贵, \xd6\xdd = 州, \xc3\xa9 = 茅, \xcc\xa8 = 台
    text_gbk = raw.decode('gbk')
    parts = text_gbk.split('~')
    print('Name (GBK decoded):', parts[1])
except Exception as e:
    print('Tencent error:', e)
