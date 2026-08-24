from __future__ import annotations

import logging
import queue
import threading
import time
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


def _bounded_call(label, fn, timeout_seconds: float, default=None):
    """Run a vendor boundary with a wall-clock budget on every platform."""
    result_queue: queue.Queue = queue.Queue(maxsize=1)

    def worker():
        try:
            result_queue.put((True, fn()), block=False)
        except Exception as exc:
            result_queue.put((False, exc), block=False)

    thread = threading.Thread(
        target=worker, name=f"policy-vendor-{label}", daemon=True
    )
    thread.start()
    thread.join(max(0.01, float(timeout_seconds)))
    if thread.is_alive():
        return default, f"[WARN] {label} timeout after {timeout_seconds:.2f}s; degraded"
    try:
        ok, value = result_queue.get_nowait()
    except queue.Empty:
        return default, f"[WARN] {label} returned no result; degraded"
    if ok:
        return value, ""
    return default, f"[WARN] {label} failed: {value}; degraded"


@dataclass
class StrategyOutcome:
    cards: List[SignalCard]
    status: str
    warnings: List[str]


POLICY_KEYWORDS = {
    "人工智能": ["人工智能", "AI", "算力", "大模型"],
    "半导体": ["半导体", "芯片", "集成电路"],
    "机器人": ["机器人", "自动化", "智能制造"],
    "新能源": ["新能源", "光伏", "储能", "电池"],
    "低空经济": ["低空", "无人机", "通航"],
}

# P5-focus: mapping from universe focus_value to THS concept name aliases
# Used when news_df matching fails but universe has a focus (FOCUSED mode)
_FOCUS_ALIAS_KEYWORDS: Dict[str, List[str]] = {
    "semiconductor": ["半导体", "芯片", "集成电路", "集成电路制造", "半导体设备"],
    "new_energy": ["新能源", "光伏", "储能", "电池", "新能源汽车"],
    "AI": ["人工智能", "AI", "大模型", "算力", "AI芯片"],
    "robot": ["机器人", "自动化", "智能制造", "人形机器人"],
    "low_altitude": ["低空", "无人机", "通航", "eVTOL"],
}

