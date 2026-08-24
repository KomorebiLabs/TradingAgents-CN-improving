"""Offline regression tests for upstream provider API/response drift."""

from __future__ import annotations

from contextlib import nullcontext
import sys
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest

from tradingagents.screener.data_access import ScreenerDataAccess
from tradingagents.screener.vendors import backup, misc, sina


@pytest.fixture(autouse=True)
def _minimal_akshare_module(monkeypatch):
    """Keep optional-provider tests runnable when CI omits AkShare."""
    module = ModuleType("akshare")
    for name in (
        "stock_individual_fund_flow_rank",
        "stock_board_concept_name_em",
        "stock_lhb_detail_em",
        "stock_lhb_stock_statistic_em",
        "stock_lhb_jgstatistic_em",
        "stock_zh_vote_baidu",
    ):
        setattr(module, name, None)
    monkeypatch.setitem(sys.modules, "akshare", module)


class _HttpStub:
    def sleep_for_vendor(self, _vendor):
        return None

    def spoof(self):
        return nullcontext()


def test_baostock_receives_hyphenated_dates(monkeypatch):
    captured = {}
    result = SimpleNamespace(
        error_code="0",
        get_data=lambda: pd.DataFrame(
            [["2025-01-02", "1", "2", "0.5", "1.5", "100"]]
        ),
    )
    fake_bs = SimpleNamespace(
        login=lambda: SimpleNamespace(error_code="0"),
        logout=lambda: None,
        query_history_k_data_plus=lambda *args, **kwargs: (
            captured.update(kwargs) or result
        ),
    )
    monkeypatch.setitem(__import__("sys").modules, "baostock", fake_bs)

    frame = backup.fetch_hist_baostock(
        _HttpStub(), "000001", "20250101", "20250110"
    )

    assert frame is not None
    assert captured["start_date"] == "2025-01-01"
    assert captured["end_date"] == "2025-01-10"


def test_yfinance_receives_hyphenated_dates(monkeypatch):
    captured = {}

    class _Ticker:
        def __init__(self, symbol):
            captured["symbol"] = symbol

        def history(self, **kwargs):
            captured.update(kwargs)
            return pd.DataFrame({"Close": [10.0]})

    monkeypatch.setattr("yfinance.Ticker", _Ticker)
    requester = SimpleNamespace(request=lambda fn, **kwargs: fn(**kwargs))

    frame = backup.fetch_hist_yfinance(
        _HttpStub(), requester, "000001", "20250101", "20250110"
    )

    assert frame is not None
    assert captured["start"] == "2025-01-01"
    assert captured["end"] == "2025-01-10"


def test_eastmoney_fund_flow_uses_current_akshare_rank_api(monkeypatch):
    expected = pd.DataFrame({"代码": ["000001"]})
    captured = {}

    def current_api(*, indicator):
        captured["indicator"] = indicator
        return expected

    monkeypatch.setattr("akshare.stock_individual_fund_flow_rank", current_api)

    result = misc.fetch_fund_flow_em(_HttpStub())

    assert result is expected
    assert captured["indicator"] == "今日"


def test_eastmoney_concept_is_an_independent_fallback(monkeypatch):
    expected = pd.DataFrame({"板块名称": ["人工智能"]})
    monkeypatch.setattr("akshare.stock_board_concept_name_em", lambda: expected)

    result = misc.fetch_concept_em(_HttpStub())

    assert result is not expected
    assert result.iloc[0]["板块名称"] == "人工智能"
    assert result.iloc[0]["source"] == "eastmoney"


def test_lhb_eastmoney_fallbacks_use_compatible_windows(monkeypatch):
    detail = pd.DataFrame({"代码": ["000001"]})
    stats = pd.DataFrame({"代码": ["000001"], "上榜次数": [2]})
    inst = pd.DataFrame({"代码": ["000001"], "买入次数": [1]})
    captured = {}
    monkeypatch.setattr(
        "akshare.stock_lhb_detail_em",
        lambda **kwargs: captured.update(detail=kwargs) or detail,
    )
    monkeypatch.setattr(
        "akshare.stock_lhb_stock_statistic_em",
        lambda **kwargs: captured.update(stats=kwargs) or stats,
    )
    monkeypatch.setattr(
        "akshare.stock_lhb_jgstatistic_em",
        lambda **kwargs: captured.update(inst=kwargs) or inst,
    )

    assert misc.fetch_lhb_detail_em(_HttpStub(), "2026-08-21") is detail
    assert misc.fetch_lhb_stats_em(_HttpStub(), "5") is stats
    assert misc.fetch_lhb_institutional_em(_HttpStub(), "5") is inst
    assert captured["detail"] == {"start_date": "20260821", "end_date": "20260821"}
    assert captured["stats"] == {"symbol": "近一月"}
    assert captured["inst"] == {"symbol": "近一月"}


