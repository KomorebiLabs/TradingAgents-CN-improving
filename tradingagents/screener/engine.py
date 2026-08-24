from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4
from typing import Any, Dict, List
import pandas as pd

from tradingagents.screener.config import SCREENER_CONFIG, SCREENER_THRESHOLDS
from tradingagents.screener.merger import merge_signal_cards
from tradingagents.ui.screener_console import (
    console,
    print_header_banner,
    print_stage_header,
    print_completion_banner,
    print_progress_bar,
    clear_progress_line,
)


def _extract_strategy_thresholds(cards: List) -> Dict[str, Any]:
    """Extract threshold_snapshot from the first card's evidence_snapshot."""
    for card in cards:
        snap = card.evidence_snapshot
        if snap and isinstance(snap, dict):
            ts = snap.get("threshold_snapshot") or snap.get("production_threshold_snapshot")
            if ts:
                return dict(ts)
    return {}


def _summarize_drop_reasons(drop_reasons: Dict[str, List[str]]) -> Dict[str, int]:
    """Summarize drop reasons into counts."""
    summary = {}
    for reason, tickers in drop_reasons.items():
        if tickers:
            summary[reason] = len(tickers)
    return summary


from tradingagents.screener.models import ScreenerMetrics, ScreeningResult
from tradingagents.screener.report import write_run_artifacts
from tradingagents.screener.runtime_guard import (
    RuntimeTimeConfig,
    check_data_consistency,
    validate_screener_run,
)
from tradingagents.screener.universe import build_screening_universe


@dataclass(frozen=True)
class StageACandidate:
    """Explainable lightweight score used only to budget Stage B work."""

    ticker: str
    data_completeness_score: float
    liquidity_score: float
    basic_momentum_score: float
    stage_a_score: float


