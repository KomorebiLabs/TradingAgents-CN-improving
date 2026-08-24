"""Cached A-share trading calendar with an explicit weekday fallback."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable


class AShareTradingCalendar:
    def __init__(
        self,
        cache_path: Path | None = None,
        fetcher: Callable[[], Iterable[object]] | None = None,
    ) -> None:
        self.cache_path = cache_path or Path.home() / ".tradingagents" / "calendar" / "a_share_sessions.json"
        self.fetcher = fetcher or self._fetch_from_akshare
        self.source = "uninitialized"
        self.degraded = False
        self.as_of: str | None = None
        self._sessions: set[date] | None = None

    @staticmethod
    def _fetch_from_akshare() -> Iterable[object]:
        import akshare as ak

        frame = ak.tool_trade_date_hist_sina()
        return frame["trade_date"].tolist()

    @staticmethod
    def _to_date(value: object) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()

    def _load(self) -> set[date]:
        if self._sessions is not None:
            return self._sessions
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            sessions = {self._to_date(item) for item in payload["sessions"]}
            self.source = "cache"
            self.as_of = payload.get("as_of")
        except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
            try:
                sessions = {self._to_date(item) for item in self.fetcher()}
                self.as_of = datetime.now().isoformat(timespec="seconds")
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.cache_path.write_text(
                    json.dumps(
                        {"as_of": self.as_of, "sessions": sorted(item.isoformat() for item in sessions)},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                self.source = "akshare_sina_trade_calendar"
            except Exception:
                sessions = set()
                self.source = "weekday_fallback"
                self.degraded = True
        self._sessions = sessions
        return sessions

    def is_trading_day(self, day: date) -> bool:
        sessions = self._load()
        return day in sessions if sessions else day.weekday() < 5

    def latest_trading_day(self, reference: date | None = None) -> date:
        candidate = reference or date.today()
        for _ in range(370):
            if self.is_trading_day(candidate):
                return candidate
            candidate -= timedelta(days=1)
        raise RuntimeError("无法在一年范围内解析最近 A 股交易日")


_DEFAULT_CALENDAR = AShareTradingCalendar()


def is_a_share_trading_day(day: date) -> bool:
    return _DEFAULT_CALENDAR.is_trading_day(day)


def latest_a_share_trading_day(reference: date | None = None) -> date:
    return _DEFAULT_CALENDAR.latest_trading_day(reference)