class PolicyStrategy:
    def __init__(self, data_access, config: Dict[str, Any] | None = None):
        self.data_access = data_access
        self.config = config or {}

    def run(self, universe: List[str], trade_date: str) -> StrategyOutcome:
        console.print(f"[cyan]>> PolicyStrategy[/cyan]  [dim]{len(universe)} stocks...", end="\r")

        policy_config = self.config.get("strategies", {}).get("policy", {})
        th = policy_config.get("thresholds", {})
        concept_conviction_low = float(th.get("concept_conviction_low", 52.0))
        max_concepts = int(policy_config.get("max_concepts", 5))
        max_stocks_per_concept = int(policy_config.get("max_stocks_per_concept", 5))
        request_timeout = float(policy_config.get("request_timeout_seconds", 20.0))
        stage_timeout = float(policy_config.get("stage_timeout_seconds", 120.0))
        stage_deadline = time.monotonic() + max(1.0, stage_timeout)
        runtime_warnings: List[str] = []

        def call_vendor(label, fn, default=None):
            remaining = stage_deadline - time.monotonic()
            if remaining <= 0:
                runtime_warnings.append(
                    f"[WARN] PolicyStrategy stage timeout ({stage_timeout:.2f}s); skipped {label}"
                )
                return default
            console.print(f"[dim]  Policy heartbeat: {label}...[/dim]", end="\r")
            value, warning = _bounded_call(
                label, fn, min(request_timeout, remaining), default
            )
            if warning:
                runtime_warnings.append(warning)
                _logger.warning(warning)
            return value

        capability = call_vendor(
            "validate_interface_assumptions",
            lambda: self.data_access.validate_interface_assumptions(
                trade_date=trade_date
            ),
            default={
                "warnings": ["[WARN] capability probe unavailable; policy degraded"],
                "strategy_capabilities": {"policy": {"status_hint": "degraded"}},
                "concept_list_verified": False,
                "freshness": [],
            },
        )

        # A2: build full threshold_snapshot from config for output audit
        threshold_snapshot = {k: v for k, v in th.items()}
        threshold_snapshot["source"] = "policy"
        threshold_snapshot["effective_values"] = {
            "concept_conviction_low": concept_conviction_low,
            "max_concepts": max_concepts,
            "max_stocks_per_concept": max_stocks_per_concept,
        }
        cards: List[SignalCard] = []
        strategy_capability = capability.get("strategy_capabilities", {}).get("policy", {})
        concept_verified = bool(capability.get("concept_list_verified", False))
        concept_primary = strategy_capability.get("primary_dependencies", {}).get(
            "concept_list",
            capability.get("concept_primary_vendor", "ths"),
        )
        concept_fallback = strategy_capability.get("primary_dependencies", {}).get(
            "concept_fallback",
            capability.get("concept_list_fallback_vendor", ""),
        )
        news_auxiliary = strategy_capability.get("primary_dependencies", {}).get(
            "news_auxiliary",
            "baidu",
        )

        # Phase4: Load index constituents cache for concept_weight scoring
        # One-time load at startup (~1-2s), O(1) lookup per stock thereafter
        self._hs300_members: set = set()
        self._csi500_members: set = set()
        self._cy50_members: set = set()

        for _index_code, _cache_attr, _name_zh in [
            ("000300", "_hs300_members", "沪深300"),
            ("000905", "_csi500_members", "中证500"),
            ("399006", "_cy50_members", "创业板指"),
        ]:
            try:
                df = call_vendor(
                    f"index_constituents:{_index_code}",
                    lambda code=_index_code: self.data_access.fetch_index_constituents(code),
                )
                if df is not None and not getattr(df, "empty", True):
                    cols = list(df.columns)
                    code_col = next((c for c in cols if "成分券代码" in str(c) or str(c).lower() in ("code", "symbol")), None)
                    if code_col:
                        codes = df[code_col].astype(str).str.zfill(6).tolist()
                        setattr(self, _cache_attr, set(codes))
                        console.print(f"[dim]  Loaded {len(codes)} stocks for {_name_zh}...[/dim]", end="\r")
            except Exception:
                pass

        concept_df = (
            call_vendor("concept_boards", self.data_access.fetch_concept_boards)
            if concept_verified and hasattr(self.data_access, "fetch_concept_boards")
            else None
        )
        news_df = (
            call_vendor(
                "policy_news_baidu",
                lambda: self.data_access.fetch_policy_news_baidu(
                    trade_date, look_back_days=7, limit=24
                ),
            )
            if hasattr(self.data_access, "fetch_policy_news_baidu")
            else None
        )
        policy_focus = self.config.get("policy_focus")
        selected_concepts, keyword_mode, selection_mode = self._select_policy_concepts(
            concept_df,
            news_df,
            policy_focus,
        )
        # H6 OPTIMIZATION: respect max_concepts budget cap
        selected_concepts = selected_concepts[:max_concepts]
        degraded_reason = self._build_degradation_reason(concept_verified, bool(selected_concepts), keyword_mode)
        # H6 OPTIMIZATION: single batch fetch of all concept constituents upfront (O(m) API calls)
        # Instead of per-stock per-concept fetching. Universe loop below only does O(1) dict lookups.
        console.print(f"[cyan]  Loading concept constituents[/cyan]  [dim]{len(selected_concepts)} concepts...[/dim]", end="\r")
        concept_constituents = call_vendor(
            "concept_constituents",
            lambda: self._load_concept_constituents(
                selected_concepts, max_stocks_per_concept
            ),
            default={},
        )
        universe_codes = {code.zfill(6) for code in universe}
        # H6 OPTIMIZATION: pre-compute universe hits once (O(n+m) set operations)
        universe_hits = self._build_universe_concept_hits(concept_constituents, universe_codes)
        # H6 OPTIMIZATION: pre-compute all concept profiles once (no per-stock computation needed)
        concept_profiles = self._build_concept_profiles(
            selected_concepts=selected_concepts,
            concept_constituents=concept_constituents,
            universe_hits=universe_hits,
            news_df=news_df,
        )

        total = len(universe)
        log_interval = max(1, total // 10) if total > 0 else 1
        _logger.info(f"[Policy] Starting analysis for {total} stocks...")

        console.print(f"[cyan]  Policy scoring[/cyan]  [dim]{total} stocks...[/dim]", end="\r")

        for idx, raw_code in enumerate(universe):
            ticker = format_ticker(raw_code)
            mapped_concept = self._pick_best_concept_for_code(
                raw_code=raw_code,
                selected_concepts=selected_concepts,
                universe_hits=universe_hits,
                concept_profiles=concept_profiles,
                fallback_index=idx,
            )
            member_metrics = self._compute_member_rank_metrics(
                raw_code=raw_code,
                concept_name=mapped_concept,
                concept_constituents=concept_constituents,
            )
            concept_heat = self._concept_heat_score(mapped_concept, news_df)
            stock_strength_score = self._compute_stock_strength_score(
                ticker=ticker,
                raw_code=raw_code,
                concept_name=mapped_concept,
                concept_constituents=concept_constituents,
                fallback_rank=idx,
            )
            relative_rank_score = self._compute_relative_rank_score(
                raw_code=raw_code,
                concept_name=mapped_concept,
                concept_constituents=concept_constituents,
            )
            board_leadership_score = self._compute_board_leadership_score(
                concept_name=mapped_concept,
                member_metrics=member_metrics,
                concept_profiles=concept_profiles,
            )
            multi_concept_overlap_count = self._compute_multi_concept_overlap_count(
                raw_code=raw_code,
                selected_concepts=selected_concepts,
                concept_constituents=concept_constituents,
            )
            concept_competition_score = self._compute_concept_competition_score(
                concept_name=mapped_concept,
                concept_profiles=concept_profiles,
                multi_concept_overlap_count=multi_concept_overlap_count,
            )
            concept_conviction_score = self._compute_concept_conviction_score(
                board_leadership_score=board_leadership_score,
                concept_competition_score=concept_competition_score,
                primary_concept_score=concept_profiles.get(mapped_concept, {}).get("primary_concept_score", 42.0),
                source_quality_score=75.0 if news_df is not None and not getattr(news_df, "empty", True) else 45.0,
                cross_hit_score=85.0 if raw_code.zfill(6) in universe_hits.get(mapped_concept, set()) else 40.0,
            )
            primary_concept_score = concept_profiles.get(mapped_concept, {}).get("primary_concept_score", 42.0)
            primary_concept_selection_summary = self._build_primary_concept_selection_summary(
                concept_name=mapped_concept,
                concept_profiles=concept_profiles,
                member_metrics=member_metrics,
                multi_concept_overlap_count=multi_concept_overlap_count,
            )
            cross_hit_score = 85.0 if raw_code.zfill(6) in universe_hits.get(mapped_concept, set()) else 40.0
            source_quality_score = 75.0 if news_df is not None and not getattr(news_df, "empty", True) else 45.0
            liquidity_score = max(40.0, 68.0 - idx * 2.0)
            concept_breadth_score = concept_profiles.get(mapped_concept, {}).get("concept_breadth_score", 42.0)
            stock_selection_tag = self._build_stock_selection_tag(
                member_metrics,
                cross_hit_score,
                keyword_mode,
                selection_mode,
            )
            concept_weight_bucket = self._build_concept_weight_bucket(
                raw_code=raw_code,
                is_member=member_metrics.get("is_member", False),
                top_tier_hit=member_metrics.get("top_tier_hit", False),
                hs300=self._hs300_members,
                csi500=self._csi500_members,
                cy50=self._cy50_members,
            )
            score = round(
                min(
                    100.0,
                    0.22 * concept_heat
                    + 0.22 * stock_strength_score
                    + 0.18 * relative_rank_score
                    + 0.16 * board_leadership_score
                    + 0.10 * cross_hit_score
                    + 0.05 * concept_competition_score
                    + 0.05 * primary_concept_score
                    + 0.04 * source_quality_score
                    + 0.03 * concept_breadth_score
                    + 0.02 * liquidity_score,
                ),
                2,
            )
            degraded = not concept_verified or not selected_concepts
            evidence = SignalEvidence(
                strategy="policy",
                score=score,
                rank_in_strategy=idx + 1,
                reason="Policy/news-driven concept mapping with keyword fallback",
                raw_metrics={
                    "score_family": "policy_concept_board_v1",
                    "concept_heat": concept_heat,
                    "stock_strength_score": stock_strength_score,
                    "relative_rank_score": relative_rank_score,
                    "board_leadership_score": board_leadership_score,
                    "concept_competition_score": concept_competition_score,
                    "concept_conviction_score": concept_conviction_score,
                    "primary_concept_score": primary_concept_score,
                    "cross_hit_score": cross_hit_score,
                    "source_quality_score": source_quality_score,
                    "liquidity_score": liquidity_score,
                    "concept_breadth_score": concept_breadth_score,
                    "selected_concept": mapped_concept,
                    "primary_concept_selection_summary": primary_concept_selection_summary,
                    "stock_selection_tag": stock_selection_tag,
                    "concept_weight_bucket": concept_weight_bucket,
                    "multi_concept_overlap_count": multi_concept_overlap_count,
                    "concept_rank_position": member_metrics["rank_position"],
                    "top_tier_hit": member_metrics["top_tier_hit"],
                    "is_concept_member": member_metrics["is_member"],
                    "member_strength_composite": member_metrics["member_strength_composite"],
                    "keyword_fallback_used": keyword_mode,
                    "universe_cross_hit": raw_code.zfill(6) in universe_hits.get(mapped_concept, set()),
                    "news_sources_used": [news_auxiliary] if news_df is not None else [],
                    "concept_primary_vendor": concept_primary,
                    "concept_fallback_vendor": concept_fallback or "none",
                    "concept_count": 0 if concept_df is None else len(concept_df),
                    "news_event_count": 0 if news_df is None else len(news_df),
                    "concept_constituent_count": len(concept_constituents.get(mapped_concept, [])),
                    "strategy_status_hint": strategy_capability.get("status_hint", "degraded"),
                    "production_rule_version": "policy_pg_v3",
                    # A2: store the full config-driven threshold_snapshot, not just concept_conviction_low
                    "threshold_snapshot": threshold_snapshot,
                    "concept_linkage_boundary": self._build_concept_linkage_boundary(
                        concept_verified=concept_verified,
                        keyword_mode=keyword_mode,
                        concept_constituent_count=len(concept_constituents.get(mapped_concept, [])),
                        universe_cross_hit=raw_code.zfill(6) in universe_hits.get(mapped_concept, set()),
                        concept_primary=concept_primary,
                        concept_fallback=concept_fallback or "none",
                        news_auxiliary=news_auxiliary,
                    ),
                    "degraded_context": {
                        "concept_verified": concept_verified,
                        "selected_concepts_count": len(selected_concepts),
                        "keyword_mode": keyword_mode,
                        "news_available": news_df is not None and not getattr(news_df, "empty", True),
                    },
                    "vendor_trace": {
                        "concept_primary_vendor": concept_primary,
                        "concept_fallback_vendor": concept_fallback or "none",
                        "news_auxiliary_vendor": news_auxiliary,
                    },
                },
                freshness=capability.get("freshness", []),
                degraded=degraded,
                degradation_reason=degraded_reason,
            )
            cards.append(
                SignalCard(
                    ticker=ticker,
                    raw_code=raw_code,
                    exchange=score_to_exchange(raw_code),
                    company_name=placeholder_name(raw_code),
                    trade_date=trade_date,
                    sector_tags=["policy_driven", stock_selection_tag],
                    concept_tags=[mapped_concept, stock_selection_tag, concept_weight_bucket],
                    strategy_sources=["policy"],
                    signal_breakdown=[evidence],
                    trigger_reason=self._build_trigger_reason(
                        keyword_mode=keyword_mode,
                        stock_selection_tag=stock_selection_tag,
                        concept_weight_bucket=concept_weight_bucket,
                        selection_mode=selection_mode,
                    ),
                    initial_confidence=min(94.0, score + (4.0 if concept_verified else 0.0)),
                    risk_flags=self._build_risk_flags(
                        concept_verified=concept_verified,
                        keyword_mode=keyword_mode,
                        news_df=news_df,
                        member_metrics=member_metrics,
                        stock_selection_tag=stock_selection_tag,
                        concept_weight_bucket=concept_weight_bucket,
                        concept_conviction_score=concept_conviction_score,
                        concept_conviction_low=concept_conviction_low,
                    ),
                    screening_score=score,
                    data_source_verified=concept_verified and bool(selected_concepts),
                    evidence_snapshot={
                        "capability_summary": capability,
                        "strategy_capability": strategy_capability,
                        "strategy": "policy",
                        "concept_linkage_boundary": self._build_concept_linkage_boundary(
                            concept_verified=concept_verified,
                            keyword_mode=keyword_mode,
                            concept_constituent_count=len(concept_constituents.get(mapped_concept, [])),
                            universe_cross_hit=raw_code.zfill(6) in universe_hits.get(mapped_concept, set()),
                            concept_primary=concept_primary,
                            concept_fallback=concept_fallback or "none",
                            news_auxiliary=news_auxiliary,
                        ),
                        "selected_concepts": selected_concepts,
                        "concept_profiles": concept_profiles,
                        "universe_hits": {key: sorted(value) for key, value in universe_hits.items()},
                        "concept_constituents_preview": {
                            key: value[:3] for key, value in concept_constituents.items()
                        },
                        "primary_concept_selection_summary": primary_concept_selection_summary,
                        # A2: full threshold audit trail
                        "threshold_snapshot": threshold_snapshot,
                    },
                )
            )

            # Progress log at ~50-stock intervals
            if (idx + 1) % 50 == 0 or (idx + 1) == total:
                print_progress_bar("Policy scoring", idx + 1, total)

        clear_progress_line()
        console.print(f"[cyan]  Policy:[/cyan] [dim]sorting {len(cards)} cards...[/dim]", end="\r")

        _logger.info(f"[Policy] Analysis done: {len(cards)} cards from {total} stocks")
        cards.sort(key=lambda card: card.screening_score, reverse=True)
        warnings = list(capability.get("warnings", [])) + runtime_warnings
        if not concept_verified:
            warnings.append("[WARN] concept list validation not completed; policy strategy runs in degraded mode")
        status = (
            "ready"
            if cards and strategy_capability.get("status_hint") == "ready" and concept_verified and bool(selected_concepts)
            else "degraded"
        )
        console.print(f"[green][OK] PolicyStrategy done[/green]  [cyan]{len(cards)}[/cyan] cards  [dim]status={status}[/dim]")
        return StrategyOutcome(cards=cards, status=status, warnings=warnings)

    @staticmethod
    def _select_policy_concepts(
        concept_df: Any,
        news_df: Any,
        policy_focus: Dict[str, str] | None = None,
    ) -> tuple[list[str], bool, str]:
        """Select policy concepts from THS concept list.

        Returns:
            selected_concepts: list of concept names
            keyword_mode: bool — True if relying on keyword/fallback matching (reduces scores)
            selection_mode: str — "news_matched" | "focus_aligned" | "keyword_fallback"
        """
        if concept_df is None or getattr(concept_df, "empty", True):
            return [], True, "keyword_fallback"

        concept_names = concept_df["name"].astype(str).tolist() if "name" in concept_df.columns else []
        if not concept_names:
            return [], True, "keyword_fallback"

        # Step A: news_df 无数据（None/empty）→ 无法判断，返回 THS 前5 + keyword_mode=True
        if news_df is None or getattr(news_df, "empty", True):
            return concept_names[:5], True, "keyword_fallback"

        # Step B: news_df 有内容，尝试精确匹配
        text_columns = [col for col in news_df.columns if str(col) in {"事件", "内容", "标题", "event"}]
        joined = " ".join(
            str(value)
            for col in text_columns
            for value in news_df[col].astype(str).tolist()
        )
        matched = [name for name in concept_names if name in joined]
        if matched:
            return matched[:5], False, "news_matched"

        # Step C: POLICY_KEYWORDS 匹配（原有逻辑）
        keyword_concepts: List[str] = []
        for concept_name, keywords in POLICY_KEYWORDS.items():
            if any(keyword in joined for keyword in keywords):
                keyword_concepts.append(concept_name)

        keyword_fallback = [n for n in concept_names if any(seed in n for seed in keyword_concepts)]
        if keyword_fallback:
            return keyword_fallback[:5], True, "keyword_fallback"

        # Step D: news 匹配失败但存在 focus → 用 focus 语义匹配（新增）
        if policy_focus and policy_focus.get("focus_value"):
            focus_value = policy_focus["focus_value"].lower()
            focus_aliases = _FOCUS_ALIAS_KEYWORDS.get(focus_value, [])
            if not focus_aliases:
                focus_aliases = [policy_focus["focus_value"]]

            matched = [
                name for name in concept_names
                if any(alias in name for alias in focus_aliases)
            ]
            if matched:
                return matched[:5], True, "focus_aligned"

        # Step E: 完全兜底（原有行为，保留）
        return concept_names[:5], True, "keyword_fallback"

    @staticmethod
    def _concept_heat_score(concept_name: str, news_df: Any) -> float:
        if news_df is None or getattr(news_df, "empty", True):
            return 45.0
        text = " ".join(str(value) for value in news_df.astype(str).values.flatten().tolist())
        hits = text.count(concept_name)
        if hits == 0:
            for _, keywords in POLICY_KEYWORDS.items():
                hits += sum(text.count(keyword) for keyword in keywords if keyword in concept_name or concept_name in keyword)
        return round(min(100.0, 50.0 + hits * 8.0), 2)

    @staticmethod
    def _build_universe_concept_hits(
        concept_constituents: Dict[str, List[Dict[str, Any]]],
        universe_codes: set[str],
    ) -> Dict[str, set[str]]:
        hits: Dict[str, set[str]] = {}
        for concept_name, rows in concept_constituents.items():
            codes = {row.get("code", "") for row in rows if row.get("code")}
            hits[concept_name] = codes & universe_codes
        return hits

    @staticmethod
    def _pick_best_concept_for_code(
        raw_code: str,
        selected_concepts: List[str],
        universe_hits: Dict[str, set[str]],
        concept_profiles: Dict[str, Dict[str, Any]],
        fallback_index: int,
    ) -> str:
        code = raw_code.zfill(6)
        matched: List[str] = []
        for concept_name in selected_concepts:
            if code in universe_hits.get(concept_name, set()):
                matched.append(concept_name)
        if matched:
            ranked = sorted(
                matched,
                key=lambda name: (
                    concept_profiles.get(name, {}).get("top_selection_score", 0.0),
                    concept_profiles.get(name, {}).get("concept_heat", 0.0),
                ),
                reverse=True,
            )
            return ranked[0]
        if not selected_concepts:
            return "policy_fallback"
        return selected_concepts[fallback_index % len(selected_concepts)]

    def _load_concept_constituents(
        self,
        selected_concepts: List[str],
        max_stocks_per_concept: int = 20,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Load constituent stocks for each selected concept.

        H6 OPTIMIZATION: this is called ONCE per run (not per-stock),
        fetching at most max_stocks_per_concept rows per concept board.
        All subsequent per-stock scoring uses O(1) in-memory dict lookups.
        """
        payload: Dict[str, List[Dict[str, Any]]] = {}
        if not hasattr(self.data_access, "fetch_concept_constituents"):
            return payload
        for concept_name in selected_concepts[:5]:
            try:
                df = self.data_access.fetch_concept_constituents(concept_name)
                if df is None or getattr(df, "empty", True):
                    payload[concept_name] = []
                    continue
                payload[concept_name] = self._normalize_constituent_rows(df, max_stocks_per_concept)
            except Exception:
                payload[concept_name] = []
        return payload

    @staticmethod
    def _normalize_constituent_rows(df: Any, max_stocks: int = 20) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if df is None or getattr(df, "empty", True):
            return rows
        columns = list(df.columns)
        code_col = next((col for col in columns if "代码" in str(col) or str(col).lower() == "code"), None)
        name_col = next((col for col in columns if "名称" in str(col) or str(col).lower() == "name"), None)
        change_col = next((col for col in columns if "涨跌幅" in str(col) or "change" in str(col).lower()), None)
        amount_col = next((col for col in columns if "成交额" in str(col) or "amount" in str(col).lower()), None)
        turnover_col = next((col for col in columns if "换手率" in str(col) or "turnover" in str(col).lower()), None)

        for _, row in df.head(max_stocks).iterrows():
            rows.append(
                {
                    "code": str(row[code_col]).zfill(6) if code_col is not None else "",
                    "name": str(row[name_col]) if name_col is not None else "",
                    "change_pct": PolicyStrategy._safe_float(row[change_col]) if change_col is not None else None,
                    "amount": PolicyStrategy._safe_float(row[amount_col]) if amount_col is not None else None,
                    "turnover": PolicyStrategy._safe_float(row[turnover_col]) if turnover_col is not None else None,
                }
            )
        return rows

    def _compute_top_selection_score(
        self,
        member_metrics: Dict[str, Any],
        concept_profiles: Dict[str, Any],
        concept_name: str,
        raw_code: str,
    ) -> float:
        """Compute the concept-selection score using static index membership instead of daily change rank.

        New formula (Phase4):
            score = 55.0
                    + index_tier_score   (HS300=28, CSI500/CY50=18, none=0)
                    + concept_membership  (+12 if is_member else +0)
                    + concept_breadth bonus (up to +10)
        """
        profile = concept_profiles.get(concept_name, {})

        index_tier = self._get_index_tier(
            raw_code,
            self._hs300_members,
            self._csi500_members,
            self._cy50_members,
        )
        is_member = member_metrics.get("is_member", False)
        concept_membership = 12.0 if is_member else 0.0

        score = 55.0 + index_tier + concept_membership
        score += min(10.0, profile.get("concept_breadth_score", 0.0) * 0.12)

        return round(min(100.0, max(20.0, score)), 2)

    def _compute_stock_strength_score(
        self,
        ticker: str,
        raw_code: str,
        concept_name: str,
        concept_constituents: Dict[str, List[Dict[str, Any]]],
        fallback_rank: int,
    ) -> float:
        rows = concept_constituents.get(concept_name, [])
        if not rows:
            return max(35.0, 72.0 - fallback_rank * 4.0)

        code = raw_code.zfill(6)
        matched = next((item for item in rows if item.get("code") == code), None)
        if matched is None:
            return max(38.0, 68.0 - fallback_rank * 3.0)

        change_pct = matched.get("change_pct") or 0.0
        amount = matched.get("amount") or 0.0
        turnover = matched.get("turnover") or 0.0
        score = 50.0 + change_pct * 2.5
        if amount > 5e8:
            score += 12.0
        elif amount > 1e8:
            score += 7.0
        if turnover > 5:
            score += 10.0
        elif turnover > 2:
            score += 5.0
        return round(min(100.0, max(20.0, score)), 2)

    @staticmethod
    def _compute_relative_rank_score(
        raw_code: str,
        concept_name: str,
        concept_constituents: Dict[str, List[Dict[str, Any]]],
    ) -> float:
        rows = concept_constituents.get(concept_name, [])
        if not rows:
            return 42.0
        ranked = sorted(
            rows,
            key=lambda item: (
                item.get("change_pct") if item.get("change_pct") is not None else -999.0,
                item.get("amount") if item.get("amount") is not None else -1.0,
            ),
            reverse=True,
        )
        code = raw_code.zfill(6)
        for idx, item in enumerate(ranked, 1):
            if item.get("code") == code:
                percentile = 1.0 - ((idx - 1) / max(1, len(ranked)))
                return round(35.0 + percentile * 60.0, 2)
        return 40.0

    def _compute_member_rank_metrics(
        self,
        raw_code: str,
        concept_name: str,
        concept_constituents: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        rows = concept_constituents.get(concept_name, [])
        empty = {
            "is_member": False,
            "rank_position": None,
            "top_tier_hit": False,
            "member_strength_composite": 35.0,
        }
        if not rows:
            return empty

        ranked_rows = sorted(
            rows,
            key=lambda item: self._member_composite_value(item),
            reverse=True,
        )
        code = raw_code.zfill(6)
        for idx, item in enumerate(ranked_rows, 1):
            if item.get("code") == code:
                return {
                    "is_member": True,
                    "rank_position": idx,
                    "top_tier_hit": idx <= min(3, len(ranked_rows)),
                    "member_strength_composite": round(self._member_composite_value(item), 2),
                }
        return empty

    def _compute_board_leadership_score(
        self,
        concept_name: str,
        member_metrics: Dict[str, Any],
        concept_profiles: Dict[str, Dict[str, Any]],
    ) -> float:
        profile = concept_profiles.get(concept_name, {})
        if not member_metrics.get("is_member"):
            return max(35.0, profile.get("top_selection_score", 48.0) - 18.0)

        rank_position = member_metrics.get("rank_position") or 99
        score = 55.0
        if rank_position == 1:
            score += 28.0
        elif rank_position <= 3:
            score += 20.0
        elif rank_position <= 5:
            score += 12.0
        score += min(12.0, profile.get("concept_breadth_score", 0.0) * 0.12)
        score += min(10.0, member_metrics.get("member_strength_composite", 0.0) * 0.10 - 5.0)
        return round(min(100.0, max(20.0, score)), 2)

    def _build_concept_profiles(
        self,
        selected_concepts: List[str],
        concept_constituents: Dict[str, List[Dict[str, Any]]],
        universe_hits: Dict[str, set[str]],
        news_df: Any,
    ) -> Dict[str, Dict[str, Any]]:
        profiles: Dict[str, Dict[str, Any]] = {}
        for concept_name in selected_concepts:
            rows = concept_constituents.get(concept_name, [])
            concept_heat = self._concept_heat_score(concept_name, news_df)
            hit_count = len(universe_hits.get(concept_name, set()))
            member_count = len(rows)
            avg_strength = 0.0
            if rows:
                avg_strength = sum(self._member_composite_value(item) for item in rows[:5]) / min(5, len(rows))
            concept_breadth_score = min(100.0, 38.0 + hit_count * 14.0 + min(28.0, member_count * 1.8))
            top_selection_score = min(100.0, 0.55 * concept_heat + 0.25 * avg_strength + 0.20 * concept_breadth_score)
            primary_concept_score = min(100.0, 0.50 * top_selection_score + 0.30 * concept_heat + 0.20 * concept_breadth_score)
            profiles[concept_name] = {
                "concept_heat": round(concept_heat, 2),
                "member_count": member_count,
                "universe_hit_count": hit_count,
                "concept_breadth_score": round(concept_breadth_score, 2),
                "top_selection_score": round(top_selection_score, 2),
                "primary_concept_score": round(primary_concept_score, 2),
            }
        return profiles

    @staticmethod
    def _compute_multi_concept_overlap_count(
        raw_code: str,
        selected_concepts: List[str],
        concept_constituents: Dict[str, List[Dict[str, Any]]],
    ) -> int:
        code = raw_code.zfill(6)
        hits = 0
        for concept_name in selected_concepts:
            if any(item.get("code") == code for item in concept_constituents.get(concept_name, [])):
                hits += 1
        return hits

    @staticmethod
    def _compute_concept_competition_score(
        concept_name: str,
        concept_profiles: Dict[str, Dict[str, Any]],
        multi_concept_overlap_count: int,
    ) -> float:
        profile = concept_profiles.get(concept_name, {})
        top_selection_score = profile.get("top_selection_score", 42.0)
        concept_heat = profile.get("concept_heat", 45.0)
        score = 40.0 + 0.38 * top_selection_score + 0.20 * concept_heat
        if multi_concept_overlap_count >= 2:
            score += min(12.0, (multi_concept_overlap_count - 1) * 6.0)
        return round(min(100.0, max(20.0, score)), 2)

    @staticmethod
    def _compute_concept_conviction_score(
        board_leadership_score: float,
        concept_competition_score: float,
        primary_concept_score: float,
        source_quality_score: float,
        cross_hit_score: float,
    ) -> float:
        score = (
            0.30 * board_leadership_score
            + 0.24 * concept_competition_score
            + 0.22 * primary_concept_score
            + 0.14 * source_quality_score
            + 0.10 * cross_hit_score
        )
        return round(min(100.0, max(20.0, score)), 2)

    @staticmethod
    def _build_primary_concept_selection_summary(
        concept_name: str,
        concept_profiles: Dict[str, Dict[str, Any]],
        member_metrics: Dict[str, Any],
        multi_concept_overlap_count: int,
    ) -> str:
        profile = concept_profiles.get(concept_name, {})
        rank_position = member_metrics.get("rank_position")
        member_rank = f"rank={rank_position}" if rank_position is not None else "rank=unconfirmed"
        return (
            f"{concept_name} selected as primary concept | "
            f"top_selection={profile.get('top_selection_score', 0.0)} | "
            f"heat={profile.get('concept_heat', 0.0)} | "
            f"overlap={multi_concept_overlap_count} | {member_rank}"
        )

    @staticmethod
    def _member_composite_value(item: Dict[str, Any]) -> float:
        change_pct = item.get("change_pct") or 0.0
        amount = item.get("amount") or 0.0
        turnover = item.get("turnover") or 0.0
        score = 45.0 + change_pct * 3.5
        if amount > 8e8:
            score += 18.0
        elif amount > 3e8:
            score += 10.0
        elif amount > 1e8:
            score += 5.0
        if turnover > 8:
            score += 14.0
        elif turnover > 4:
            score += 8.0
        elif turnover > 2:
            score += 4.0
        return min(100.0, max(20.0, score))

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_degradation_reason(concept_verified: bool, has_selected_concepts: bool, keyword_mode: bool) -> str:
        reasons: List[str] = []
        if not concept_verified:
            reasons.append("concept_list_unverified")
        if not has_selected_concepts:
            reasons.append("concept_mapping_empty")
        if keyword_mode:
            reasons.append("keyword_fallback")
        return ",".join(reasons)

    @staticmethod
    def _build_stock_selection_tag(
        member_metrics: Dict[str, Any],
        cross_hit_score: float,
        keyword_mode: bool,
        selection_mode: str = "keyword_fallback",
    ) -> str:
        if member_metrics.get("top_tier_hit"):
            return "policy_top_stock"
        if member_metrics.get("is_member"):
            return "policy_core_member"
        if cross_hit_score >= 80 and not keyword_mode:
            return "policy_cross_hit_candidate"
        # P5-focus: focus_aligned but not a THS member → better than pure keyword fallback
        if selection_mode == "focus_aligned":
            return "policy_focus_aligned"
        return "policy_keyword_fallback"

    @staticmethod
    def _build_trigger_reason(
        keyword_mode: bool,
        stock_selection_tag: str,
        concept_weight_bucket: str,
        selection_mode: str = "keyword_fallback",
    ) -> str:
        """Build the trigger reason string for a signal card.

        Phase4 + P5-focus logic:
            policy_top_stock              -> policy_concept_top_pick
            concept_weight_core/quality    -> policy_concept_core_member
            policy_focus_aligned          -> policy_event_focus_aligned
            keyword_mode                  -> policy_event_keyword_fallback
            otherwise                     -> policy_event_concept_map
        """
        if stock_selection_tag == "policy_top_stock":
            return "policy_concept_top_pick"
        if concept_weight_bucket in ("concept_weight_core", "concept_weight_quality"):
            return "policy_concept_core_member"
        # P5-focus: distinguish focus_aligned from pure keyword fallback
        if stock_selection_tag == "policy_focus_aligned":
            return "policy_event_focus_aligned"
        if keyword_mode:
            return "policy_event_keyword_fallback"
        return "policy_event_concept_map"

    @staticmethod
    def _build_concept_weight_bucket(raw_code: str, is_member: bool, top_tier_hit: bool, hs300: set, csi500: set, cy50: set) -> str:
        """Determine the concept weight bucket for a stock based on index membership + THS confirmation.

        New Phase4 label system (replaces board_rank_bucket):
            HS300 member + THS member   -> concept_weight_core       (板块核心资产)
            CSI500/CY50 member + THS    -> concept_weight_quality    (优质标的)
            THS member only (no index)  -> concept_weight_secondary  (概念成员)
            Not in THS or any index     -> concept_weight_unconfirmed (未确认)
        """
        if top_tier_hit:
            return "concept_weight_core"
        if is_member:
            code = str(raw_code).zfill(6)
            if code in hs300:
                return "concept_weight_core"
            if code in csi500 or code in cy50:
                return "concept_weight_quality"
            return "concept_weight_secondary"
        return "concept_weight_unconfirmed"

    @staticmethod
    def _get_index_tier(raw_code: str, hs300: set, csi500: set, cy50: set) -> int:
        """Return the index tier score for a stock based on index constituent membership.

        Scores:
            HS300 member  -> 28  (core blue chip, most representative A-share)
            CSI500 member -> 18  (quality mid-cap, strong growth)
            CY50 member   -> 18  (tech growth leader)
            None          ->  0  (not in any tracked index)
        """
        code = raw_code.zfill(6)
        if code in hs300:
            return 28
        if code in csi500 or code in cy50:
            return 18
        return 0

    @staticmethod
    def _build_concept_linkage_boundary(
        concept_verified: bool,
        keyword_mode: bool,
        concept_constituent_count: int,
        universe_cross_hit: bool,
        concept_primary: str,
        concept_fallback: str,
        news_auxiliary: str,
    ) -> Dict[str, Any]:
        linkage_mode = "verified_constituent_cross_hit"
        confidence_tier = "high"
        if not concept_verified:
            linkage_mode = "unverified_concept_source"
            confidence_tier = "low"
        elif keyword_mode:
            linkage_mode = "keyword_fallback_mapping"
            confidence_tier = "low"
        elif concept_constituent_count <= 0:
            linkage_mode = "concept_without_constituents"
            confidence_tier = "low"
        elif not universe_cross_hit:
            linkage_mode = "concept_match_without_cross_hit"
            confidence_tier = "medium"

        return {
            "linkage_mode": linkage_mode,
            "confidence_tier": confidence_tier,
            "concept_primary_vendor": concept_primary,
            "concept_fallback_vendor": concept_fallback,
            "news_auxiliary_vendor": news_auxiliary,
            "constituent_cross_hit": universe_cross_hit,
            "constituent_count": concept_constituent_count,
        }

    @staticmethod
    def _build_risk_flags(
        concept_verified: bool,
        keyword_mode: bool,
        news_df: Any,
        member_metrics: Dict[str, Any],
        stock_selection_tag: str,
        concept_weight_bucket: str,
        concept_conviction_score: float,
        concept_conviction_low: float,
    ) -> List[str]:
        flags = []
        if not concept_verified:
            flags.append("concept_primary_unavailable")
        if keyword_mode:
            flags.append("keyword_fallback_active")
        if news_df is None or getattr(news_df, "empty", True):
            flags.append("policy_news_unavailable")
        if not member_metrics.get("is_member"):
            flags.append("concept_member_unconfirmed")
        elif not member_metrics.get("top_tier_hit"):
            flags.append("non_top_concept_member")
        if concept_weight_bucket == "concept_weight_secondary":
            flags.append("board_tail_member")
        if concept_weight_bucket == "concept_weight_unconfirmed":
            flags.append("concept_weight_unconfirmed")
        if stock_selection_tag == "policy_keyword_fallback":
            flags.append("policy_selection_confidence_low")
        if concept_conviction_score <= concept_conviction_low:
            flags.append("concept_conviction_low")
        return flags
