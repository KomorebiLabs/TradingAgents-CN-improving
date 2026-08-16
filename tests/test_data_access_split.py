"""Unit tests for the pure-function layers extracted from ScreenerDataAccess.

Covers: ticker_formats, response_parsers, capability matrix builders —
all offline, all deterministic. These functions were previously untestable
private methods inside the 1905-line god class.
"""

from __future__ import annotations

import json

import pytest

from tradingagents.screener import capability
from tradingagents.screener.response_parsers import (
    parse_tencent_index_lines,
    parse_tencent_kline,
    parse_tencent_quote_lines,
    parse_ths_board_table,
)
from tradingagents.screener.ticker_formats import (
    normalize_date_for_tencent,
    normalize_ticker_for_baostock,
    normalize_ticker_for_sina,
    normalize_ticker_for_tencent,
    normalize_ticker_for_yfinance,
    safe_float,
)


class TestTickerFormats:
    @pytest.mark.parametrize(
        "ticker,expected",
        [
            ("600519", "sh600519"),
            ("000001", "sz000001"),
            ("sz000001", "sz000001"),
            ("sh600519", "sh600519"),
            ("600519.SS", "sh600519"),
            ("000001.SZ", "sz000001"),
            ("688001", "sh688001"),  # STAR market starts with 6
            ("930001", "sh930001"),  # BSE-style 9-prefix
        ],
    )
    def test_sina(self, ticker, expected):
        assert normalize_ticker_for_sina(ticker) == expected

    @pytest.mark.parametrize(
        "ticker,expected",
        [
            ("600519", ("600519", "sh")),
            ("000001", ("000001", "sz")),
            ("sz000001", ("000001", "sz")),
            ("600519.SS", ("600519", "sh")),
        ],
    )
    def test_tencent(self, ticker, expected):
        assert normalize_ticker_for_tencent(ticker) == expected

    @pytest.mark.parametrize(
        "ticker,expected",
        [
            ("600519", "sh.600519"),
            ("000001", "sz.000001"),
            ("sz.000001", "sz.000001"),
            ("sh600519", "sh.600519"),
            ("600519.SS", "sh.600519"),
        ],
    )
    def test_baostock(self, ticker, expected):
        assert normalize_ticker_for_baostock(ticker) == expected

    @pytest.mark.parametrize(
        "ticker,expected",
        [
            ("600519", "600519.SS"),
            ("000001", "000001.SZ"),
            ("sh600519", "600519.SS"),
            ("sz000001", "000001.SZ"),
            ("600519.SS", "600519.SS"),
        ],
    )
    def test_yfinance(self, ticker, expected):
        assert normalize_ticker_for_yfinance(ticker) == expected

    def test_tencent_date_normalization(self):
        assert normalize_date_for_tencent("20260115") == "2026-01-15"
        assert normalize_date_for_tencent("2026-01-15") == "2026-01-15"
        assert normalize_date_for_tencent("") == ""
        assert normalize_date_for_tencent("2026011") == "2026011"  # not 8 digits: passthrough

    def test_safe_float(self):
        assert safe_float("3.14") == 3.14
        assert safe_float(None) is None
        assert safe_float("abc") is None


