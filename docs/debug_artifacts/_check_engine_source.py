# Check if engine.py code is actually what we think
import inspect
from tradingagents.screener.engine import ScreenerEngine

src = inspect.getsource(ScreenerEngine.run)
# Find the name injection section
lines = src.split('\n')
in_injection = False
for i, line in enumerate(lines):
    if '_inject_name' in line or 'inject_name' in line or 'resolver.resolve' in line:
        in_injection = True
    if in_injection:
        print(f"Line {i}: {line}")
        if i > 20:
            break