class ScreenerEngine:
    """A1 skeleton engine.

    This version only establishes runtime validation, universe construction,
    metrics, and result packaging. Strategy execution will be added in A2.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}

    def _build_strategies(self, data_access):
        from tradingagents.screener.strategies import PolicyStrategy, SmartMoneyStrategy, TechnicalStrategy

        return (
            TechnicalStrategy(data_access, self.config),
            PolicyStrategy(data_access, self.config),
            SmartMoneyStrategy(data_access, self.config),
        )

    def _build_data_access(self):
        from tradingagents.screener.data_access import ScreenerDataAccess

        return ScreenerDataAccess(self.config)

    def _build_deep_analyzer(self):
        from tradingagents.screener.deep_analyzer import DeepAnalyzer

        return DeepAnalyzer(self.config)

    def _build_runtime_config(self) -> RuntimeTimeConfig:
        runtime = self.config.get("run_time", {})
        return RuntimeTimeConfig(
            earliest_run_time=runtime.get("earliest", "16:30"),
            latest_next_day=runtime.get("latest_next_day", "09:00"),
            allow_weekend=runtime.get("allow_weekend", False),
            allow_non_trading_day_override=runtime.get("allow_non_trading_day_override", False),
            allow_experimental_intraday=runtime.get("allow_experimental_intraday", True),
            max_data_age_days=runtime.get("max_data_age_days", 2),
        )

    @staticmethod
    def _prepare_stagea_input(tickers: List[str], max_input: int) -> List[str]:
        """Deduplicate in source order, then enforce the Stage A input budget."""
        budget = max(0, int(max_input))
        return list(dict.fromkeys(tickers))[:budget]

    @staticmethod
    def _select_stageb_candidates(
        candidates: List[StageACandidate], max_input: int
    ) -> List[StageACandidate]:
        """Select the strongest Stage A candidates with deterministic tie-breaking."""
        budget = max(0, int(max_input))
        return sorted(candidates, key=lambda item: (-item.stage_a_score, item.ticker))[:budget]

    def _run_stage_a(
        self,
        tickers: List[str],
        trade_date: str,
        data_access: Any,
    ) -> tuple[List[StageACandidate], Dict[str, List[str]]]:
        """Stage A: Light pre-screening to quickly eliminate obviously invalid stocks.

        P5-3: Uses fast, low-cost checks to reduce Stage B computation load.
        Returns (passed_tickers, drop_reasons_dict).

        Checks per Plan5:
        1. History data availability (critical for all strategies)
        2. Minimum history rows (data completeness)
        3. Basic liquidity (turnover rate)
        4. Extreme price anomaly (limit up/down)
        """
        import logging
        _logger = logging.getLogger(__name__)

        from tradingagents.ui.screener_console import print_progress_bar, clear_progress_line, console

        passed: List[StageACandidate] = []
        total = len(tickers)
        lookback_days = self.config.get("strategies", {}).get("technical", {}).get("lookback_days", 100)
        from datetime import datetime as _dt, timedelta as _td
        end_dt = _dt.strptime(trade_date, "%Y-%m-%d")
        start_dt = end_dt - _td(days=lookback_days + 30)
        start_date = start_dt.strftime("%Y-%m-%d")
        end_date = trade_date
        min_hist_rows = self.config.get("strategies", {}).get("technical", {}).get("thresholds", {}).get("hist_rows_minimum", 30)
        min_turnover_rate = self.config.get("strategies", {}).get("technical", {}).get("thresholds", {}).get("low_turnover_rate", 2.0)
        from tradingagents.agents.utils.exchange_rules import is_price_change_anomalous

        drop_reasons: Dict[str, List[str]] = {
            "no_hist_data": [],
            "insufficient_history": [],
            "low_liquidity": [],
            "extreme_price_anomaly": [],
        }

        print_interval = 25  # print every 25 stocks for user-facing progress
        for i, raw_code in enumerate(tickers):
            drop_reason = None
            data_completeness_score = 0.0
            liquidity_score = 50.0
            basic_momentum_score = 50.0

            try:
                # Format ticker
                ticker = raw_code
                if "." not in ticker:
                    if ticker.startswith(("6", "9")):
                        ticker = f"{ticker}.SH"
                    elif ticker.startswith(("0", "2", "3")):
                        ticker = f"{ticker}.SZ"

                # Check 1: History data availability
                hist = data_access.fetch_hist(ticker, start_date, end_date, adjust="qfq")
                if hist is None or (hasattr(hist, "empty") and hist.empty):
                    drop_reason = "no_hist_data"
                elif len(hist) < min_hist_rows:
                    drop_reason = "insufficient_history"
                else:
                    data_completeness_score = min(100.0, len(hist) / max(lookback_days, 1) * 100.0)
                    # Check 2: Basic liquidity from history data
                    # Calculate average turnover rate from recent data
                    if "turnover" in hist.columns or "turnover_rate" in hist.columns:
                        turnover_col = "turnover" if "turnover" in hist.columns else "turnover_rate"
                        recent_turnover = hist[turnover_col].tail(5).mean()
                        if not pd.isna(recent_turnover) and recent_turnover < min_turnover_rate:
                            drop_reason = "low_liquidity"
                        elif not pd.isna(recent_turnover):
                            liquidity_score = min(
                                100.0,
                                float(recent_turnover) / max(float(min_turnover_rate), 0.01) * 50.0,
                            )

                    # Check 3: Extreme price anomaly from history
                    # Look for limit up/down in recent days
                    if "pct_change" in hist.columns or "change_pct" in hist.columns:
                        pct_col = "pct_change" if "pct_change" in hist.columns else "change_pct"
                        recent_changes = hist[pct_col].tail(3)
                        mean_change = recent_changes.mean()
                        if not pd.isna(mean_change):
                            basic_momentum_score = max(0.0, min(100.0, 50.0 + float(mean_change) * 5.0))
                        name_columns = [column for column in ("name", "stock_name") if column in hist.columns]
                        is_st = bool(name_columns) and hist[name_columns[0]].astype(str).str.upper().str.contains("ST").any()
                        if any(
                            is_price_change_anomalous(change, ticker, is_st=is_st)
                            for change in recent_changes.dropna()
                        ):
                            drop_reason = "extreme_price_anomaly"

            except Exception:
                drop_reason = "no_hist_data"

            if drop_reason:
                drop_reasons[drop_reason].append(raw_code)
            else:
                stage_a_score = (
                    data_completeness_score * 0.45
                    + liquidity_score * 0.35
                    + basic_momentum_score * 0.20
                )
                passed.append(
                    StageACandidate(
                        ticker=raw_code,
                        data_completeness_score=round(data_completeness_score, 2),
                        liquidity_score=round(liquidity_score, 2),
                        basic_momentum_score=round(basic_momentum_score, 2),
                        stage_a_score=round(stage_a_score, 2),
                    )
                )

            # Print user-facing progress every 50 stocks
            if (i + 1) % print_interval == 0 or (i + 1) == total:
                print_progress_bar("Stage A", i + 1, total)

        clear_progress_line()
        console.print(f"[green][OK] Stage A done[/green]  [cyan]{len(passed)}/{total}[/cyan] passed  [red]{total - len(passed)}[/red] dropped")

        return passed, drop_reasons

    def run(
        self,
        mode: str = "MVP",
        trade_date: str | None = None,
        enable_deep_analysis: bool = True,
        persist_outputs: bool = True,
    ) -> ScreeningResult:
        import logging
        _logger = logging.getLogger(__name__)

        print_header_banner(mode, trade_date, enable_deep_analysis)

        now = datetime.now()
        trade_date = trade_date or now.strftime("%Y-%m-%d")

        passed, warnings = validate_screener_run(
            mode=mode,
            trade_date=trade_date,
            config=self._build_runtime_config(),
        )
        if not passed:
            raise RuntimeError("; ".join(warnings))

        started_at = datetime.now()
        data_access = self._build_data_access()
        capability_summary = data_access.validate_interface_assumptions(trade_date=trade_date)
        try:
            universe = build_screening_universe(mode=mode, config=self.config)
        except RuntimeError as e:
            raise RuntimeError(
                f"Universe construction failed: {e}\n"
                "Hint: Try --mode CUSTOM with --tickers <list> to skip index constituent fetching."
            )

        # P5-focus: propagate universe focus to strategy config
        if universe.metadata.get("focus_type"):
            self.config["policy_focus"] = {
                "focus_type": universe.metadata["focus_type"],
                "focus_value": universe.metadata["focus_value"],
            }

        console.print(f"[green][OK] Universe ready[/green]  [dim]{len(universe.tickers)} stocks  mode=[cyan]{mode}[/cyan]")

        # P5-3: Stage A - Light pre-screening
        stagea_universe_count = len(universe.tickers)
        stagea_deduped_count = len(dict.fromkeys(universe.tickers))
        stagea_max = self.config.get("stagea_max_input", stagea_deduped_count)
        stagea_input_tickers = self._prepare_stagea_input(universe.tickers, stagea_max)
        stagea_input_count = len(stagea_input_tickers)
        print_stage_header("Stage A", f"light pre-screening of {stagea_input_count} stocks")
        stagea_candidates, stagea_drop_reasons = self._run_stage_a(
            stagea_input_tickers, trade_date, data_access
        )
        stagea_pass_count = len(stagea_candidates)
        stagea_drop_count = stagea_input_count - stagea_pass_count

        _logger.info(
            f"[Screener] Stage A complete: {stagea_pass_count}/{stagea_input_count} passed "
            f"(dropped {stagea_drop_count})"
        )

        # B-8.1: apply stageb_max_input truncation before Stage B
        stageb_max = self.config.get("stageb_max_input", 1000)
        stageb_candidates = self._select_stageb_candidates(stagea_candidates, stageb_max)
        if len(stagea_candidates) > len(stageb_candidates):
            _logger.info(
                f"[Screener] Stage B score limit applied: "
                f"{len(stagea_candidates)} -> {len(stageb_candidates)}"
            )
        stagea_pass_tickers = [candidate.ticker for candidate in stageb_candidates]

        print_stage_header("Stage B", f"running strategies on {len(stagea_pass_tickers)} stocks")

        technical_strategy, policy_strategy, smart_money_strategy = self._build_strategies(data_access)
        console.print("[dim]  Running TechnicalStrategy...[/dim]", end="\r")
        technical_outcome = technical_strategy.run(stagea_pass_tickers, trade_date)
        console.print(f"[green]  [OK] TechnicalStrategy[/green]  [cyan]{len(technical_outcome.cards)}[/cyan] cards  ", end="\r")

        console.print("[dim]  Running PolicyStrategy...[/dim]", end="\r")
        policy_outcome = policy_strategy.run(stagea_pass_tickers, trade_date)
        console.print(f"[green]  [OK] PolicyStrategy[/green]  [cyan]{len(policy_outcome.cards)}[/cyan] cards  ", end="\r")

        console.print("[dim]  Running SmartMoneyStrategy...[/dim]", end="\r")
        smart_money_outcome = smart_money_strategy.run(stagea_pass_tickers, trade_date)
        console.print()
        console.print(f"[green][OK] Stage B done[/green]  Technical=[cyan]{len(technical_outcome.cards)}[/cyan]  Policy=[cyan]{len(policy_outcome.cards)}[/cyan]  SmartMoney=[cyan]{len(smart_money_outcome.cards)}[/cyan]")

        merged_candidates, dropped_candidates = merge_signal_cards(
            technical_outcome.cards + policy_outcome.cards + smart_money_outcome.cards,
            mode=mode,
            config=self.config,
        )

        deep_results = []
        if enable_deep_analysis and merged_candidates:
            print_stage_header("Stage DeepAnalysis", f"deep analysis of {len(merged_candidates)} candidates")
            deep_analyzer = self._build_deep_analyzer()
            deep_results = deep_analyzer.analyze_top_candidates(merged_candidates, trade_date)
        elif enable_deep_analysis and not merged_candidates:
            console.print("[yellow]  DeepAnalysis skipped (no candidates)[/yellow]")

        completed_at = datetime.now()

        # P5-3: Stage A audit info
        stagea_audit = {
            "stagea_universe_count": stagea_universe_count,
            "stagea_deduped_count": stagea_deduped_count,
            "stagea_input_budget": max(0, int(stagea_max)),
            "stagea_input_count": stagea_input_count,
            "stagea_budget_truncated_count": stagea_deduped_count - stagea_input_count,
            "stagea_pass_count": stagea_pass_count,
            "stagea_drop_count": stagea_drop_count,
            "stagea_drop_breakdown": _summarize_drop_reasons(stagea_drop_reasons),
            "stageb_input_budget": max(0, int(stageb_max)),
            "stageb_input_count": len(stageb_candidates),
            "stageb_selection_basis": "stage_a_score_desc_then_ticker_asc",
            "stageb_selected_score_range": {
                "highest": stageb_candidates[0].stage_a_score if stageb_candidates else None,
                "lowest": stageb_candidates[-1].stage_a_score if stageb_candidates else None,
            },
            "stagea_enabled": True,
        }

        metrics = ScreenerMetrics(
            run_id=str(uuid4()),
            mode=mode,
            universe_size=len(universe.tickers),
            strategy_a_candidates=len(technical_outcome.cards),
            strategy_b_candidates=len(policy_outcome.cards),
            strategy_c_candidates=len(smart_money_outcome.cards),
            final_candidates=len(merged_candidates),
            api_requests_total=capability_summary.get("request_stats", {}).get("total_requests", 0),
            api_requests_failed=capability_summary.get("request_stats", {}).get("failed_requests", 0),
            degraded_strategies=[
                name
                for name, outcome in {
                    "technical": technical_outcome,
                    "policy": policy_outcome,
                    "smart_money": smart_money_outcome,
                }.items()
                if outcome.status != "ready"
            ],
            elapsed_seconds_total=(completed_at - started_at).total_seconds(),
            llm_calls_total=len(deep_results) if deep_results else 0,
            # A5: build threshold snapshots from config + per-strategy snapshots
            threshold_snapshot={
                "strategies": {
                    "technical": _extract_strategy_thresholds(technical_outcome.cards),
                    "policy": _extract_strategy_thresholds(policy_outcome.cards),
                    "smart_money": _extract_strategy_thresholds(smart_money_outcome.cards),
                },
                "hard_filters": dict(SCREENER_THRESHOLDS),
                "config_vendors": self.config.get("vendors", {}),
                "run_mode": mode,
            },
            conflict_priority_snapshot=dict(SCREENER_CONFIG.get("conflict_priority", {})),
            merger_threshold_snapshot=dict(SCREENER_CONFIG.get("merger_thresholds", {})),
            effective_config_used={
                "mode": mode,
                "conflict_priority_source": "SCREENER_CONFIG",
                "merger_thresholds_source": "SCREENER_CONFIG",
                "threshold_source": "SCREENER_CONFIG",
                # P5-3: Stage A audit trail
                "stagea_audit": stagea_audit,
            },
        )

        result = ScreeningResult(
            run_id=metrics.run_id,
            mode=mode,
            trade_date=trade_date,
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            universe_size=len(universe.tickers),
            universe_metadata=universe.metadata,
            candidates=merged_candidates,
            dropped_candidates=dropped_candidates,
            strategy_status={
                "technical": technical_outcome.status,
                "policy": policy_outcome.status,
                "smart_money": smart_money_outcome.status,
            },
            data_issues=list(warnings) + list(capability_summary.get("warnings", [])),
            metrics=metrics.model_dump(),
        )

        from tradingagents.screener.name_resolver import NameResolver

        resolver = NameResolver(data_access=data_access, trade_date=trade_date)
        resolver.load()

        def _strip_suffix(code: str) -> str:
            """Strip exchange suffix (e.g. '.SH', '.SZ') to get raw 6-digit code."""
            if "." in code:
                code = code.split(".")[0]
            return code

        def _inject_name(card):
            card.company_name = resolver.resolve(card.raw_code)
            return card

        print_stage_header("Stage Names", f"resolving company names for {len(merged_candidates)} candidates")
        for card in merged_candidates:
            _inject_name(card)
        for item in dropped_candidates:
            if isinstance(item, dict):
                ticker = item.get("ticker", "")
                raw_code = item.get("raw_code") or _strip_suffix(ticker)
                item["company_name"] = resolver.resolve(raw_code)

        result.metrics["name_resolver_source"] = resolver.source
        result.metrics["name_resolver_warnings"] = resolver.warnings

        result.metrics["capability_summary"] = capability_summary
        result.metrics["universe_summary"] = universe.metadata
        result.metrics["dropped_candidates_count"] = len(dropped_candidates)
        # A5: build semantic_home_chain directly inline (single source of truth)
        semantic_home_chain: Dict[str, Any] = {}
        for result_item in deep_results:
            ticker = result_item.signal_card.ticker
            summary = result_item.final_state_summary or {}
            audit = dict(summary.get("semantic_trigger_audit", {}) or {})
            profile = dict(summary.get("semantic_execution_profile", {}) or {})
            semantic_home_chain[ticker] = {
                "trigger": list(audit.get("semantic_trigger_reasons", []) or []),
                "route": dict(summary.get("route_decision", {}) or {}),
                "execution": {
                    "route_behavior_tag": profile.get("route_behavior_tag", ""),
                    "response_style": profile.get("response_style", ""),
                    "conclusion_mode": profile.get("conclusion_mode", ""),
                    "evidence_must_include": list(profile.get("evidence_must_include", []) or []),
                },
                "decision": result_item.final_decision or "",
            }
        result.metrics["semantic_home_chain"] = semantic_home_chain
        if persist_outputs:
            result.metrics["artifacts"] = write_run_artifacts(result, deep_results, self.config)

        result.data_issues.extend(check_data_consistency(result))

        elapsed = (datetime.now() - started_at).total_seconds()
        print_completion_banner(len(merged_candidates), len(deep_results), elapsed)

        return result