class TestThsBoardTableParser:
    HTML_FIXTURE = """
    <html><body><table>
    <thead><tr><th>序号</th><th>股票代码</th><th>股票简称</th><th>现价</th><th>涨跌幅</th><th>换手率</th><th>成交额</th></tr></thead>
    <tbody>
      <tr><td>1</td><td>600519</td><td>贵州茅台</td><td>1700.0</td><td>1.23%</td><td>0.5</td><td>23.45</td></tr>
      <tr><td>2</td><td>000001</td><td>平安银行</td><td>10.5</td><td>-0.5%</td><td>1.2</td><td>5.6</td></tr>
      <tr><td>3</td><td>BADCODE</td><td>无效行</td><td>1</td><td>0</td><td>0</td><td>0</td></tr>
    </tbody>
    </table></body></html>
    """

    def test_parses_valid_rows_and_skips_bad_codes(self):
        rows = parse_ths_board_table(self.HTML_FIXTURE, max_stocks=10)
        assert len(rows) == 2  # BADCODE row dropped
        assert rows[0]["code"] == "600519"
        assert rows[0]["name"] == "贵州茅台"
        assert rows[0]["change_pct"] == 1.23
        assert rows[0]["amount"] == pytest.approx(23.45e8)  # 亿 -> 元

    def test_no_tbody_returns_empty(self):
        assert parse_ths_board_table("<html>no table</html>") == []

    def test_max_stocks_limit(self):
        rows = parse_ths_board_table(self.HTML_FIXTURE, max_stocks=1)
        assert len(rows) == 1


class TestTencentParsers:
    def test_kline_roundtrip(self):
        payload = {
            "code": 0,
            "data": {
                "sh600519": {
                    "qfqday": [
                        ["2026-01-14", 1690.0, 1700.5, 1710.0, 1685.0, 25000],
                        ["2026-01-15", 1700.5, 1712.0, 1720.0, 1699.0, 31000],
                    ]
                }
            },
        }
        text = f"var kline_dayqfq={json.dumps(payload)}"
        df = parse_tencent_kline(text, "sh600519", "qfq")
        assert df is not None and len(df) == 2
        assert list(df.columns) == ["date", "open", "close", "high", "low", "volume", "amount"]
        assert df.iloc[0]["close"] == 1700.5
        assert df.iloc[-1]["date"] >= df.iloc[0]["date"]  # sorted

    def test_kline_param_error_returns_none(self):
        assert parse_tencent_kline('var x={"code":0,"msg":"param error","data":[]}', "sh600519", "qfq") is None

    def test_quote_lines(self):
        # 32+ fields to pass the stock-quote minimum
        fields = ["1", "贵州茅台", "sh600519", "1700.0"] + ["0"] * 34
        text = 'v_sh600519="' + "~".join(fields) + '";'
        df = parse_tencent_quote_lines(text)
        assert df is not None
        assert df.iloc[0]["symbol"] == "sh600519"
        assert df.iloc[0]["trade"] == 1700.0
        assert df.iloc[0]["source"] == "tencent_direct"

    def test_quote_lines_too_few_fields(self):
        text = 'v_sz000001="1~平安银行~sz000001~10.5";'
        assert parse_tencent_quote_lines(text) is None

    def test_index_lines(self):
        fields = ["1", "上证指数", "sh000001", "3200.5", "12.3", "0.39", "123456", "x", "456789"]
        text = 'v_s_sh000001="' + "~".join(fields) + '";'
        df = parse_tencent_index_lines(text)
        assert df is not None
        assert df.iloc[0]["price"] == 3200.5
        assert df.iloc[0]["changepercent"] == 0.39


