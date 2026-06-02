# Check if ScreenerEngine.run is a bound method or standalone function
from tradingagents.screener.engine import ScreenerEngine
import inspect

print("ScreenerEngine.run:", ScreenerEngine.run)
print("Type:", type(ScreenerEngine.run))

# Check if it's a method or function
import types
if isinstance(ScreenerEngine.run, types.FunctionType):
    print("It's a function (not a method)")
else:
    print("It's a bound method")

# Check the source of run
src = inspect.getsource(ScreenerEngine.run)
print("First line of run:", src.split('\n')[0])

# More importantly: check if run is a method of the class
print("\nrun in ScreenerEngine.__dict__:", 'run' in ScreenerEngine.__dict__)
print("run from module:", hasattr(ScreenerEngine, 'run'))

# Check if the engine module has run as a standalone function
import tradingagents.screener.engine as eng
if hasattr(eng, 'run'):
    print("'run' exists in engine module (standalone function)")
    src2 = inspect.getsource(eng.run)
    print("First line of module.run:", src2.split('\n')[0])
