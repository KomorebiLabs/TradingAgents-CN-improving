"""Offline tests for stock-news snapshot caching."""

from __future__ import annotations

import pandas as pd

from tradingagents.dataflows.akshare import news


def test_stock_news_reuses_recent_vendor_snapshot(monkeypatch):
    calls = []
    frame = pd.DataFrame(
        [
            {
                "发布时间": "2026-08-15 10:11:51",
                "新闻标题": "贵州茅台发布中报",
                "文章来源": "测试来源",
                "关键词": "600519",
                "新闻内容": "测试新闻内容",
                "新闻链接": "https://example.test/news",
            }
        ]
    )

    class FakeAkshare:
        def stock_news_em(self, symbol):
            calls.append(symbol)
            return frame

    monkeypatch.setattr(news, "_require_akshare", lambda: FakeAkshare())
    monkeypatch.setattr(news, "_throttle_eastmoney", type("Throttle", (), {"wait": lambda self: None})())
    news._STOCK_NEWS_CACHE.clear()

    first = news.get_akshare_news("600519", "2026-08-13", "2026-08-20")
    second = news.get_akshare_news("600519.SH", "2026-07-01", "2026-08-20")

    assert "贵州茅台" in first
    assert "贵州茅台" in second
    assert calls == ["600519"]


def test_stock_news_accepts_tool_keyword_ticker(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "发布时间": "2026-08-15 10:11:51",
                "新闻标题": "贵州茅台发布中报",
                "文章来源": "测试来源",
                "关键词": "600519",
                "新闻内容": "测试新闻内容",
                "新闻链接": "https://example.test/news",
            }
        ]
    )

    class FakeAkshare:
        def stock_news_em(self, symbol):
            return frame

    monkeypatch.setattr(news, "_require_akshare", lambda: FakeAkshare())
    monkeypatch.setattr(news, "_throttle_eastmoney", type("Throttle", (), {"wait": lambda self: None})())
    news._STOCK_NEWS_CACHE.clear()

    result = news.get_akshare_news(
        ticker="600519", start_date="2026-08-13", end_date="2026-08-20"
    )

    assert "贵州茅台" in result
