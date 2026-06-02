import akshare as ak
import inspect
import re

# Get source code of stock_board_concept_info_ths
src = inspect.getsource(ak.stock_board_concept_info_ths)
urls = re.findall(r'https?://[^\s"\']+', src)
print('URLs in stock_board_concept_info_ths:')
for u in urls:
    print(f'  {u}')

# Also check stock_board_concept_cons_em source
src2 = inspect.getsource(ak.stock_board_concept_cons_em)
urls2 = re.findall(r'https?://[^\s"\']+', src2)
print('\nURLs in stock_board_concept_cons_em:')
for u in urls2:
    print(f'  {u}')

# Try to understand what parameters stock_board_concept_info_ths accepts
# by checking its docs
print('\n--- Docstring ---')
print(ak.stock_board_concept_info_ths.__doc__)
