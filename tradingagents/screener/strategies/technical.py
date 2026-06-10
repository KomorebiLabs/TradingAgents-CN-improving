from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import pandas as pd

from tradingagents.screener.models import SignalCard, SignalEvidence
from tradingagents.screener.universe import format_ticker
from tradingagents.ui.screener_console import (
    console,
    print_progress_bar,
    clear_progress_line,
)

_logger = logging.getLogger(__name__)


@dataclass
class StrategyOutcome:
    cards: List[SignalCard]
    status: str
    warnings: List[str]


def score_to_exchange(raw_code: str) -> str:
    if raw_code.startswith(("6", "9")):
        return "SH"
    if raw_code.startswith(("0", "2", "3")):
        return "SZ"
    if raw_code.startswith(("4", "8")):
        return "BJ"
    return ""


def placeholder_name(raw_code: str) -> str:
    return {
        "000300": "CSI 300 Index Proxy",
        "000905": "CSI 500 Index Proxy",
        "399006": "ChiNext Index Proxy",
        "000688": "STAR 50 Proxy",
    }.get(raw_code, f"Proxy {raw_code}")


def _technical_concept_tags(fallback_vendor: str, degraded: bool) -> List[str]:
    tags = ["technical_trend"]
    if fallback_vendor == "tencent":
        tags.append("tencent_hist_fallback")
    elif fallback_vendor == "yfinance":
        tags.append("yfinance_hist_fallback")
    if degraded:
        tags.append("technical_degraded")
    return tags


def _technical_trigger_reason(metrics: Dict[str, float], fallback_vendor: str, degraded: bool) -> str:
    if degraded and fallback_vendor not in {"tencent", "yfinance"}:
        return "technical_momentum_degraded"
    if metrics.get("trend_grade", "") == "recovery":
        return "technical_recovery_structure"
    if metrics.get("structure_risk_score", 100.0) <= 40:
        return "technical_trend_extended_risk"
    if metrics.get("trend_alignment_score", 0.0) >= 80 and metrics.get("momentum_score", 0.0) >= 70:
        return "technical_trend_breakout"
    if fallback_vendor == "tencent":
        return "technical_momentum_tencent_fallback"
    if fallback_vendor == "yfinance":
        return "technical_momentum_yfinance_fallback"
    return "technical_trend_follow"