def test_baidu_vote_requests_stock_schema_and_facade_falls_back(monkeypatch):
    expected = pd.DataFrame({"周期": ["day"], "看涨比例": [60]})
    captured = {}

    def vote_api(**kwargs):
        captured.update(kwargs)
        raise KeyError("voteRecords")

    monkeypatch.setattr("akshare.stock_zh_vote_baidu", vote_api)
    assert misc.fetch_vote_baidu("600519") is None
    assert captured == {"symbol": "600519", "indicator": "股票"}

    access = ScreenerDataAccess(config={"a0_probe": {"enable_live_probes": False}})
    monkeypatch.setattr(misc, "fetch_vote_baidu", lambda **kwargs: None)
    monkeypatch.setattr(misc, "fetch_popularity_em", lambda symbol: expected)
    assert access.fetch_vote_baidu("600519") is expected


def test_popularity_fallback_uses_available_fund_flow_proxy(monkeypatch):
    frame = pd.DataFrame(
        {"股票代码": ["000001", "600519"], "今日主力净流入-净额": [1.0, 2.0]}
    )
    captured = {}
    monkeypatch.setattr(
        "akshare.stock_individual_fund_flow_rank",
        lambda **kwargs: captured.update(kwargs) or frame,
    )

    result = misc.fetch_popularity_em("600519")

    assert captured == {"indicator": "今日"}
    assert result["股票代码"].tolist() == ["600519"]
    assert result.iloc[0]["source"] == "eastmoney_fund_flow_proxy"


def test_popularity_fallback_never_returns_another_stock(monkeypatch):
    frame = pd.DataFrame({"股票代码": ["000001"], "净额": [1.0]})
    monkeypatch.setattr(
        "akshare.stock_individual_fund_flow_rank", lambda **_kwargs: frame
    )

    assert misc.fetch_popularity_em("600519") is None


def test_facade_uses_em_when_sina_concept_and_lhb_are_unavailable(monkeypatch):
    concept = pd.DataFrame({"板块名称": ["机器人"]})
    detail = pd.DataFrame({"代码": ["000001"]})
    stats = pd.DataFrame({"代码": ["000001"], "上榜次数": [2]})
    inst = pd.DataFrame({"代码": ["000001"], "买入次数": [1]})
    access = ScreenerDataAccess(config={"a0_probe": {"enable_live_probes": False}})

    monkeypatch.setattr("tradingagents.screener.vendors.ths.fetch_concept_boards", lambda _http: None)
    monkeypatch.setattr(sina, "fetch_concept", lambda _http: None)
    monkeypatch.setattr(misc, "fetch_concept_em", lambda _http: concept)
    monkeypatch.setattr(sina, "fetch_lhb_detail", lambda *_args: None)
    monkeypatch.setattr(sina, "fetch_lhb_ggtj", lambda *_args: None)
    monkeypatch.setattr(sina, "fetch_lhb_jgzz", lambda *_args: None)
    monkeypatch.setattr(misc, "fetch_lhb_detail_em", lambda *_args: detail)
    monkeypatch.setattr(misc, "fetch_lhb_stats_em", lambda *_args: stats)
    monkeypatch.setattr(misc, "fetch_lhb_institutional_em", lambda *_args: inst)

    assert access.fetch_concept_boards() is concept
    assert access.fetch_lhb_sina("2026-08-21") is detail
    assert access.fetch_lhb_stats_sina("5") is stats
    assert access.fetch_lhb_institutional_stats_sina("5") is inst


def test_baidu_popularity_uses_ths_flow_as_last_resort(monkeypatch):
    flow = pd.DataFrame(
        {"股票代码": ["000001", "600519"], "今日主力净流入-净额": [1.0, 2.0]}
    )
    access = ScreenerDataAccess(config={"a0_probe": {"enable_live_probes": False}})
    monkeypatch.setattr(misc, "fetch_vote_baidu", lambda **kwargs: None)
    monkeypatch.setattr(misc, "fetch_popularity_em", lambda symbol: None)
    monkeypatch.setattr(access, "fetch_fund_flow", lambda: flow)

    result = access.fetch_vote_baidu("600519")

    assert result["股票代码"].tolist() == ["600519"]
    assert result.iloc[0]["source"] == "ths_or_em_fund_flow_proxy"
