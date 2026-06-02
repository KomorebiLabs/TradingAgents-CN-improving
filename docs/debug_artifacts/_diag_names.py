# DIAG: Find clean UTF-8 source for company names
import requests

# Try Sina A-share list - it returns \uXXXX encoded JSON (clean UTF-8)
print("=== Sina A-share list ===")
try:
    url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple?page=1&num=2000&sort=symbol&asc=1&node=hs_a&symbol=&_s_r_a=page'
    resp = requests.get(url, timeout=15)
    stocks = resp.json()
    name_map = {s['symbol']: s['name'] for s in stocks}
    print('Total fetched:', len(stocks))
    for code in ['600519', '000001', 'sh600519', 'sz000001']:
        print(f'  {code}: {name_map.get(code, "NOT_FOUND")}')
except Exception as e:
    print('Sina error:', e)

# Try EastMoney
print("\n=== EastMoney list ===")
try:
    url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=2000&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f12,f14'
    resp = requests.get(url, timeout=15)
    data = resp.json()
    items = data['data']['diff']
    name_map2 = {item['f12']: item['f14'] for item in items}
    print('Total fetched:', len(items))
    for code in ['600519', '000001', '688981']:
        print(f'  {code}: {name_map2.get(code, "NOT_FOUND")}')
except Exception as e:
    print('EastMoney error:', e)
