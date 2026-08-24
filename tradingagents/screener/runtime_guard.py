from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, List, Tuple

from tradingagents.screener.models import ScreeningResult


@dataclass
class RuntimeTimeConfig:
    earliest_run_time: str = "16:30"
    latest_next_day: str = "09:00"
    allow_weekend: bool = False
    allow_non_trading_day_override: bool = False
    allow_experimental_intraday: bool = True
    max_data_age_days: int = 2


class TimeValidator:
    def __init__(
        self,
        config: RuntimeTimeConfig | None = None,
        trading_day_checker: Callable[[object], bool] | None = None,
    ):
        self.config = config or RuntimeTimeConfig()
        if trading_day_checker is None:
            from tradingagents.screener.trading_calendar import is_a_share_trading_day

            trading_day_checker = is_a_share_trading_day
        self.trading_day_checker = trading_day_checker

    def validate(
        self,
        mode: str = "MVP",
        trade_date: str | None = None,
        now: datetime | None = None,
    ) -> Tuple[bool, List[str]]:
        now = now or datetime.now()
        warnings: List[str] = []

        # Allow past trade dates to bypass intraday and weekend checks -- we already have closed data
        is_past = False
        if trade_date:
            try:
                trade_dt = datetime.strptime(trade_date, "%Y-%m-%d")
                is_past = trade_dt.date() < now.date()
                if (
                    not self.trading_day_checker(trade_dt.date())
                    and not self.config.allow_non_trading_day_override
                ):
                    return False, [f"[FATAL] {trade_date} 是 A 股非交易日"]
            except ValueError:
                pass

        if is_past:
            warnings.append(f"[WARN] trade_date {trade_date} is in the past; bypassing intraday and weekend time checks")

        if now.weekday() >= 5 and not is_past:
            if not self.config.allow_weekend and not self.config.allow_non_trading_day_override:
                return False, ["[FATAL] 当前是周末，默认不允许运行 Screener"]
            warnings.append("[WARN] 当前是周末，处于 override 模式")

        time_str = now.strftime("%H:%M")
        time_only = time_str  # e.g. "14:30"

        if not is_past and "09:30" <= time_only < "15:00":
            if mode != "EXPERIMENTAL":
                return False, ["[FATAL] 当前处于盘中，生产模式默认拒绝运行"]
            if mode == "EXPERIMENTAL" and self.config.allow_experimental_intraday:
                warnings.append("[WARN] 当前处于盘中，实验模式允许运行，但数据可能不完整")

        if not is_past and "15:00" <= time_str < self.config.earliest_run_time and mode != "EXPERIMENTAL":
            return False, [f"[FATAL] 当前时间 {time_str} 处于收盘后未稳定窗口，默认拒绝运行"]

        if is_past and "15:00" <= time_str < self.config.earliest_run_time:
            warnings.append(f"[WARN] trade_date {trade_date} is past; bypassing unstable post-close window check")

        if trade_date:
            try:
                trade_dt = datetime.strptime(trade_date, "%Y-%m-%d")
                age_days = (now.date() - trade_dt.date()).days
                if age_days > self.config.max_data_age_days:
                    warnings.append(
                        f"[WARN] 数据日期 {trade_date} 距离当前超过 {self.config.max_data_age_days} 天"
                    )
            except ValueError:
                warnings.append(f"[WARN] trade_date 无法解析: {trade_date}")

        return True, warnings


def validate_screener_run(
    mode: str = "MVP",
    trade_date: str | None = None,
    config: RuntimeTimeConfig | None = None,
) -> Tuple[bool, List[str]]:
    return TimeValidator(config=config).validate(mode=mode, trade_date=trade_date)


def check_data_consistency(screening_result: ScreeningResult) -> List[str]:
    issues: List[str] = []

    if not screening_result.candidates:
        issues.append("[FATAL] 没有候选股票，策略可能全部失效")

    try:
        trade_dt = datetime.strptime(screening_result.trade_date, "%Y-%m-%d")
        if trade_dt.date() < datetime.now().date() - timedelta(days=2):
            issues.append(f"[WARN] 数据日期 {screening_result.trade_date} 可能过期")
    except ValueError:
        issues.append(f"[WARN] 无法解析 trade_date: {screening_result.trade_date}")

    for candidate in screening_result.candidates[:3]:
        if not candidate.data_source_verified:
            issues.append(f"[WARN] {candidate.ticker} 的数据源未经完整验证")

    return issues
