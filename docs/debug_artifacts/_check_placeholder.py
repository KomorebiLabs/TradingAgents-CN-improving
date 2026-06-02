# Check what placeholder_name does
import sys
sys.path.insert(0, 'd:/cursor/HarmonyOS/Github project/TradingAgents-main')

# Find placeholder_name
from tradingagents.screener.strategies.policy import placeholder_name
print("placeholder_name('600519') =", repr(placeholder_name('600519')))
print("placeholder_name('sh600519') =", repr(placeholder_name('sh600519')))
print("placeholder_name('000001') =", repr(placeholder_name('000001')))

# Check _strip_suffix behavior
def _strip_suffix(code):
    if "." in code:
        code = code.split(".")[0]
    return code

print("\n_strip_suffix('600519.SH') =", repr(_strip_suffix('600519.SH')))
print("_strip_suffix('000001.SZ') =", repr(_strip_suffix('000001.SZ')))

# Check what raw_code is on a card
from tradingagents.screener.strategies.policy import PolicyStrategy, PolicyAccessReady

class FakeDA(PolicyAccessReady):
    def validate_interface_assumptions(self, trade_date=None):
        return {
            "concept_list_verified": False,
            "strategy_capabilities": {
                "policy": {"status_hint": "ready", "primary_dependencies": {}}
            },
            "warnings": [], "freshness": [],
        }
    def fetch_concept_boards(self):
        import pandas as pd
        return pd.DataFrame({"name": ["test"], "code": ["T1"]})
    def fetch_policy_news_baidu(self, *a, **kw):
        import pandas as pd
        return pd.DataFrame({"事件": ["AI news"]})
    def fetch_concept_constituents(self, name):
        return None

strategy = PolicyStrategy(FakeDA(), config={})
outcome = strategy.run(["600519", "000001"], "2026-05-08")

for card in outcome.cards:
    print(f"\nCard ticker={card.ticker!r}, raw_code={card.raw_code!r}, company_name={card.company_name!r}")

# Check: what does ticker look like with exchange suffix?
# And what does resolver.resolve() return for each format?
from tradingagents.screener.name_resolver import NameResolver
resolver = NameResolver(trade_date='2026-05-08')
resolver.load()
print(f"\nResolver source: {resolver.source}")
print(f"Resolver cache has '600519': {'600519' in resolver._cache}")
print(f"Resolver resolve('600519'): {resolver.resolve('600519')!r}")
print(f"Resolver resolve('sh600519'): {resolver.resolve('sh600519')!r}")