class TechnicalStrategy:
    def __init__(self, data_access, config: Dict[str, Any] | None = None):
        self.data_access = data_access
        self.config = config or {}

    def run(self, universe: List[str], trade_date: str) -> StrategyOutcome:
        console.print(f"[cyan]>> TechnicalStrategy[/cyan]  [dim]{len(universe)} stocks...", end="\r")

        capability = self.data_access.validate_interface_assumptions(trade_date=trade_date)
        strategy_config = self.config.get("strategies", {}).get("technical", {})
        th = strategy_config.get("thresholds", {})
        signal_consistency_low = float(th.get("signal_consistency_low", 45.0))
        hist_rows_minimum = int(th.get("hist_rows_minimum", 30))
        fund_flow_bonus = float(th.get("fund_flow_bonus", 3.0))
        hist_rows_penalty = float(th.get("hist_rows_penalty", 10.0))
        score_ceiling = float(th.get("score_ceiling", 95.0))
        score_floor = float(th.get("score_floor", 20.0))
        weights = {
            "trend_alignment": float(th.get("trend_alignment_weight", 0.22)),
            "momentum": float(th.get("momentum_weight", 0.18)),
            "drawdown_resilience": float(th.get("drawdown_resilience_weight", 0.14)),
            "volatility": float(th.get("volatility_weight", 0.10)),
            "trend_consistency": float(th.get("trend_consistency_weight", 0.12)),
            "structure_risk": float(th.get("structure_risk_weight", 0.11)),
            "volume_confirmation": float(th.get("volume_confirmation_weight", 0.07)),
            "breakout_quality": float(th.get("breakout_quality_weight", 0.04)),
            "divergence": float(th.get("divergence_weight", 0.02)),
        }
        allow_yfinance_fallback = bool(strategy_config.get("allow_yfinance_fallback", True))

        # A2: build full threshold_snapshot from config for output audit
        threshold_snapshot = {k: v for k, v in th.items()}
        threshold_snapshot["source"] = "technical"
        threshold_snapshot["effective_values"] = {
            "signal_consistency_low": signal_consistency_low,
            "hist_rows_minimum": hist_rows_minimum,
            "fund_flow_bonus": fund_flow_bonus,
            "hist_rows_penalty": hist_rows_penalty,
            "score_ceiling": score_ceiling,
            "score_floor": score_floor,
            "weights": weights,
            "allow_yfinance_fallback": allow_yfinance_fallback,
        }
        cards: List[SignalCard] = []
        fund_flow_verified = bool(capability.get("fund_flow_bulk_verified", False))
        hist_verified = bool(capability.get("hist_fetch_verified", False))
        tencent_hist_verified = bool(capability.get("tencent_hist_verified", False))
        yfinance_hist_verified = bool(capability.get("yfinance_hist_verified", False))
        effective_hist_available = hist_verified or tencent_hist_verified or (
            allow_yfinance_fallback and yfinance_hist_verified
        )
        histories, history_vendors = self._load_histories(
            universe=universe,
            trade_date=trade_date,
            capability=capability,
            tencent_hist_verified=tencent_hist_verified,
            allow_yfinance_fallback=allow_yfinance_fallback,
            hist_verified=hist_verified,
        )

        console.print(f"[cyan]  Loading histories[/cyan]  [dim]{len(universe)} stocks...[/dim]", end="\r")

        for i, raw_code in enumerate(universe):
            ticker = format_ticker(raw_code)
            hist = histories.get(ticker)
            hist_vendor = history_vendors.get(ticker, "")
            metrics = self._compute_hist_metrics(hist)
            signal_consistency_index = self._compute_signal_consistency_index(metrics)
            score = self._build_total_score(
                metrics,
                fund_flow_verified,
                weights=weights,
                fund_flow_bonus=fund_flow_bonus,
                hist_rows_penalty=hist_rows_penalty,
                hist_rows_minimum=hist_rows_minimum,
                score_ceiling=score_ceiling,
                score_floor=score_floor,
            )
            degraded = not (fund_flow_verified and effective_hist_available and metrics.get("hist_rows", 0) >= hist_rows_minimum)
            evidence = SignalEvidence(
                strategy="technical",
                score=score,
                rank_in_strategy=i + 1,
                reason="Historical trend/momentum scoring from Tencent-first daily bars",
                raw_metrics={
                    "score_family": "technical_hist_trend_v1",
                    "lookback_days": self.config.get("strategies", {})
                    .get("technical", {})
                    .get("lookback_days", 100),
                    "trend_alignment_score": metrics["trend_alignment_score"],
                    "momentum_score": metrics["momentum_score"],
                    "drawdown_resilience_score": metrics["drawdown_resilience_score"],
                    "volatility_score": metrics["volatility_score"],
                    "trend_consistency_score": metrics["trend_consistency_score"],
                    "structure_risk_score": metrics["structure_risk_score"],
                    "avg_volume_20d": metrics["avg_volume_20d"],
                    "latest_volume": metrics["latest_volume"],
                    "volume_spike_ratio": metrics["volume_spike_ratio"],
                    "volume_confirmation_score": metrics["volume_confirmation_score"],
                    "breakout_quality_score": metrics["breakout_quality_score"],
                    "volume_price_divergence_score": metrics["volume_price_divergence_score"],
                    "signal_consistency_index": signal_consistency_index,
                    "close_above_ma20": metrics["close_above_ma20"],
                    "close_above_ma60": metrics["close_above_ma60"],
                    "close": metrics["close"],
                    "ma20": metrics["ma20"],
                    "ma60": metrics["ma60"],
                    "ma_spread_pct": metrics["ma_spread_pct"],
                    "recent_extension_pct": metrics["recent_extension_pct"],
                    "positive_days_ratio_pct": metrics["positive_days_ratio_pct"],
                    "return_20d_pct": metrics["return_20d_pct"],
                    "return_60d_pct": metrics["return_60d_pct"],
                    "max_drawdown_pct": metrics["max_drawdown_pct"],
                    "annualized_volatility_pct": metrics["annualized_volatility_pct"],
                    "trend_failure_streak": metrics["trend_failure_streak"],
                    "support_loss_count": metrics["support_loss_count"],
                    "trend_grade": metrics["trend_grade"],
                    "structure_risk_band": metrics["structure_risk_band"],
                    "production_rule_version": "technical_pg_v3",
                    # A2: store the full config-driven threshold_snapshot, not just signal_consistency_low
                    "threshold_snapshot": threshold_snapshot,
                    "hist_rows": metrics["hist_rows"],
                    "fallback_vendor": hist_vendor or capability.get("hist_fetch_fallback_vendor", ""),
                    "hist_fetch_secondary_vendor": capability.get("hist_fetch_secondary_vendor", ""),
                    "tencent_hist_verified": tencent_hist_verified,
                    "yfinance_hist_verified": yfinance_hist_verified,
                    "fund_flow_verified": fund_flow_verified,
                    "effective_hist_available": effective_hist_available,
                    "degraded_context": {
                        "fund_flow_verified": fund_flow_verified,
                        "effective_hist_available": effective_hist_available,
                        "hist_rows": metrics["hist_rows"],
                        "used_vendor": hist_vendor or capability.get("hist_fetch_fallback_vendor", ""),
                    },
                    "vendor_trace": {
                        "hist_primary_vendor": capability.get("hist_primary_vendor", "tencent"),
                        "hist_secondary_vendor": capability.get("hist_fetch_secondary_vendor", ""),
                        "hist_fallback_vendor": hist_vendor or capability.get("hist_fetch_fallback_vendor", ""),
                        "fund_flow_primary_vendor": capability.get("fund_flow_primary_vendor", "ths"),
                    },
                },
                freshness=capability.get("freshness", []),
                degraded=degraded,
                degradation_reason=self._build_degradation_reason(
                    capability,
                    allow_yfinance_fallback=allow_yfinance_fallback,
                    hist_rows=metrics["hist_rows"],
                    hist_rows_minimum=hist_rows_minimum,
                ),
            )
            cards.append(
                SignalCard(
                    ticker=ticker,
                    raw_code=raw_code,
                    exchange=score_to_exchange(raw_code),
                    company_name=placeholder_name(raw_code),
                    trade_date=trade_date,
                    sector_tags=["broad_market"],
                    concept_tags=_technical_concept_tags(hist_vendor, degraded),
                    strategy_sources=["technical"],
                    signal_breakdown=[evidence],
                    trigger_reason=_technical_trigger_reason(metrics, hist_vendor, degraded),
                    initial_confidence=min(95.0, score * 0.9 + (5.0 if not degraded else 0.0)),
                    risk_flags=self._build_risk_flags(
                        capability=capability,
                        effective_hist_available=effective_hist_available,
                        allow_yfinance_fallback=allow_yfinance_fallback,
                        used_yfinance_hist=hist_vendor == "yfinance",
                        used_tencent_hist=hist_vendor == "tencent",
                        hist_rows=metrics["hist_rows"],
                        hist_rows_minimum=hist_rows_minimum,
                        metrics=metrics,
                        signal_consistency_index=signal_consistency_index,
                        signal_consistency_low=signal_consistency_low,
                    ),
                    screening_score=score,
                    data_source_verified=bool(fund_flow_verified and effective_hist_available and metrics["hist_rows"] >= hist_rows_minimum),
                    evidence_snapshot={
                        "capability_summary": capability,
                        "strategy": "technical",
                        "hist_fallback_vendor": hist_vendor or "none",
                        "hist_preview": self._preview_hist(hist),
                        "score_components": metrics,
                        # A2: full threshold audit trail
                        "threshold_snapshot": threshold_snapshot,
                    },
                )
            )

            # Print progress every 50 stocks
            if (i + 1) % 50 == 0 or (i + 1) == len(universe):
                pct = (i + 1) * 100 // len(universe)
                print_progress_bar("Technical scoring", i + 1, len(universe))

        clear_progress_line()
        console.print(f"[cyan]  Technical:[/cyan] [dim]sorting {len(cards)} cards...[/dim]", end="\r")

        cards.sort(key=lambda card: card.screening_score, reverse=True)
        top_n = self.config.get("strategies", {}).get("technical", {}).get("top_output", 20)
        cards = cards[: min(len(cards), top_n)]
        for rank, card in enumerate(cards, 1):
            if card.signal_breakdown:
                card.signal_breakdown[0].rank_in_strategy = rank

        warnings = list(capability.get("warnings", []))
        status = "ready" if cards and fund_flow_verified and effective_hist_available else "degraded"
        console.print(f"[green][OK] TechnicalStrategy done[/green]  [cyan]{len(cards)}[/cyan] cards  [dim]status={status}[/dim]")
        return StrategyOutcome(cards=cards, status=status, warnings=warnings)

    @staticmethod
    def _compute_hist_metrics(hist: Any) -> Dict[str, Any]:
        empty = {
            "hist_rows": 0,
            "close": 0.0,
            "ma20": 0.0,
            "ma60": 0.0,
            "avg_volume_20d": 0.0,
            "latest_volume": 0.0,
            "volume_spike_ratio": 0.0,
            "close_above_ma20": False,
            "close_above_ma60": False,
            "return_20d_pct": 0.0,
            "return_60d_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "annualized_volatility_pct": 0.0,
            "trend_alignment_score": 0.0,
            "momentum_score": 0.0,
            "drawdown_resilience_score": 0.0,
            "volatility_score": 0.0,
            "trend_consistency_score": 0.0,
            "structure_risk_score": 0.0,
            "volume_confirmation_score": 0.0,
            "breakout_quality_score": 0.0,
            "volume_price_divergence_score": 0.0,
            "trend_failure_streak": 0,
            "support_loss_count": 0,
            "trend_grade": "flat",
            "structure_risk_band": "medium",
            "ma_spread_pct": 0.0,
            "recent_extension_pct": 0.0,
            "positive_days_ratio_pct": 0.0,
        }
        if hist is None or getattr(hist, "empty", True):
            return empty

        df = hist.copy()
        close_col = "close" if "close" in df.columns else "Close" if "Close" in df.columns else None
        volume_col = "volume" if "volume" in df.columns else "Volume" if "Volume" in df.columns else None
        if close_col is None:
            return empty

        series = pd.to_numeric(df[close_col], errors="coerce").dropna()
        if series.empty:
            return empty
        volume_series = None
        if volume_col is not None:
            volume_series = pd.to_numeric(df[volume_col], errors="coerce").dropna()

        rows = len(series)
        close = float(series.iloc[-1])
        ma20 = float(series.tail(min(20, rows)).mean())
        ma60 = float(series.tail(min(60, rows)).mean())
        close_above_ma20 = close >= ma20 if ma20 else False
        close_above_ma60 = close >= ma60 if ma60 else False

        if rows >= 21:
            return_20d = (close / float(series.iloc[-21]) - 1.0) * 100.0
        else:
            return_20d = 0.0
        if rows >= 61:
            return_60d = (close / float(series.iloc[-61]) - 1.0) * 100.0
        else:
            return_60d = return_20d

        rolling_max = series.cummax()
        drawdown = ((series / rolling_max) - 1.0) * 100.0
        max_drawdown_pct = abs(float(drawdown.min())) if not drawdown.empty else 0.0

        returns = series.pct_change().dropna()
        annualized_volatility_pct = float(returns.std() * (252**0.5) * 100.0) if not returns.empty else 0.0
        positive_days_ratio = float((returns > 0).mean()) if not returns.empty else 0.0
        ma_spread_pct = ((ma20 / ma60) - 1.0) * 100.0 if ma60 else 0.0
        recent_extension_pct = ((close / ma20) - 1.0) * 100.0 if ma20 else 0.0
        trend_failure_streak = TechnicalStrategy._count_recent_trend_failures(series)
        support_loss_count = int((series.tail(min(20, rows)) < ma20).sum()) if ma20 else 0
        avg_volume_20d = (
            float(volume_series.tail(min(20, len(volume_series))).mean())
            if volume_series is not None and not volume_series.empty
            else 0.0
        )
        latest_volume = float(volume_series.iloc[-1]) if volume_series is not None and not volume_series.empty else 0.0
        volume_spike_ratio = (latest_volume / avg_volume_20d) if avg_volume_20d > 0 else 0.0

        trend_alignment_score = 40.0
        if close_above_ma20:
            trend_alignment_score += 25.0
        if close_above_ma60:
            trend_alignment_score += 20.0
        if ma20 >= ma60 > 0:
            trend_alignment_score += 15.0

        momentum_score = min(100.0, max(20.0, 50.0 + return_20d * 1.2 + return_60d * 0.5))
        drawdown_resilience_score = min(100.0, max(20.0, 100.0 - max_drawdown_pct * 2.2))
        volatility_score = min(100.0, max(20.0, 100.0 - annualized_volatility_pct * 1.1))
        trend_consistency_score = min(
            100.0,
            max(
                20.0,
                38.0 + positive_days_ratio * 45.0 + max(0.0, ma_spread_pct) * 1.1 - max_drawdown_pct * 0.6,
            ),
        )
        structure_risk_score = 68.0
        volume_confirmation_score = 42.0
        if volume_spike_ratio >= 1.6 and return_20d > 0:
            volume_confirmation_score += 30.0
        elif volume_spike_ratio >= 1.15 and return_20d > 0:
            volume_confirmation_score += 18.0
        elif volume_spike_ratio <= 0.75 and return_20d > 8:
            volume_confirmation_score -= 10.0
        if close_above_ma20 and close_above_ma60:
            volume_confirmation_score += 8.0

        breakout_quality_score = 38.0
        if close_above_ma20 and close_above_ma60 and return_20d > 0:
            breakout_quality_score += 16.0
        if ma_spread_pct > 0:
            breakout_quality_score += min(18.0, ma_spread_pct * 2.2)
        if recent_extension_pct > 2.0:
            breakout_quality_score += min(14.0, (recent_extension_pct - 2.0) * 2.0)
        if volume_spike_ratio > 1.0:
            breakout_quality_score += min(10.0, (volume_spike_ratio - 1.0) * 12.0)

        volume_price_divergence_score = 62.0
        if return_20d > 12 and volume_spike_ratio < 0.85:
            volume_price_divergence_score -= 18.0
        if recent_extension_pct > 8 and volume_spike_ratio >= 1.8:
            volume_price_divergence_score -= 12.0
        if trend_failure_streak >= 3 and volume_spike_ratio > 1.5:
            volume_price_divergence_score -= 10.0
        if recent_extension_pct > 4:
            structure_risk_score -= min(16.0, (recent_extension_pct - 4.0) * 1.8)
        if not close_above_ma20:
            structure_risk_score -= 10.0
        if not close_above_ma60:
            structure_risk_score -= 8.0
        if ma20 < ma60:
            structure_risk_score -= 12.0
        if trend_failure_streak >= 3:
            structure_risk_score -= 8.0
        if support_loss_count >= 8:
            structure_risk_score -= 7.0
        if max_drawdown_pct >= 18:
            structure_risk_score -= 8.0
        if annualized_volatility_pct >= 45:
            structure_risk_score -= 8.0
        if volume_spike_ratio >= 1.8 and recent_extension_pct >= 8:
            structure_risk_score -= 8.0
        if return_20d > 10 and volume_spike_ratio < 0.8:
            structure_risk_score -= 6.0

        if structure_risk_score >= 72 and trend_alignment_score >= 70:
            trend_grade = "trend_confirmed"
        elif structure_risk_score <= 42 or trend_failure_streak >= 3:
            trend_grade = "recovery"
        else:
            trend_grade = "transition"

        if structure_risk_score >= 70:
            structure_risk_band = "low"
        elif structure_risk_score <= 45:
            structure_risk_band = "high"
        else:
            structure_risk_band = "medium"

        return {
            "hist_rows": rows,
            "close": round(close, 4),
            "ma20": round(ma20, 4),
            "ma60": round(ma60, 4),
            "avg_volume_20d": round(avg_volume_20d, 2),
            "latest_volume": round(latest_volume, 2),
            "volume_spike_ratio": round(volume_spike_ratio, 2),
            "ma_spread_pct": round(ma_spread_pct, 2),
            "recent_extension_pct": round(recent_extension_pct, 2),
            "positive_days_ratio_pct": round(positive_days_ratio * 100.0, 2),
            "close_above_ma20": close_above_ma20,
            "close_above_ma60": close_above_ma60,
            "return_20d_pct": round(return_20d, 2),
            "return_60d_pct": round(return_60d, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "annualized_volatility_pct": round(annualized_volatility_pct, 2),
            "trend_alignment_score": round(min(100.0, trend_alignment_score), 2),
            "momentum_score": round(momentum_score, 2),
            "drawdown_resilience_score": round(drawdown_resilience_score, 2),
            "volatility_score": round(volatility_score, 2),
            "trend_consistency_score": round(trend_consistency_score, 2),
            "volume_confirmation_score": round(min(100.0, max(20.0, volume_confirmation_score)), 2),
            "breakout_quality_score": round(min(100.0, max(20.0, breakout_quality_score)), 2),
            "volume_price_divergence_score": round(min(100.0, max(20.0, volume_price_divergence_score)), 2),
            "structure_risk_score": round(min(100.0, max(20.0, structure_risk_score)), 2),
            "trend_failure_streak": trend_failure_streak,
            "support_loss_count": support_loss_count,
            "trend_grade": trend_grade,
            "structure_risk_band": structure_risk_band,
        }

    @staticmethod
    def _build_total_score(
        metrics: Dict[str, Any],
        fund_flow_verified: bool,
        weights: Dict[str, float] | None = None,
        fund_flow_bonus: float = 3.0,
        hist_rows_penalty: float = 10.0,
        hist_rows_minimum: int = 30,
        score_ceiling: float = 95.0,
        score_floor: float = 20.0,
    ) -> float:
        if weights is None:
            weights = {
                "trend_alignment": 0.22,
                "momentum": 0.18,
                "drawdown_resilience": 0.14,
                "volatility": 0.10,
                "trend_consistency": 0.12,
                "structure_risk": 0.11,
                "volume_confirmation": 0.07,
                "breakout_quality": 0.04,
                "divergence": 0.02,
            }
        base = (
            weights.get("trend_alignment", 0.22) * metrics["trend_alignment_score"]
            + weights.get("momentum", 0.18) * metrics["momentum_score"]
            + weights.get("drawdown_resilience", 0.14) * metrics["drawdown_resilience_score"]
            + weights.get("volatility", 0.10) * metrics["volatility_score"]
            + weights.get("trend_consistency", 0.12) * metrics["trend_consistency_score"]
            + weights.get("structure_risk", 0.11) * metrics["structure_risk_score"]
            + weights.get("volume_confirmation", 0.07) * metrics["volume_confirmation_score"]
            + weights.get("breakout_quality", 0.04) * metrics["breakout_quality_score"]
            + weights.get("divergence", 0.02) * metrics["volume_price_divergence_score"]
        )
        if fund_flow_verified:
            base += fund_flow_bonus
        if metrics["hist_rows"] < hist_rows_minimum:
            base -= hist_rows_penalty
        return round(min(score_ceiling, max(score_floor, base)), 2)

    @staticmethod
    def _compute_signal_consistency_index(metrics: Dict[str, Any]) -> float:
        score = 40.0
        if metrics.get("close_above_ma20", False):
            score += 12.0
        if metrics.get("close_above_ma60", False):
            score += 10.0
        score += max(0.0, min(18.0, (metrics.get("trend_consistency_score", 0.0) - 40.0) * 0.45))
        score += max(0.0, min(12.0, (metrics.get("volume_confirmation_score", 0.0) - 45.0) * 0.35))
        score -= max(0.0, min(18.0, (50.0 - metrics.get("volume_price_divergence_score", 50.0)) * 0.45))
        return round(min(100.0, max(20.0, score)), 2)

    @staticmethod
    def _build_degradation_reason(
        capability: Dict[str, Any],
        allow_yfinance_fallback: bool,
        hist_rows: int,
        hist_rows_minimum: int = 30,
    ) -> str:
        reasons: List[str] = []
        if not capability.get("fund_flow_bulk_verified", False):
            reasons.append("fund_flow_unverified")
        hist_verified = bool(capability.get("hist_fetch_verified", False))
        tencent_hist_verified = bool(capability.get("tencent_hist_verified", False))
        yfinance_hist_verified = bool(capability.get("yfinance_hist_verified", False))
        if not hist_verified and not tencent_hist_verified and not (
            allow_yfinance_fallback and yfinance_hist_verified
        ):
            reasons.append("hist_fetch_unverified")
        if hist_rows < hist_rows_minimum:
            reasons.append("insufficient_hist_rows")
        return ",".join(reasons)

    @staticmethod
    def _build_risk_flags(
        capability: Dict[str, Any],
        effective_hist_available: bool,
        allow_yfinance_fallback: bool,
        used_yfinance_hist: bool,
        used_tencent_hist: bool = False,
        hist_rows: int = 0,
        hist_rows_minimum: int = 30,
        metrics: Dict[str, Any] | None = None,
        signal_consistency_index: float = 50.0,
        signal_consistency_low: float = 45.0,
    ) -> List[str]:
        flags: List[str] = []
        metrics = metrics or {}
        if capability.get("fund_flow_fallback_vendor"):
            flags.append("fund_flow_primary_unavailable")
        if capability.get("hist_fetch_fallback_vendor") and not effective_hist_available:
            flags.append("hist_primary_unavailable")
        if used_tencent_hist:
            flags.append("using_tencent_hist_fallback")
        elif allow_yfinance_fallback and capability.get("yfinance_hist_verified", False):
            flags.append("using_yfinance_hist_fallback")
        if used_yfinance_hist:
            flags.append("yfinance_hist_data_attached")
        if hist_rows < hist_rows_minimum:
            flags.append("short_history_window")
        if metrics.get("structure_risk_score", 100.0) <= 45:
            flags.append("trend_structure_extended")
        if metrics.get("trend_consistency_score", 100.0) <= 48:
            flags.append("trend_consistency_weak")
        if metrics.get("volume_spike_ratio", 0.0) >= 1.8 and metrics.get("recent_extension_pct", 0.0) >= 8:
            flags.append("volume_exhaustion_risk")
        if metrics.get("volume_price_divergence_score", 100.0) <= 42:
            flags.append("price_volume_divergence")
        if metrics.get("trend_failure_streak", 0) >= 3:
            flags.append("trend_failure_streak_high")
        if metrics.get("support_loss_count", 0) >= 8:
            flags.append("support_loss_cluster")
        if not metrics.get("close_above_ma20", True):
            flags.append("lost_ma20_support")
        if signal_consistency_index <= signal_consistency_low:
            flags.append("signal_consistency_low")
        return flags

    @staticmethod
    def _count_recent_trend_failures(series: pd.Series) -> int:
        if series is None or series.empty:
            return 0
        recent = series.tail(min(12, len(series)))
        if len(recent) < 4:
            return 0
        failures = 0
        prev = None
        for value in recent:
            current = float(value)
            if prev is not None and current < prev:
                failures += 1
            prev = current
        return failures

    def _load_histories(
        self,
        universe: List[str],
        trade_date: str,
        capability: Dict[str, Any],
        tencent_hist_verified: bool,
        allow_yfinance_fallback: bool,
        hist_verified: bool,
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        lookback_days = self.config.get("strategies", {}).get("technical", {}).get("lookback_days", 100)
        end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=lookback_days + 30)
        start_date = start_dt.strftime("%Y-%m-%d")
        end_date = end_dt.strftime("%Y-%m-%d")

        histories: Dict[str, Any] = {}
        vendors: Dict[str, str] = {}
        total = len(universe)
        # Log progress every 50 stocks
        print_interval = 50
        _logger.info(f"[Technical] Starting history fetch for {total} stocks...")

        for i, raw_code in enumerate(universe):
            ticker = format_ticker(raw_code)
            try:
                hist = None
                vendor = ""
                if hist_verified and hasattr(self.data_access, "fetch_hist"):
                    hist = self.data_access.fetch_hist(ticker, start_date, end_date, adjust="qfq")
                    if hist is not None and not getattr(hist, "empty", True):
                        vendor = "primary_chain"
                if (hist is None or getattr(hist, "empty", True)) and tencent_hist_verified:
                    hist = self.data_access.fetch_tencent_hist(ticker, start_date, end_date)
                    if hist is not None and not getattr(hist, "empty", True):
                        vendor = "tencent"
                if (
                    (hist is None or getattr(hist, "empty", True))
                    and allow_yfinance_fallback
                    and capability.get("yfinance_hist_verified", False)
                ):
                    hist = self.data_access.fetch_yfinance_hist(ticker, start_date, end_date)
                    if hist is not None and not getattr(hist, "empty", True):
                        vendor = "yfinance"
                if hist is not None and not getattr(hist, "empty", True):
                    histories[ticker] = hist
                    vendors[ticker] = vendor
            except Exception:
                pass

            # Print progress every 50 stocks
            if (i + 1) % print_interval == 0 or (i + 1) == total:
                pct = (i + 1) * 100 // total
                print_progress_bar("Fetching histories", i + 1, total)

        clear_progress_line()
        console.print(f"[green][OK] Histories fetched[/green]  [cyan]{len(histories)}/{total}[/cyan] with valid data")
        if len(histories) == 0:
            console.print("[yellow][!] WARNING: no valid history data loaded, scoring will be degraded[/yellow]")
        return histories, vendors

    @staticmethod
    def _preview_hist(hist) -> Dict[str, Any]:
        if hist is None or getattr(hist, "empty", True):
            return {}
        tail = hist.tail(3)
        return {
            "rows": len(hist),
            "columns": list(getattr(hist, "columns", [])),
            "tail_index": [str(idx) for idx in tail.index.tolist()],
        }
