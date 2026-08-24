from types import SimpleNamespace

from tradingagents.screener.engine import ScreenerEngine
from tradingagents.screener.universe import UniverseBuildResult


def test_engine_reuses_data_access_and_refreshes_final_health(monkeypatch):
    captured = {}

    class FakeDataAccess:
        def __init__(self):
            self.phase = "probe"

        def validate_interface_assumptions(self, trade_date=None):
            return {"warnings": [], "request_stats": {}, "vendor_health": {"vendor": {"calls": 1}}}

        def get_vendor_health_snapshot(self):
            calls = 5 if self.phase == "names" else 4
            return {"vendor": {"calls": calls, "failures": 1, "last_status": "ok"}}

        def get_cache_stats(self):
            return {"hist_cache_hits": 2, "hist_cache_misses": 1, "hist_cache_hit_ratio": 0.667}

    data_access = FakeDataAccess()

    def fake_universe(mode, config, data_access=None, trade_date=None):
        captured["data_access"] = data_access
        captured["trade_date"] = trade_date
        return UniverseBuildResult(tickers=[], metadata={"source": "test"})

    outcome = SimpleNamespace(cards=[], status="ready", warnings=[])
    strategy = SimpleNamespace(run=lambda _tickers, _date: outcome)
    engine = ScreenerEngine({"stagea_max_input": 0, "stageb_max_input": 0})
    monkeypatch.setattr(engine, "_build_data_access", lambda: data_access)
    monkeypatch.setattr(engine, "_build_strategies", lambda da: (strategy, strategy, strategy))
    monkeypatch.setattr("tradingagents.screener.engine.validate_screener_run", lambda **kwargs: (True, []))
    monkeypatch.setattr("tradingagents.screener.engine.build_screening_universe", fake_universe)
    monkeypatch.setattr(
        "tradingagents.screener.name_resolver.NameResolver.load",
        lambda self: setattr(self._da, "phase", "names"),
    )

    result = engine.run(
        mode="CUSTOM",
        trade_date="2026-08-24",
        enable_deep_analysis=False,
        persist_outputs=False,
    )

    assert captured == {"data_access": data_access, "trade_date": "2026-08-24"}
    assert result.metrics["capability_summary"]["vendor_health"]["vendor"]["calls"] == 5
    assert result.metrics["capability_summary"]["cache_stats"]["hist_cache_hits"] == 2
