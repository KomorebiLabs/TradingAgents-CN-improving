"""Contract tests for official announcements and independent financial data."""

from __future__ import annotations

from types import SimpleNamespace

from tradingagents.dataflows import cninfo_announcements, tushare_financials


def test_cninfo_announcements_normalize_official_records(monkeypatch):
    payload = {
        "announcements": [
            {
                "secCode": "600519",
                "secName": "贵州茅台",
                "announcementTitle": "贵州茅台2025年年度报告",
                "announcementTime": 1775433600000,
                "adjunctUrl": "finalpage/2026-04-06/1234567890.PDF",
            }
        ]
    }

    def fake_post(*args, **kwargs):
        return SimpleNamespace(
            status_code=200,
            json=lambda: payload,
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(cninfo_announcements.requests, "post", fake_post)

    result = cninfo_announcements.get_cninfo_announcements(
        "600519", "2026-04-01", "2026-04-10"
    )

    assert "Vendor: cninfo.official" in result
    assert "贵州茅台2025年年度报告" in result
    assert "https://static.cninfo.com.cn/finalpage/2026-04-06/1234567890.PDF" in result
    assert "Source date: 2026-04-06" in result


def test_tushare_financials_render_period_and_units(monkeypatch):
    payload = {
        "code": 0,
        "msg": "",
        "data": {
            "fields": ["ts_code", "ann_date", "end_date", "revenue", "n_income"],
            "items": [["600519.SH", "20260406", "20251231", 172054171890.91, 82320067101.68]],
        },
    }

    def fake_post(*args, **kwargs):
        return SimpleNamespace(
            status_code=200,
            json=lambda: payload,
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(tushare_financials.requests, "post", fake_post)
    monkeypatch.setenv("TUSHARE_TOKEN", "test-token")

    result = tushare_financials.get_tushare_financial_statement(
        "600519.SH", "income", "annual", "2026-08-20"
    )

    assert "Vendor: tushare.pro" in result
    assert "Revenue (2025-12-31): 172054171890.91 元" in result
    assert "Net Income (2025-12-31): 82320067101.68 元" in result
    assert "Published date: 2026-04-06" in result


def test_tushare_permission_failure_is_explicit(monkeypatch):
    payload = {"code": 2002, "msg": "no permission"}

    monkeypatch.setattr(
        tushare_financials.requests,
        "post",
        lambda *args, **kwargs: SimpleNamespace(
            status_code=200,
            json=lambda: payload,
            raise_for_status=lambda: None,
        ),
    )
    monkeypatch.setenv("TUSHARE_TOKEN", "test-token")

    result = tushare_financials.get_tushare_financial_statement(
        "600519.SH", "income", "annual", "2026-08-20"
    )

    assert "permission" in result.lower()
    assert "test-token" not in result
