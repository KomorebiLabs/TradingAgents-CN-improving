"""Offline point-in-time safeguards for historical tool inputs."""

from __future__ import annotations

import pandas as pd

from tradingagents.dataflows import cn_indicators
from tradingagents.dataflows.akshare.news import (
    _prepare_cn_stock_news,
    _prepare_sector_news,
)


class _HistoryPortStub:
    def __init__(self, frame: pd.DataFrame):
        self.frame = frame
        self.calls: list[dict[str, str]] = []

    def fetch_hist(self, *, ticker, start_date, end_date, adjust):
        self.calls.append(
            {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
                "adjust": adjust,
            }
        )
        return self.frame.copy()


def _history_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2026-08-18", "2026-08-21"],
            "open": [10.0, 11.0],
            "high": [10.5, 11.5],
            "low": [9.5, 10.5],
            "close": [10.2, 11.2],
            "volume": [1000, 1200],
        }
    )


def _news_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "发布时间": ["2026-08-19 09:00:00", "2026-08-21 09:00:00"],
            "新闻标题": ["inside cutoff", "future article"],
            "文章来源": ["fixture", "fixture"],
            "关键词": ["test", "test"],
            "新闻内容": ["valid", "future"],
            "新闻链接": ["https://example.invalid/valid", "https://example.invalid/future"],
        }
    )


def test_cn_history_passes_cutoff_and_drops_future_vendor_rows(monkeypatch):
    stub = _HistoryPortStub(_history_frame())
    monkeypatch.setattr(cn_indicators, "get_market_data_port", lambda: stub)

    result = cn_indicators._get_cn_hist_data("sh600519", "20260820", look_back_days=30)

    assert stub.calls == [
        {
            "ticker": "sh600519",
            "start_date": "2026-06-21",
            "end_date": "2026-08-20",
            "adjust": "qfq",
        }
    ]
    assert result is not None
    assert result["Date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-08-18"]


def test_stock_news_output_excludes_articles_after_end_date():
    prepared = _prepare_cn_stock_news(
        _news_frame(),
        start_date="2026-08-18",
        end_date="2026-08-20",
    )

    assert prepared["新闻标题"].tolist() == ["inside cutoff"]


def test_sector_news_output_excludes_articles_after_end_date():
    prepared = _prepare_sector_news(
        _news_frame(),
        keywords=["inside", "future"],
        start_date="2026-08-18",
        end_date="2026-08-20",
    )

    assert prepared["新闻标题"].tolist() == ["inside cutoff"]