class TestCapabilityBuilders:
    VENDORS = {"enable_yfinance_backup": True, "hist_primary": "tencent_direct"}

    def test_baseline_shape(self):
        summary = {"hist_primary_vendor": "tencent_direct"}
        baseline = capability.build_vendor_baseline(summary, self.VENDORS)
        assert set(baseline) == {"history", "spot", "concept", "industry", "fund_flow", "index", "tick", "auxiliary"}
        assert baseline["history"]["last_resort"] == "yfinance"

    def test_baseline_yfinance_disabled(self):
        baseline = capability.build_vendor_baseline({}, {"enable_yfinance_backup": False})
        assert baseline["history"]["last_resort"] == ""

    def test_legacy_aliases_fill_compatibility_keys(self):
        summary = {"fund_flow_verified": True, "probe_results": {"hist_yfinance": {"ok": True}}}
        out = capability.apply_legacy_aliases(summary, self.VENDORS)
        assert out["fund_flow_bulk_verified"] is True
        assert out["yfinance_hist_verified"] is True
        assert out["hist_fetch_fallback_vendor"] == "yfinance"

    def test_strategy_capabilities_readiness(self):
        summary = {
            "hist_fetch_verified": True,
            "fund_flow_verified": True,
            "concept_list_verified": False,
        }
        caps = capability.build_strategy_capabilities(summary, self.VENDORS)
        assert caps["technical"]["status_hint"] == "ready"
        assert caps["policy"]["status_hint"] == "degraded"
        assert caps["smart_money"]["status_hint"] == "ready"

    def test_exception_classification(self):
        assert capability.classify_probe_exception("HTTPSConnectionPool MaxRetryError") == "network_unreachable"
        assert capability.classify_probe_exception("ReadTimeout: timed out") == "timeout"
        assert capability.classify_probe_exception("YFRateLimitError too many requests") == "rate_limited"
        assert capability.classify_probe_exception("something odd") == "unknown_error"

    def test_probe_single_success_and_failure(self):
        import pandas as pd

        result = capability.probe_single("hist_x", lambda: pd.DataFrame({"a": [1]}))
        assert result.ok and result.classification == "ok" and result.vendor == "hist"

        result = capability.probe_single("hist_y", lambda: (_ for _ in ()).throw(ValueError("boom")))
        assert not result.ok and result.classification == "unknown_error"

    def test_probe_cache_roundtrip(self, tmp_path, monkeypatch):
        from datetime import datetime

        config = {"data_cache_dir": str(tmp_path)}
        monkeypatch.chdir(tmp_path)
        summary = {"probed_at": datetime.now().isoformat(), "spot_snapshot_verified": True}
        capability.save_probe_cache(summary, config)
        loaded = capability.load_probe_cache(config, tushare_configured=False)
        assert loaded is not None
        assert loaded["spot_snapshot_verified"] is True
        assert loaded["tushare_configured"] is False  # default filled

    def test_probe_cache_ttl_expiry(self, tmp_path, monkeypatch):
        from datetime import datetime as dt

        config = {"data_cache_dir": str(tmp_path), "a0_probe": {"cache_ttl_minutes": 60}}
        monkeypatch.chdir(tmp_path)
        old = (dt.now() - __import__("datetime").timedelta(hours=2)).isoformat()
        capability.save_probe_cache({"probed_at": old}, config)
        assert capability.load_probe_cache(config, False) is None


class TestFacadeShape:
    """The slim facade must expose the full pre-split public surface."""

    def test_public_api_surface_stable(self):
        from tradingagents.screener.data_access import ScreenerDataAccess

        required = [
            "fetch_hist", "fetch_tencent_hist", "fetch_yfinance_hist",
            "fetch_spot_snapshot", "fetch_concept_boards", "fetch_concept_constituents",
            "fetch_industry_boards", "fetch_fund_flow", "fetch_index_spot",
            "fetch_index_constituents", "fetch_tick_data", "fetch_policy_news_baidu",
            "fetch_lhb_sina", "fetch_lhb_stats_sina", "fetch_lhb_institutional_stats_sina",
            "fetch_valuation_baidu", "fetch_vote_baidu",
            "get_interface_capability_summary", "validate_interface_assumptions",
        ]
        for name in required:
            assert callable(getattr(ScreenerDataAccess, name, None)), f"missing public method: {name}"

    def test_offline_capability_summary(self):
        from tradingagents.screener.data_access import ScreenerDataAccess

        access = ScreenerDataAccess(config={"a0_probe": {"enable_live_probes": False}})
        summary = access.get_interface_capability_summary()
        assert summary["hist_primary_vendor"] == "tencent_direct"
        assert "vendor_baseline" in summary
        assert "strategy_capabilities" in summary

    def test_satisfies_market_data_port_protocol(self):
        from tradingagents.ports.market_data import MarketDataPort
        from tradingagents.screener.data_access import ScreenerDataAccess

        assert isinstance(ScreenerDataAccess(), MarketDataPort)
