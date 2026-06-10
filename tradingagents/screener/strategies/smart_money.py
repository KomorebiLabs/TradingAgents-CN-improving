from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import pandas as pd

from tradingagents.screener.models import SignalCard, SignalEvidence
from tradingagents.screener.strategies.technical import placeholder_name, score_to_exchange
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


class SmartMoneyStrategy:
    def __init__(self, data_access, config: Dict[str, Any] | None = None):
        self.data_access = data_access
        self.config = config or {}

    def run(self, universe: List[str], trade_date: str) -> StrategyOutcome:
        console.print(f"[cyan]>> SmartMoneyStrategy[/cyan]  [dim]{len(universe)} stocks...", end="\r")

        capability = self.data_access.validate_interface_assumptions(trade_date=trade_date)
        smart_config = self.config.get("strategies", {}).get("smart_money", {})
        th = smart_config.get("thresholds", {})
        # A2: extract scoring weights for the total score formula
        score_weights = {
            "momentum": 0.24,
            "tick": 0.11,
            "tick_persistence": 0.10,
            "popularity": 0.12,
            "institutional": 0.11,
            "continuity": 0.10,
            "multi_day": 0.10,
            "valuation": 0.10,
            "risk_constraint": 0.07,
            "joint_quality": 0.10,
        }
        for k in list(score_weights.keys()):
            cfg_key = f"score_weight_{k}"
            if cfg_key in th:
                score_weights[k] = float(th[cfg_key])
        # A2: extract scoring base thresholds for parameterization
        scoring_bases = {
            "tick_base": float(th.get("tick_base", 45.0)),
            "tick_no_type_base": float(th.get("tick_no_type_base", 50.0)),
            "tick_large_trade_threshold": float(th.get("tick_large_trade_threshold", 100.0)),
            "tick_large_trade_bonus_per": float(th.get("tick_large_trade_bonus_per", 2.0)),
            "popularity_base": float(th.get("popularity_base", 45.0)),
            "popularity_no_value_base": float(th.get("popularity_no_value_base", 50.0)),
            "tick_persistence_base": float(th.get("tick_persistence_base", 45.0)),
            "tick_persistence_no_type_base": float(th.get("tick_persistence_no_type_base", 50.0)),
            "tick_persistence_streak_mult": float(th.get("tick_persistence_streak_mult", 4.0)),
            "valuation_neutral": float(th.get("valuation_neutral", 55.0)),
            "institutional_base": float(th.get("institutional_base", 45.0)),
            "institutional_no_match_base": float(th.get("institutional_no_match_base", 48.0)),
            "lhbc_base": float(th.get("lhbc_base", 42.0)),
            "joint_quality_base": float(th.get("joint_quality_base", 45.0)),
            "multi_day_base": float(th.get("multi_day_base", 42.0)),
            "risk_constraint_base": float(th.get("risk_constraint_base", 62.0)),
            "lookback_days": int(th.get("lookback_days", 140)),
        }
        quality_stability_low = float(th.get("quality_stability_low", 48.0))
        hist_rows_minimum = int(th.get("hist_rows_minimum", 20))
        deep_drawdown_pct = float(th.get("deep_drawdown_pct", 22.0))
        high_volatility_pct = float(th.get("high_volatility_pct", 55.0))
        overheated_valuation_mismatch_popularity = float(th.get("overheated_valuation_mismatch_popularity", 80.0))
        overheated_valuation_mismatch_valuation = float(th.get("overheated_valuation_mismatch_valuation", 45.0))
        heat_quality_gap_wide = float(th.get("heat_quality_gap_wide", 22.0))
        flow_continuity_weak = float(th.get("flow_continuity_weak", 50.0))
        continuity_fragile = float(th.get("continuity_fragile", 48.0))

        # A2: build full threshold_snapshot from config for output audit
        threshold_snapshot = {k: v for k, v in th.items()}
        threshold_snapshot["source"] = "smart_money"
        threshold_snapshot["effective_values"] = {
            "quality_stability_low": quality_stability_low,
            "hist_rows_minimum": hist_rows_minimum,
            "deep_drawdown_pct": deep_drawdown_pct,
            "high_volatility_pct": high_volatility_pct,
            "overheated_valuation_mismatch_popularity": overheated_valuation_mismatch_popularity,
            "overheated_valuation_mismatch_valuation": overheated_valuation_mismatch_valuation,
            "heat_quality_gap_wide": heat_quality_gap_wide,
            "flow_continuity_weak": flow_continuity_weak,
            "continuity_fragile": continuity_fragile,
            "score_weights": score_weights,
            "scoring_bases": scoring_bases,
        }
        cards: List[SignalCard] = []
        strategy_capability = capability.get("strategy_capabilities", {}).get("smart_money", {})
        hist_verified = bool(capability.get("hist_fetch_verified", False))
        tencent_hist_verified = bool(capability.get("tencent_hist_verified", False))
        yfinance_hist_verified = bool(capability.get("yfinance_hist_verified", False))
        allow_yfinance_fallback = bool(self.config.get("fallbacks", {}).get("enable_yfinance_backup", True))
        effective_hist_available = hist_verified or tencent_hist_verified or (
            allow_yfinance_fallback and yfinance_hist_verified
        )
        fund_flow_verified = bool(
            strategy_capability.get("fund_flow_verified", capability.get("fund_flow_verified", False))
        )
        tick_primary_vendor = strategy_capability.get("primary_dependencies", {}).get("tick_data", "tencent")
        valuation_auxiliary = strategy_capability.get("primary_dependencies", {}).get("valuation_auxiliary", "baidu")
        dragon_tiger_auxiliary = strategy_capability.get("primary_dependencies", {}).get(
            "dragon_tiger_auxiliary",
            "sina",
        )
        lhb_df = self.data_access.fetch_lhb_sina(trade_date) if hasattr(self.data_access, "fetch_lhb_sina") else None
        lhb_stats_df = (
            self.data_access.fetch_lhb_stats_sina("5") if hasattr(self.data_access, "fetch_lhb_stats_sina") else None
        )
        lhb_inst_df = (
            self.data_access.fetch_lhb_institutional_stats_sina("5")
            if hasattr(self.data_access, "fetch_lhb_institutional_stats_sina")
            else None
        )

        scored_cards: List[SignalCard] = []
        total = len(universe)
        log_interval = max(1, total // 10) if total > 0 else 1
        _logger.info(f"[SmartMoney] Starting analysis for {total} stocks...")

        console.print(f"[cyan]  SmartMoney scoring[/cyan]  [dim]{total} stocks...[/dim]", end="\r")

        for idx, raw_code in enumerate(universe):
            ticker = format_ticker(raw_code)
            hist_vendor, hist_metrics = self._load_hist_metrics(ticker, trade_date, capability)
            tick_df = (
                self.data_access.fetch_tick_data(self._ticker_to_prefixed_symbol(ticker))
                if hasattr(self.data_access, "fetch_tick_data")
                else None
            )
            vote_df = self.data_access.fetch_vote_baidu(symbol=raw_code) if hasattr(self.data_access, "fetch_vote_baidu") else None
            valuation_df = self.data_access.fetch_valuation_baidu() if hasattr(self.data_access, "fetch_valuation_baidu") else None

            tick_score = self._compute_tick_score(tick_df, scoring_bases=scoring_bases)
            tick_persistence_score = self._compute_tick_persistence_score(tick_df, scoring_bases=scoring_bases)
            popularity_score = self._compute_popularity_score(vote_df, scoring_bases=scoring_bases)
            valuation_score = self._compute_valuation_score(valuation_df, raw_code, scoring_bases=scoring_bases)
            institutional_score = self._compute_institutional_score(lhb_df, raw_code, scoring_bases=scoring_bases)
            continuity_score = self._compute_lhb_continuity_score(
                lhb_stats_df=lhb_stats_df,
                lhb_inst_df=lhb_inst_df,
                raw_code=raw_code,
                scoring_bases=scoring_bases,
            )
            continuity_grade = self._build_continuity_grade(continuity_score, hist_metrics)
            multi_day_persistence_score = self._compute_multi_day_persistence_score(
                hist_metrics=hist_metrics,
                tick_persistence_score=tick_persistence_score,
                continuity_score=continuity_score,
                scoring_bases=scoring_bases,
            )
            risk_constraint_score = self._compute_risk_constraint_score(
                hist_metrics=hist_metrics,
                tick_score=tick_score,
                popularity_score=popularity_score,
                valuation_score=valuation_score,
                continuity_score=continuity_score,
                scoring_bases=scoring_bases,
            )
            joint_quality_score = self._compute_joint_quality_score(
                popularity_score=popularity_score,
                valuation_score=valuation_score,
                tick_score=tick_score,
                continuity_score=continuity_score,
                risk_constraint_score=risk_constraint_score,
                scoring_bases=scoring_bases,
            )
            heat_quality_gap_score = self._compute_heat_quality_gap_score(
                popularity_score=popularity_score,
                valuation_score=valuation_score,
                continuity_score=continuity_score,
                risk_constraint_score=risk_constraint_score,
                institutional_score=institutional_score,
                scoring_bases=scoring_bases,
            )
            quality_stability_index = self._compute_quality_stability_index(
                multi_day_persistence_score=multi_day_persistence_score,
                risk_constraint_score=risk_constraint_score,
                continuity_score=continuity_score,
                heat_quality_gap_score=heat_quality_gap_score,
            )
            capital_quality_tag = self._build_capital_quality_tag(
                tick_score=tick_score,
                multi_day_persistence_score=multi_day_persistence_score,
                continuity_score=continuity_score,
                risk_constraint_score=risk_constraint_score,
                institutional_score=institutional_score,
                heat_quality_gap_score=heat_quality_gap_score,
            )
            capital_quality_band = self._build_capital_quality_band(
                capital_quality_tag=capital_quality_tag,
                risk_constraint_score=risk_constraint_score,
                continuity_score=continuity_score,
            )
            capital_quality_weight = self._compute_capital_quality_weight(
                capital_quality_tag=capital_quality_tag,
                risk_constraint_score=risk_constraint_score,
                continuity_score=continuity_score,
                heat_quality_gap_score=heat_quality_gap_score,
            )
            # A2: use neutral default from scoring_bases when valuation data unavailable
            vs = valuation_score if valuation_score is not None else scoring_bases["valuation_neutral"]
            score = round(
                min(
                    100.0,
                    score_weights["momentum"] * hist_metrics["momentum_score"]
                    + score_weights["tick"] * tick_score
                    + score_weights["tick_persistence"] * tick_persistence_score
                    + score_weights["popularity"] * popularity_score
                    + score_weights["institutional"] * institutional_score
                    + score_weights["continuity"] * continuity_score
                    + score_weights["multi_day"] * multi_day_persistence_score
                    + score_weights["valuation"] * vs
                    + score_weights["risk_constraint"] * risk_constraint_score
                    + score_weights["joint_quality"] * joint_quality_score,
                ),
                2,
            )
            score = round(min(100.0, max(20.0, score + capital_quality_weight)), 2)
            degraded = not effective_hist_available or hist_metrics["hist_rows"] < hist_rows_minimum
            evidence = SignalEvidence(
                strategy="smart_money",
                score=score,
                rank_in_strategy=idx + 1,
                reason="Tencent-first capital-flow proxy using hist, tick, popularity and龙虎榜 enhancements",
                raw_metrics={
                    "score_family": "smart_money_capital_quality_v1",
                    "hist_primary_vendor": strategy_capability.get("primary_dependencies", {}).get(
                        "hist_fetch",
                        capability.get("hist_primary_vendor", "tencent"),
                    ),
                    "resolved_hist_vendor": hist_vendor,
                    "tick_primary_vendor": tick_primary_vendor,
                    "valuation_auxiliary_vendor": valuation_auxiliary,
                    "dragon_tiger_auxiliary_vendor": dragon_tiger_auxiliary,
                    "tencent_hist_verified": tencent_hist_verified,
                    "yfinance_hist_verified": yfinance_hist_verified,
                    "fund_flow_verified": fund_flow_verified,
                    "hist_rows": hist_metrics["hist_rows"],
                    "momentum_score": hist_metrics["momentum_score"],
                    "return_20d_pct": hist_metrics["return_20d_pct"],
                    "tick_score": tick_score,
                    "tick_persistence_score": tick_persistence_score,
                    "popularity_score": popularity_score,
                    "valuation_score": valuation_score,
                    "institutional_score": institutional_score,
                    "continuity_score": continuity_score,
                    "continuity_grade": continuity_grade,
                    "multi_day_persistence_score": multi_day_persistence_score,
                    "quality_stability_index": quality_stability_index,
                    "risk_constraint_score": risk_constraint_score,
                    "joint_quality_score": joint_quality_score,
                    "heat_quality_gap_score": heat_quality_gap_score,
                    "capital_quality_tag": capital_quality_tag,
                    "capital_quality_band": capital_quality_band,
                    "capital_quality_weight": capital_quality_weight,
                    "capital_quality_summary": self._build_capital_quality_summary(
                        capital_quality_tag=capital_quality_tag,
                        risk_constraint_score=risk_constraint_score,
                        continuity_score=continuity_score,
                        institutional_score=institutional_score,
                        heat_quality_gap_score=heat_quality_gap_score,
                    ),
                    "strategy_status_hint": strategy_capability.get("status_hint", "degraded"),
                    "production_rule_version": "smart_money_pg_v3",
                    # A2: store the full config-driven threshold_snapshot, not just quality_stability_low
                    "threshold_snapshot": threshold_snapshot,
                    "degraded_context": {
                        "effective_hist_available": effective_hist_available,
                        "fund_flow_verified": fund_flow_verified,
                        "hist_rows": hist_metrics["hist_rows"],
                        "capital_quality_tag": capital_quality_tag,
                        "valuation_available": valuation_score is not None,  # H2 FIX: track valuation availability
                    },
                    "vendor_trace": {
                        "hist_primary_vendor": strategy_capability.get("primary_dependencies", {}).get(
                            "hist_fetch",
                            capability.get("hist_primary_vendor", "tencent"),
                        ),
                        "tick_primary_vendor": tick_primary_vendor,
                        "valuation_auxiliary_vendor": valuation_auxiliary,
                        "dragon_tiger_auxiliary_vendor": dragon_tiger_auxiliary,
                    },
                },
                freshness=capability.get("freshness", []),
                degraded=degraded,
                degradation_reason="hist_fetch_unverified" if degraded else "",
            )
            scored_cards.append(
                SignalCard(
                    ticker=ticker,
                    raw_code=raw_code,
                    exchange=score_to_exchange(raw_code),
                    company_name=placeholder_name(raw_code),
                    trade_date=trade_date,
                    sector_tags=["capital_flow", capital_quality_tag],
                    concept_tags=["smart_money_enhanced", capital_quality_tag, capital_quality_band],
                    strategy_sources=["smart_money"],
                    signal_breakdown=[evidence],
                    trigger_reason=self._build_trigger_reason(
                        degraded=degraded,
                        capital_quality_tag=capital_quality_tag,
                    ),
                    initial_confidence=min(93.0, score * 0.88 + (4.0 if not degraded else 0.0)),
                    risk_flags=self._build_risk_flags(
                        effective_hist_available=effective_hist_available,
                        fund_flow_verified=fund_flow_verified,
                        hist_rows=hist_metrics["hist_rows"],
                        tick_df=tick_df,
                        lhb_df=lhb_df,
                        hist_metrics=hist_metrics,
                        popularity_score=popularity_score,
                        valuation_score=valuation_score,
                        continuity_score=continuity_score,
                        capital_quality_tag=capital_quality_tag,
                        heat_quality_gap_score=heat_quality_gap_score,
                        quality_stability_index=quality_stability_index,
                        quality_stability_low=quality_stability_low,
                        hist_rows_minimum=hist_rows_minimum,
                        deep_drawdown_pct=deep_drawdown_pct,
                        high_volatility_pct=high_volatility_pct,
                        overheated_valuation_mismatch_popularity=overheated_valuation_mismatch_popularity,
                        overheated_valuation_mismatch_valuation=overheated_valuation_mismatch_valuation,
                        heat_quality_gap_wide=heat_quality_gap_wide,
                        flow_continuity_weak=flow_continuity_weak,
                        continuity_fragile=continuity_fragile,
                    ),
                    screening_score=score,
                    data_source_verified=effective_hist_available and hist_metrics["hist_rows"] >= hist_rows_minimum,
                    evidence_snapshot={
                        "capability_summary": capability,
                        "strategy_capability": strategy_capability,
                        "strategy": "smart_money",
                        "hist_metrics": hist_metrics,
                        "tick_preview": self._preview_rows(tick_df),
                        "lhb_preview": self._preview_rows(lhb_df),
                        "lhb_stats_preview": self._preview_rows(lhb_stats_df),
                        "lhb_inst_preview": self._preview_rows(lhb_inst_df),
                        "capital_quality_tag": capital_quality_tag,
                        "capital_quality_band": capital_quality_band,
                        "capital_quality_summary": self._build_capital_quality_summary(
                            capital_quality_tag=capital_quality_tag,
                            risk_constraint_score=risk_constraint_score,
                            continuity_score=continuity_score,
                            institutional_score=institutional_score,
                            heat_quality_gap_score=heat_quality_gap_score,
                        ),
                        # A2: full threshold audit trail
                        "threshold_snapshot": threshold_snapshot,
                    },
                )
            )

            # Print progress every 50 stocks
            if (idx + 1) % 50 == 0 or (idx + 1) == total:
                pct = (idx + 1) * 100 // total
                print_progress_bar("SmartMoney scoring", idx + 1, total)

        # Print progress every 50 stocks
        if total > 0:
            clear_progress_line()
        else:
            console.print("[yellow]  SmartMoney: 0 stocks to process[/yellow]")

        console.print(f"[cyan]  SmartMoney:[/cyan] [dim]sorting {len(scored_cards)} cards...[/dim]", end="\r")

        scored_cards.sort(key=lambda card: card.screening_score, reverse=True)
        top_n = self.config.get("strategies", {}).get("smart_money", {}).get("top_output", 200)
        cards = scored_cards[: min(len(scored_cards), top_n)]
        for rank, card in enumerate(cards, 1):
            if card.signal_breakdown:
                card.signal_breakdown[0].rank_in_strategy = rank

        warnings = list(capability.get("warnings", []))
        status = (
            "ready"
            if cards and strategy_capability.get("status_hint") == "ready" and effective_hist_available
            else "degraded"
        )
        console.print(f"[green][OK] SmartMoneyStrategy done[/green]  [cyan]{len(cards)}[/cyan] cards  [dim]status={status}[/dim]")
        return StrategyOutcome(cards=cards, status=status, warnings=warnings)

    def _load_hist_metrics(self, ticker: str, trade_date: str, capability: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        from tradingagents.screener.strategies.technical import TechnicalStrategy

        trade_dt = pd.Timestamp(trade_date)
        start_date = (trade_dt - pd.Timedelta(days=140)).strftime("%Y-%m-%d")
        end_date = trade_dt.strftime("%Y-%m-%d")

        hist = None
        vendor = ""
        if capability.get("hist_fetch_verified", False) and hasattr(self.data_access, "fetch_hist"):
            hist = self.data_access.fetch_hist(ticker, start_date, end_date, adjust="qfq")
            if hist is not None and not getattr(hist, "empty", True):
                vendor = "primary_chain"
        if (
            (hist is None or getattr(hist, "empty", True))
            and capability.get("tencent_hist_verified", False)
            and hasattr(self.data_access, "fetch_tencent_hist")
        ):
            hist = self.data_access.fetch_tencent_hist(ticker, start_date, end_date)
            if hist is not None and not getattr(hist, "empty", True):
                vendor = "tencent"
        if (
            (hist is None or getattr(hist, "empty", True))
            and capability.get("yfinance_hist_verified", False)
            and self.config.get("fallbacks", {}).get("enable_yfinance_backup", True)
            and hasattr(self.data_access, "fetch_yfinance_hist")
        ):
            hist = self.data_access.fetch_yfinance_hist(ticker, start_date, end_date)
            if hist is not None and not getattr(hist, "empty", True):
                vendor = "yfinance"
        return vendor or "none", TechnicalStrategy._compute_hist_metrics(hist)

    @staticmethod
    def _ticker_to_prefixed_symbol(ticker: str) -> str:
        code, suffix = ticker.split(".", 1)
        if suffix.upper() == "SH":
            return f"sh{code}"
        if suffix.upper() == "BJ":
            return f"bj{code}"
        return f"sz{code}"

    @staticmethod
    def _compute_tick_score(tick_df: Any, scoring_bases: Dict[str, Any] | None = None) -> float:
        sb = scoring_bases or {}
        tick_base = sb.get("tick_base", 45.0)
        tick_no_type_base = sb.get("tick_no_type_base", 50.0)
        tick_large_trade_threshold = sb.get("tick_large_trade_threshold", 100.0)
        tick_large_trade_bonus_per = sb.get("tick_large_trade_bonus_per", 2.0)
        if tick_df is None or getattr(tick_df, "empty", True):
            return tick_base
        columns = {str(col).lower(): col for col in tick_df.columns}
        type_col = columns.get("type") or columns.get("性质")
        volume_col = columns.get("volume") or columns.get("成交量")
        if type_col is None:
            return tick_no_type_base
        buy_weight = 0.0
        sell_weight = 0.0
        large_trade_bonus = 0.0
        for _, row in tick_df.head(200).iterrows():
            weight = 1.0
            if volume_col is not None:
                try:
                    weight = float(row[volume_col])
                except Exception:
                    weight = 1.0
            kind = str(row[type_col])
            if "买" in kind or kind.lower().startswith("b"):
                buy_weight += weight
                if weight >= tick_large_trade_threshold:
                    large_trade_bonus += tick_large_trade_bonus_per
            elif "卖" in kind or kind.lower().startswith("s"):
                sell_weight += weight
                if weight >= tick_large_trade_threshold:
                    large_trade_bonus -= tick_large_trade_bonus_per
        total = buy_weight + sell_weight
        if total <= 0:
            return tick_no_type_base
        imbalance = (buy_weight - sell_weight) / total
        return round(min(100.0, max(20.0, tick_no_type_base + imbalance * 50.0 + large_trade_bonus)), 2)

    @staticmethod
    def _compute_popularity_score(vote_df: Any, scoring_bases: Dict[str, Any] | None = None) -> float:
        sb = scoring_bases or {}
        popularity_base = sb.get("popularity_base", 45.0)
        popularity_no_value_base = sb.get("popularity_no_value_base", 50.0)
        if vote_df is None or getattr(vote_df, "empty", True):
            return popularity_base
        text = " ".join(str(value) for value in vote_df.astype(str).values.flatten().tolist())
        numeric_values: List[float] = []
        for token in text.replace("%", " ").split():
            try:
                numeric_values.append(float(token))
            except ValueError:
                continue
        if not numeric_values:
            return popularity_no_value_base
        anchor = max(numeric_values[:10])
        return round(min(100.0, max(20.0, 40.0 + anchor * 0.6)), 2)

    @staticmethod
    def _compute_tick_persistence_score(tick_df: Any, scoring_bases: Dict[str, Any] | None = None) -> float:
        sb = scoring_bases or {}
        tick_persistence_base = sb.get("tick_persistence_base", 45.0)
        tick_persistence_no_type_base = sb.get("tick_persistence_no_type_base", 50.0)
        tick_persistence_streak_mult = sb.get("tick_persistence_streak_mult", 4.0)
        if tick_df is None or getattr(tick_df, "empty", True):
            return tick_persistence_base
        columns = {str(col).lower(): col for col in tick_df.columns}
        type_col = columns.get("type") or columns.get("性质")
        if type_col is None:
            return tick_persistence_no_type_base
        recent = [str(value) for value in tick_df.head(30)[type_col].tolist()]
        if not recent:
            return tick_persistence_no_type_base
        streak = 0
        max_streak = 0
        prev_buy = None
        for value in recent:
            current_buy = "买" in value or value.lower().startswith("b")
            if prev_buy is None or current_buy == prev_buy:
                streak += 1
            else:
                streak = 1
            prev_buy = current_buy
            max_streak = max(max_streak, streak)
        return round(min(100.0, max(20.0, tick_persistence_base + max_streak * tick_persistence_streak_mult)), 2)

    @staticmethod
    def _compute_valuation_score(valuation_df: Any, raw_code: str, scoring_bases: Dict[str, Any] | None = None) -> float | None:
        """计算估值评分。

        Phase 2 H2 FIX: 当找不到股票时返回 None，而非取 df.iloc[0]（张冠李戴）。
        下游消费者负责将 None 处理为中性逻辑（既不加也不减分）。
        """
        sb = scoring_bases or {}
        valuation_neutral = sb.get("valuation_neutral", 55.0)
        if valuation_df is None or getattr(valuation_df, "empty", True):
            return None
        code_columns = [col for col in valuation_df.columns if "code" in str(col).lower() or "代码" in str(col)]
        code_col = code_columns[0] if code_columns else None
        if code_col is None:
            return None
        matches = valuation_df[valuation_df[code_col].astype(str).str.contains(raw_code, na=False)]
        if matches.empty:
            return None
        row = matches.iloc[0]
        pe = None
        pb = None
        for col in valuation_df.columns:
            label = str(col).lower()
            if pe is None and ("pe" in label or "市盈率" in str(col)):
                try:
                    pe = float(row[col])
                except Exception:
                    pe = None
            if pb is None and ("pb" in label or "市净率" in str(col)):
                try:
                    pb = float(row[col])
                except Exception:
                    pb = None
        if pe is None and pb is None:
            return None
        score = valuation_neutral
        if pe is not None:
            if 0 < pe < 35:
                score += 20.0
            elif pe > 80 or pe < 0:
                score -= 15.0
        if pb is not None:
            if 0 < pb < 5:
                score += 10.0
            elif pb > 10:
                score -= 10.0
        return round(min(100.0, max(20.0, score)), 2)

    @staticmethod
    def _compute_institutional_score(lhb_df: Any, raw_code: str, scoring_bases: Dict[str, Any] | None = None) -> float:
        sb = scoring_bases or {}
        institutional_base = sb.get("institutional_base", 45.0)
        institutional_no_match_base = sb.get("institutional_no_match_base", 48.0)
        if lhb_df is None or getattr(lhb_df, "empty", True):
            return institutional_base
        code_columns = [col for col in lhb_df.columns if "代码" in str(col) or "symbol" in str(col).lower()]
        if code_columns:
            code_col = code_columns[0]
            matches = lhb_df[lhb_df[code_col].astype(str).str.contains(raw_code, na=False)]
            if not matches.empty:
                row = matches.iloc[0]
                score = institutional_base + 23.0  # 68.0 - 45.0 = 23.0 delta from base
                for col in lhb_df.columns:
                    label = str(col)
                    if "成交额" in label or "对应值" in label:
                        try:
                            value = float(row[col])
                        except Exception:
                            value = 0.0
                        if value > 5e8:
                            score += 16.0
                        elif value > 1e8:
                            score += 8.0
                return round(min(100.0, max(20.0, score)), 2)
        return institutional_no_match_base

    @staticmethod
    def _compute_lhb_continuity_score(
        lhb_stats_df: Any,
        lhb_inst_df: Any,
        raw_code: str,
        scoring_bases: Dict[str, Any] | None = None,
    ) -> float:
        sb = scoring_bases or {}
        lhbc_base = sb.get("lhbc_base", 42.0)
        score = lhbc_base
        code = raw_code.zfill(6)
        if lhb_stats_df is not None and not getattr(lhb_stats_df, "empty", True):
            code_cols = [col for col in lhb_stats_df.columns if "代码" in str(col)]
            if code_cols:
                code_col = code_cols[0]
                matches = lhb_stats_df[lhb_stats_df[code_col].astype(str).str.contains(code, na=False)]
                if not matches.empty:
                    row = matches.iloc[0]
                    try:
                        count = float(row.get("上榜次数", 0))
                    except Exception:
                        count = 0.0
                    try:
                        net = float(row.get("净额", 0))
                    except Exception:
                        net = 0.0
                    score += min(20.0, count * 4.0)
                    if net > 0:
                        score += 10.0
        if lhb_inst_df is not None and not getattr(lhb_inst_df, "empty", True):
            code_cols = [col for col in lhb_inst_df.columns if "代码" in str(col)]
            if code_cols:
                code_col = code_cols[0]
                matches = lhb_inst_df[lhb_inst_df[code_col].astype(str).str.contains(code, na=False)]
                if not matches.empty:
                    row = matches.iloc[0]
                    try:
                        net = float(row.get("净额", 0))
                    except Exception:
                        net = 0.0
                    try:
                        buy_times = float(row.get("买入次数", 0))
                    except Exception:
                        buy_times = 0.0
                    score += min(15.0, buy_times * 3.0)
                    if net > 0:
                        score += 8.0
        return round(min(100.0, max(20.0, score)), 2)

    @staticmethod
    def _compute_joint_quality_score(
        popularity_score: float,
        valuation_score: float | None,
        tick_score: float,
        continuity_score: float,
        risk_constraint_score: float,
        scoring_bases: Dict[str, Any] | None = None,
    ) -> float:
        sb = scoring_bases or {}
        joint_quality_base = sb.get("joint_quality_base", 45.0)
        score = joint_quality_base
        if popularity_score >= 70 and tick_score >= 60:
            score += 20.0
        if valuation_score is not None and valuation_score >= 70:
            score += 15.0
        elif valuation_score is not None and valuation_score <= 40 and popularity_score >= 75:
            score -= 8.0
        elif valuation_score is None and popularity_score >= 75:
            pass  # no penalty when valuation unavailable (neutral stance)
        if tick_score >= 75:
            score += 10.0
        if continuity_score >= 70:
            score += 8.0
        if risk_constraint_score <= 45:
            score -= 12.0
        return round(min(100.0, max(20.0, score)), 2)

    @staticmethod
    def _compute_multi_day_persistence_score(
        hist_metrics: Dict[str, Any],
        tick_persistence_score: float,
        continuity_score: float,
        scoring_bases: Dict[str, Any] | None = None,
    ) -> float:
        sb = scoring_bases or {}
        multi_day_base = sb.get("multi_day_base", 42.0)
        tick_persistence_base = sb.get("tick_persistence_base", 45.0)
        lhbc_base = sb.get("lhbc_base", 42.0)
        score = multi_day_base
        if hist_metrics.get("return_20d_pct", 0.0) > 0:
            score += min(18.0, hist_metrics.get("return_20d_pct", 0.0) * 0.7)
        if hist_metrics.get("return_20d_pct", 0.0) >= hist_metrics.get("return_60d_pct", 0.0) * 0.4:
            score += 8.0
        score += max(0.0, (tick_persistence_score - tick_persistence_base) * 0.25)
        score += max(0.0, (continuity_score - lhbc_base) * 0.28)
        if hist_metrics.get("max_drawdown_pct", 0.0) > 18:
            score -= 8.0
        return round(min(100.0, max(20.0, score)), 2)

    @staticmethod
    def _build_continuity_grade(continuity_score: float, hist_metrics: Dict[str, Any]) -> str:
        if continuity_score >= 72 and hist_metrics.get("return_20d_pct", 0.0) > 0:
            return "continuity_strong"
        if continuity_score >= 58:
            return "continuity_stable"
        if continuity_score <= 48:
            return "continuity_fragile"
        return "continuity_mixed"

    @staticmethod
    def _compute_risk_constraint_score(
        hist_metrics: Dict[str, Any],
        tick_score: float,
        popularity_score: float,
        valuation_score: float | None,
        continuity_score: float,
        scoring_bases: Dict[str, Any] | None = None,
    ) -> float:
        sb = scoring_bases or {}
        risk_constraint_base = sb.get("risk_constraint_base", 62.0)
        high_volatility_pct = sb.get("high_volatility_pct", 55.0)
        deep_drawdown_pct = sb.get("deep_drawdown_pct", 22.0)
        score = risk_constraint_base
        if hist_metrics.get("annualized_volatility_pct", 0.0) <= 30:
            score += 10.0
        elif hist_metrics.get("annualized_volatility_pct", 0.0) >= high_volatility_pct:
            score -= 14.0
        if hist_metrics.get("max_drawdown_pct", 0.0) <= 10:
            score += 8.0
        elif hist_metrics.get("max_drawdown_pct", 0.0) >= deep_drawdown_pct:
            score -= 10.0
        if valuation_score is not None:
            if popularity_score >= 80 and valuation_score <= 45:
                score -= 12.0
        if tick_score >= 75 and continuity_score <= 52:
            score -= 10.0
        if valuation_score is not None and valuation_score >= 70 and continuity_score >= 65:
            score += 8.0
        return round(min(100.0, max(20.0, score)), 2)

    @staticmethod
    def _compute_heat_quality_gap_score(
        popularity_score: float,
        valuation_score: float | None,
        continuity_score: float,
        risk_constraint_score: float,
        institutional_score: float,
        scoring_bases: Dict[str, Any] | None = None,
    ) -> float:
        sb = scoring_bases or {}
        valuation_neutral = sb.get("valuation_neutral", 55.0)
        vs = valuation_score if valuation_score is not None else valuation_neutral
        quality_anchor = (
            0.30 * vs
            + 0.25 * continuity_score
            + 0.25 * risk_constraint_score
            + 0.20 * institutional_score
        )
        return round(popularity_score - quality_anchor, 2)

    @staticmethod
    def _compute_quality_stability_index(
        multi_day_persistence_score: float,
        risk_constraint_score: float,
        continuity_score: float,
        heat_quality_gap_score: float,
    ) -> float:
        score = (
            0.36 * multi_day_persistence_score
            + 0.32 * risk_constraint_score
            + 0.22 * continuity_score
            + 0.10 * max(20.0, 100.0 - max(0.0, heat_quality_gap_score))
        )
        return round(min(100.0, max(20.0, score)), 2)

    @staticmethod
    def _build_capital_quality_tag(
        tick_score: float,
        multi_day_persistence_score: float,
        continuity_score: float,
        risk_constraint_score: float,
        institutional_score: float,
        heat_quality_gap_score: float,
    ) -> str:
        if (
            tick_score >= 68
            and multi_day_persistence_score >= 68
            and continuity_score >= 65
            and risk_constraint_score >= 62
            and institutional_score >= 68
            and heat_quality_gap_score <= 18
        ):
            return "capital_quality_high"
        if (
            risk_constraint_score <= 45
            or (tick_score >= 72 and continuity_score <= 50)
            or heat_quality_gap_score >= 22
        ):
            return "capital_quality_speculative"
        if continuity_score >= 58 and multi_day_persistence_score >= 58:
            return "capital_quality_persistent"
        return "capital_quality_mixed"

    @staticmethod
    def _build_capital_quality_band(
        capital_quality_tag: str,
        risk_constraint_score: float,
        continuity_score: float,
    ) -> str:
        if capital_quality_tag == "capital_quality_high":
            return "capital_band_blue_chip"
        if capital_quality_tag == "capital_quality_persistent":
            return "capital_band_persistent"
        if capital_quality_tag == "capital_quality_speculative":
            return "capital_band_speculative"
        if risk_constraint_score <= 45 or continuity_score <= 48:
            return "capital_band_fragile"
        return "capital_band_mixed"

    @staticmethod
    def _compute_capital_quality_weight(
        capital_quality_tag: str,
        risk_constraint_score: float,
        continuity_score: float,
        heat_quality_gap_score: float,
    ) -> float:
        if capital_quality_tag == "capital_quality_high":
            return 5.0
        if capital_quality_tag == "capital_quality_persistent":
            return 2.5
        if capital_quality_tag == "capital_quality_speculative":
            penalty = -4.0
            if risk_constraint_score <= 40:
                penalty -= 2.0
            if continuity_score <= 48:
                penalty -= 1.5
            if heat_quality_gap_score >= 28:
                penalty -= 1.5
            return penalty
        return 0.0

    @staticmethod
    def _build_capital_quality_summary(
        capital_quality_tag: str,
        risk_constraint_score: float,
        continuity_score: float,
        institutional_score: float,
        heat_quality_gap_score: float,
    ) -> str:
        if capital_quality_tag == "capital_quality_high":
            return (
                f"high-quality persistent flow | risk={risk_constraint_score} "
                f"| continuity={continuity_score} | institutional={institutional_score} "
                f"| heat_gap={heat_quality_gap_score}"
            )
        if capital_quality_tag == "capital_quality_persistent":
            return (
                f"persistent flow with acceptable quality | risk={risk_constraint_score} "
                f"| continuity={continuity_score} | heat_gap={heat_quality_gap_score}"
            )
        if capital_quality_tag == "capital_quality_speculative":
            return (
                f"speculative high-heat flow | risk={risk_constraint_score} "
                f"| continuity={continuity_score} | institutional={institutional_score} "
                f"| heat_gap={heat_quality_gap_score}"
            )
        return (
            f"mixed capital quality | risk={risk_constraint_score} "
            f"| continuity={continuity_score} | institutional={institutional_score} "
            f"| heat_gap={heat_quality_gap_score}"
        )

    @staticmethod
    def _build_trigger_reason(degraded: bool, capital_quality_tag: str) -> str:
        if degraded:
            return "smart_money_degraded"
        if capital_quality_tag == "capital_quality_high":
            return "smart_money_persistent_high_quality"
        if capital_quality_tag == "capital_quality_persistent":
            return "smart_money_persistent_flow"
        if capital_quality_tag == "capital_quality_speculative":
            return "smart_money_speculative_flow"
        return "smart_money_capital_flow_composite"

    @staticmethod
    def _build_risk_flags(
        effective_hist_available: bool,
        fund_flow_verified: bool,
        hist_rows: int,
        tick_df: Any,
        lhb_df: Any,
        hist_metrics: Dict[str, Any],
        popularity_score: float,
        valuation_score: float | None,
        continuity_score: float,
        capital_quality_tag: str,
        heat_quality_gap_score: float,
        quality_stability_index: float,
        quality_stability_low: float,
        # A2: configurable risk flag thresholds
        hist_rows_minimum: int = 20,
        deep_drawdown_pct: float = 22.0,
        high_volatility_pct: float = 55.0,
        overheated_valuation_mismatch_popularity: float = 80.0,
        overheated_valuation_mismatch_valuation: float = 45.0,
        heat_quality_gap_wide: float = 22.0,
        flow_continuity_weak: float = 50.0,
        continuity_fragile: float = 48.0,
    ) -> List[str]:
        flags: List[str] = []
        if not effective_hist_available:
            flags.append("hist_primary_unavailable")
        if not fund_flow_verified:
            flags.append("fund_flow_enhancement_unavailable")
        if hist_rows < hist_rows_minimum:
            flags.append("short_history_window")
        if tick_df is None or getattr(tick_df, "empty", True):
            flags.append("tick_data_unavailable")
        if lhb_df is None or getattr(lhb_df, "empty", True):
            flags.append("lhb_unavailable")
        if hist_metrics.get("max_drawdown_pct", 0.0) >= deep_drawdown_pct:
            flags.append("deep_drawdown_risk")
        if hist_metrics.get("annualized_volatility_pct", 0.0) >= high_volatility_pct:
            flags.append("high_volatility_risk")
        # H2 FIX: only apply valuation-based risk check when valuation data is available
        if valuation_score is not None and popularity_score >= overheated_valuation_mismatch_popularity and valuation_score <= overheated_valuation_mismatch_valuation:
            flags.append("overheated_valuation_mismatch")
        if heat_quality_gap_score >= heat_quality_gap_wide:
            flags.append("heat_quality_gap_wide")
        if continuity_score <= flow_continuity_weak:
            flags.append("flow_continuity_weak")
        if capital_quality_tag == "capital_quality_speculative":
            flags.append("speculative_flow_dominant")
        if continuity_score <= continuity_fragile:
            flags.append("continuity_fragile")
        if quality_stability_index <= quality_stability_low:
            flags.append("quality_stability_low")
        return flags

    @staticmethod
    def _preview_rows(df: Any) -> List[Dict[str, Any]]:
        if df is None or getattr(df, "empty", True):
            return []
        return df.head(3).to_dict(orient="records")
