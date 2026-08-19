"""ScreenerDataAccess — thin facade over the split data-access layers.

Since the Phase 4 split this module only owns:
- configuration (DEFAULT_VENDORS + per-instance overrides),
- the public fetch API (vendor fallback orchestration + the hist cache),
- the probe-cache lifecycle on top of ``capability.py``.

The implementations live in:
- ``vendors/``          per-vendor fetch functions (one change reason each),
- ``vendor_http.py``    politeness (sleep/spoof) + raw Tencent HTTP,
- ``response_parsers.py`` / ``ticker_formats.py``  pure parsing/format functions,
- ``capability.py``     probing + capability matrix + probe cache.

The public surface (method names, signatures, fallback order, returns) is
preserved exactly from the pre-split implementation.
"""

from __future__ import annotations

from typing import Any, Dict

from tradingagents.screener import capability
from tradingagents.screener import vendors
from tradingagents.screener.throttling import AntiBanConfig, ThrottledRequester
from tradingagents.screener.vendor_http import DataSourceConfig, VendorHttp
from tradingagents.screener.vendors._guard import TRACKER as VENDOR_HEALTH

# Compat re-exports: these used to be defined in this module.
ProbeResult = capability.ProbeResult

__all__ = ["ScreenerDataAccess", "DataSourceConfig", "ProbeResult"]


class ScreenerDataAccess:
    """多源金融数据访问层 (A0/A1).

    统一封装 Sina、Tencent、THS、Baidu、Baostock 等多个数据源，
    自动探测可用性，支持主备源自动切换，优雅降级。
    """

    # 默认数据源优先级配置
    DEFAULT_VENDORS: Dict[str, Any] = {
        # 历史K线: Tencent直连 > AkShare Tencent > Sina > Baostock > yfinance
        "hist_primary": "tencent_direct",
        "hist_secondary": "tencent",
        "hist_tertiary": "sina",
        "hist_quaternary": "baostock",
        # 实时行情: Tencent直连 > AkShare Tencent > Sina
        "spot_primary": "tencent_direct",
        "spot_secondary": "tencent",
        "spot_tertiary": "sina",
        # 概念板块: THS > Sina
        "concept_primary": "ths",
        "concept_secondary": "sina",
        # 行业板块: THS
        "industry_primary": "ths",
        # 资金流向: THS > AkShare EastMoney
        "fund_flow_primary": "ths",
        "fund_flow_secondary": "em",
        # 指数数据: Tencent直连 > Sina > AkShare Tencent
        "index_primary": "tencent_direct",
        "index_secondary": "sina",
        "index_tertiary": "tencent",
        # 是否启用浏览器头伪装
        "spoof_browser_headers": True,
        # 是否启用 yfinance 备源
        "enable_yfinance_backup": True,
    }

    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}
        self._probe_cache: Dict[str, Any] | None = None
        self._ds_config = DataSourceConfig(
            **{
                k: v
                for k, v in self.config.get("ds_config", {}).items()
                if k in DataSourceConfig.__dataclass_fields__
            }
        )
        anti_ban = self.config.get("anti_ban", {})
        self.requester = ThrottledRequester(
            AntiBanConfig(
                base_interval=anti_ban.get("base_interval", 1.0),
                burst_threshold=anti_ban.get("burst_threshold", 10),
                burst_pause=anti_ban.get("burst_pause", 2.0),
                failure_penalty=anti_ban.get("failure_penalty", 1.5),
                soft_rpm_limit=anti_ban.get("soft_rpm_limit", 30),
            )
        )
        self._tushare_token: str = capability.load_tushare_token()
        # B-11.1: process-level cache to avoid duplicate hist requests across Stage A and Stage B
        # R3 cache policy: in-memory, instance-scoped, no TTL (a run is short); invalidation is
        # implicit — a new ScreenerDataAccess per run starts cold. Counters expose hit ratio.
        self._hist_cache: Dict[str, Any] = {}
        self._hist_cache_hits = 0
        self._hist_cache_misses = 0
        # R3: per-run consecutive failure counters for adaptive degradation
        self._vendor_fail_counts: Dict[str, int] = {}

    # -------------------------------------------------------------------------
    # 内部: 配置与共享对象
    # -------------------------------------------------------------------------

    def _vendors_config(self) -> Dict[str, Any]:
        merged = dict(self.DEFAULT_VENDORS)
        merged.update(self.config.get("vendors", {}))
        return merged

    def _http(self) -> VendorHttp:
        return VendorHttp.from_vendor_config(self._ds_config, self._vendors_config())

    # -------------------------------------------------------------------------
    # 运行时自适应降级 (R3): 同一 run 内某供应商连续失败 N 次后短路跳过
    # -------------------------------------------------------------------------
    _CIRCUIT_BREAK_AFTER = 3

    def _vendor_circuit_open(self, name: str) -> bool:
        """True when a vendor failed N consecutive times and should be skipped."""
        return self._vendor_fail_counts.get(name, 0) >= self._CIRCUIT_BREAK_AFTER

    def _note_vendor_failure(self, name: str) -> None:
        self._vendor_fail_counts[name] = self._vendor_fail_counts.get(name, 0) + 1

    def _note_vendor_success(self, name: str) -> None:
        self._vendor_fail_counts[name] = 0

    # -------------------------------------------------------------------------
    # 数据健康度监控 (R3): vendor health snapshot + hist-cache stats
    # -------------------------------------------------------------------------

    def get_vendor_health_snapshot(self) -> Dict[str, Any]:
        """Per-vendor call/failure/elapsed stats collected via @vendor_call."""
        return VENDOR_HEALTH.snapshot()

    def get_vendor_health_lines(self) -> list:
        """Human-readable per-vendor health summary (for logs / run summary)."""
        return VENDOR_HEALTH.summary_lines()

    def reset_vendor_health(self) -> None:
        """Start a fresh health audit (call at the top of a run)."""
        VENDOR_HEALTH.reset()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Hist-cache effectiveness: hits/misses/ratio (invalidation = new instance)."""
        total = self._hist_cache_hits + self._hist_cache_misses
        return {
            "hist_cache_hits": self._hist_cache_hits,
            "hist_cache_misses": self._hist_cache_misses,
            "hist_cache_hit_ratio": round(self._hist_cache_hits / total, 3) if total else 0.0,
        }

    # -------------------------------------------------------------------------
    # 能力探测 API
    # -------------------------------------------------------------------------

    def get_interface_capability_summary(self) -> Dict[str, Any]:
        """返回接口能力摘要 (不执行 live probe)."""
        return capability.build_capability_summary(
            self._vendors_config(),
            capability.check_libraries(),
            self._tushare_token,
        )

    def validate_interface_assumptions(
        self, trade_date: str | None = None
    ) -> Dict[str, Any]:
        """执行全量 live probe，返回探测摘要."""
        # R3: each run starts a fresh vendor-health audit (probe calls count too).
        self.reset_vendor_health()
        summary = self._load_or_run_probes(trade_date=trade_date)
        summary = capability.apply_legacy_aliases(summary, self._vendors_config())
        warnings = list(summary.get("warnings", []))

        # 生成人类可读的总结警告
        if not summary.get("akshare_importable", False):
            warnings.append("[WARN] AkShare not importable")
        if not summary.get("baostock_importable", False):
            warnings.append("[WARN] Baostock not importable; hist tertiary fallback disabled")
        if not summary.get("py_mini_racer_importable", False):
            warnings.append(
                "[WARN] py-mini-racer not importable; THS fund-flow may fail; install with: pip install py-mini-racer"
            )

        verified_modules = [
            ("spot_snapshot", "Spot snapshot"),
            ("hist_fetch", "Historical bars"),
            ("concept_list", "Concept boards"),
            ("industry_list", "Industry boards"),
            ("fund_flow", "Fund flow"),
            ("index_spot", "Index spot"),
            ("tick_data", "Tick data"),
        ]
        for key, label in verified_modules:
            if not summary.get(f"{key}_verified", False):
                warnings.append(f"[WARN] {label} unavailable; using placeholder data")

        summary["warnings"] = warnings
        summary["request_stats"] = self.requester.get_stats()
        # R3: attach vendor health + hist-cache effectiveness so the run report
        # carries a live reliability audit.
        summary["vendor_health"] = self.get_vendor_health_snapshot()
        summary["cache_stats"] = self.get_cache_stats()
        # B-6.1: surface throttle warnings at the top level alongside probe warnings
        throttle_warnings = summary["request_stats"].get("warnings", [])
        for w in throttle_warnings:
            if w not in summary["warnings"]:
                summary["warnings"].append(w)
        return summary

    def _probe_groups(self) -> Dict[str, list]:
        """Probe targets per module; vendor functions bound to one shared http."""
        probe_config = self.config.get("a0_probe", {})
        sample_symbol = probe_config.get("sample_symbol", "000001")
        sample_start = probe_config.get("sample_hist_start", "20250101")
        sample_end = probe_config.get("sample_hist_end", "20250110")
        http = self._http()
        requester = self.requester

        return {
            "spot_snapshot": [
                ("spot_tencent_direct", lambda: vendors.tencent.fetch_spot_direct(http)),
                ("spot_tencent_akshare", lambda: vendors.tencent.fetch_spot_akshare(http)),
                ("spot_sina", lambda: vendors.sina.fetch_spot(http)),
            ],
            "hist_fetch": [
                ("hist_tencent_direct", lambda: vendors.tencent.fetch_hist_direct(
                    http, sample_symbol, sample_start, sample_end)),
                ("hist_tencent_akshare", lambda: vendors.tencent.fetch_hist_akshare(
                    http, sample_symbol, sample_start, sample_end)),
                ("hist_sina", lambda: vendors.sina.fetch_hist(
                    http, sample_symbol, sample_start, sample_end)),
                ("hist_baostock", lambda: vendors.backup.fetch_hist_baostock(
                    http, sample_symbol, sample_start, sample_end)),
            ],
            "concept_list": [
                ("concept_ths", lambda: vendors.ths.fetch_concept_boards(http)),
                ("concept_sina", lambda: vendors.sina.fetch_concept(http)),
            ],
            "industry_list": [
                ("industry_ths", lambda: vendors.ths.fetch_industry_boards(http)),
            ],
            "fund_flow": [
                ("fund_flow_ths", lambda: vendors.ths.fetch_fund_flow(http, symbol="即时")),
                ("fund_flow_em", lambda: vendors.misc.fetch_fund_flow_em(http)),
            ],
            "index_spot": [
                ("index_tencent_direct", lambda: vendors.tencent.fetch_index_direct(http)),
                ("index_sina", lambda: vendors.sina.fetch_index(http)),
                ("index_tencent_akshare", lambda: vendors.tencent.fetch_index_akshare(http)),
            ],
            "tick_data": [
                ("tick_tencent", lambda: vendors.tencent.fetch_tick_akshare(http, "sz000001")),
                ("tick_sina", lambda: vendors.sina.fetch_tick(http, "sz000001")),
            ],
        }

    def _load_or_run_probes(self, trade_date: str | None = None) -> Dict[str, Any]:
        if self._probe_cache is not None:
            if trade_date is not None:
                self._probe_cache["trade_date"] = trade_date
                self._probe_cache["validated"] = True
            return self._probe_cache

        cached = capability.load_probe_cache(self.config, self._tushare_token)
        if cached is not None:
            if trade_date is not None:
                cached["trade_date"] = trade_date
                cached["validated"] = True
            self._probe_cache = cached
            return cached

        if self._live_probe_enabled():
            yfinance_probe = None
            if self._vendors_config().get("enable_yfinance_backup", True):
                probe_config = self.config.get("a0_probe", {})
                sample_symbol = probe_config.get("sample_symbol", "000001")
                sample_start = probe_config.get("sample_hist_start", "20250101")
                sample_end = probe_config.get("sample_hist_end", "20250110")
                http = self._http()
                requester = self.requester
                yfinance_probe = (
                    "hist_yfinance",
                    lambda: vendors.backup.fetch_hist_yfinance(
                        http, requester, sample_symbol, sample_start, sample_end
                    ),
                )
            summary = capability.run_live_probes(
                self.get_interface_capability_summary(),
                self._probe_groups(),
                yfinance_probe,
                self.requester,
            )
        else:
            summary = self.get_interface_capability_summary()
        if trade_date is not None:
            summary["trade_date"] = trade_date
            summary["validated"] = True
        capability.save_probe_cache(summary, self.config)
        self._probe_cache = summary
        return summary

    def _live_probe_enabled(self) -> bool:
        return bool(self.config.get("a0_probe", {}).get("enable_live_probes", True))

    # -------------------------------------------------------------------------
    # 数据获取 API (供应商 fallback 编排)
    # -------------------------------------------------------------------------

    def fetch_hist(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ):
        """获取历史K线, 自动选择可用主源.

        Args:
            ticker: 股票代码, 支持 sh600519 / sz000001 / 600519 等格式
            start_date: 开始日期 YYYYMMDD 或 YYYY-MM-DD
            end_date: 结束日期
            adjust: 复权类型 "qfq" / "hfq" / "" (不复权)

        Returns:
            DataFrame with columns: date, open, close, high, low, volume, amount
        """
        vendors_cfg = self._vendors_config()
        yfinance = vendors_cfg.get("enable_yfinance_backup", True)
        http = self._http()

        # B-11.1: check cache before attempting any vendor request
        cache_key = f"{ticker}_{start_date}_{end_date}_{adjust}"
        if cache_key in self._hist_cache:
            self._hist_cache_hits += 1
            return self._hist_cache[cache_key]
        self._hist_cache_misses += 1

        # Primary: Tencent 直连
        if not self._vendor_circuit_open("tencent_direct"):
            result = vendors.tencent.fetch_hist_direct(http, ticker, start_date, end_date, adjust)
            if result is not None and not getattr(result, "empty", True):
                self._note_vendor_success("tencent_direct")
                self._hist_cache[cache_key] = result
                return result
            self._note_vendor_failure("tencent_direct")

        # Secondary: AkShare Tencent
        if not self._vendor_circuit_open("tencent_akshare"):
            result = vendors.tencent.fetch_hist_akshare(http, ticker, start_date, end_date, adjust)
            if result is not None and not getattr(result, "empty", True):
                self._note_vendor_success("tencent_akshare")
                self._hist_cache[cache_key] = result
                return result
            self._note_vendor_failure("tencent_akshare")

        # Tertiary: AkShare Sina
        if not self._vendor_circuit_open("sina_hist"):
            result = vendors.sina.fetch_hist(http, ticker, start_date, end_date, adjust)
            if result is not None and not getattr(result, "empty", True):
                self._note_vendor_success("sina_hist")
                self._hist_cache[cache_key] = result
                return result
            self._note_vendor_failure("sina_hist")

        # Quaternary: AkShare Baostock
        if not self._vendor_circuit_open("baostock_hist"):
            result = vendors.backup.fetch_hist_baostock(http, ticker, start_date, end_date, adjust)
            if result is not None and not getattr(result, "empty", True):
                self._note_vendor_success("baostock_hist")
                self._hist_cache[cache_key] = result
                return result
            self._note_vendor_failure("baostock_hist")

        # Last resort: yfinance
        if yfinance and not self._vendor_circuit_open("yfinance_hist"):
            result = vendors.backup.fetch_hist_yfinance(http, self.requester, ticker, start_date, end_date)
            if result is not None and not getattr(result, "empty", True):
                self._note_vendor_success("yfinance_hist")
                self._hist_cache[cache_key] = result
                return result
            self._note_vendor_failure("yfinance_hist")

        return None

    def fetch_tencent_hist(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ):
        return vendors.tencent.fetch_hist_akshare(self._http(), ticker, start_date, end_date, adjust)

    def fetch_yfinance_hist(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
    ):
        http = self._http()
        return vendors.backup.fetch_hist_yfinance(http, self.requester, ticker, start_date, end_date)

    def fetch_spot_snapshot(self, market: str = "all") -> Any:
        """获取全市场实时行情快照.

        Args:
            market: "all" (全部A股) / "kcb" (科创板) / "bj" (北交所)

        Returns:
            DataFrame with columns: symbol, name, trade, pricechange, changepercent,
            open, high, low, volume, amount, turnover, ...
        """
        http = self._http()
        # Primary - Tencent 直连
        if not self._vendor_circuit_open("tencent_spot"):
            result = vendors.tencent.fetch_spot_direct(http, market=market)
            if result is not None and not getattr(result, "empty", True):
                self._note_vendor_success("tencent_spot")
                return result
            self._note_vendor_failure("tencent_spot")

        # Secondary - AkShare Tencent
        if not self._vendor_circuit_open("tencent_spot_akshare"):
            result = vendors.tencent.fetch_spot_akshare(http, market=market)
            if result is not None and not getattr(result, "empty", True):
                self._note_vendor_success("tencent_spot_akshare")
                return result
            self._note_vendor_failure("tencent_spot_akshare")

        # Tertiary - AkShare Sina
        if not self._vendor_circuit_open("sina_spot"):
            result = vendors.sina.fetch_spot(http, market=market)
            if result is not None and not getattr(result, "empty", True):
                self._note_vendor_success("sina_spot")
                return result
            self._note_vendor_failure("sina_spot")

        return None

    def fetch_concept_boards(self) -> Any:
        """获取概念板块列表.

        Returns:
            DataFrame with columns: code, name, source
        """
        http = self._http()
        result = vendors.ths.fetch_concept_boards(http)
        if result is not None and not getattr(result, "empty", True):
            return result

        result = vendors.sina.fetch_concept(http)
        if result is not None and not getattr(result, "empty", True):
            return result

        return None

    def fetch_policy_news_baidu(
        self,
        curr_date: str,
        look_back_days: int = 7,
        limit: int = 12,
    ) -> Any:
        """获取政策/监管/流动性敏感宏观事件."""
        return vendors.misc.fetch_policy_news_baidu(self._http(), curr_date, look_back_days, limit)

    def fetch_lhb_sina(self, trade_date: str) -> Any:
        """获取龙虎榜明细."""
        return vendors.sina.fetch_lhb_detail(self._http(), trade_date)

    def fetch_lhb_stats_sina(self, recent_days: str = "5") -> Any:
        """获取龙虎榜个股上榜统计."""
        return vendors.sina.fetch_lhb_ggtj(self._http(), recent_days)

    def fetch_lhb_institutional_stats_sina(self, recent_days: str = "5") -> Any:
        """获取龙虎榜机构席位追踪."""
        return vendors.sina.fetch_lhb_jgzz(self._http(), recent_days)

    def fetch_concept_constituents(self, concept_name: str) -> Any:
        """获取概念板块成分股, 以 THS HTML scraping > THS API > EastMoney 顺序尝试."""
        try:
            import akshare as ak

            http = self._http()

            # Strategy 1: THS HTML scraping (most reliable for constituent stocks)
            try:
                df = vendors.ths.fetch_concept_constituents_html(http, concept_name)
                if df is not None and not getattr(df, "empty", True):
                    enriched = df.copy()
                    enriched["source"] = "ths_html"
                    return enriched
            except Exception:
                pass

            # Strategy 2: THS info API (returns concept metadata, not constituents)
            try:
                http.sleep_for_vendor("ths")
                with http.spoof():
                    df = ak.stock_board_concept_info_ths(symbol=concept_name)
                if df is not None and not getattr(df, "empty", True):
                    enriched = df.copy()
                    enriched["source"] = "ths_info"
                    return enriched
            except Exception:
                pass

            # Strategy 3: EastMoney constituents API
            try:
                http.sleep_for_vendor("sina")
                with http.spoof():
                    df = ak.stock_board_concept_cons_em(symbol=concept_name)
                if df is not None and not getattr(df, "empty", True):
                    enriched = df.copy()
                    enriched["source"] = "em_cons"
                    return enriched
            except Exception:
                return None
        except Exception:
            return None
        return None

    def fetch_industry_boards(self) -> Any:
        """获取行业板块列表.

        Returns:
            DataFrame with columns: code, name, source
        """
        result = vendors.ths.fetch_industry_boards(self._http())
        if result is not None and not getattr(result, "empty", True):
            return result
        return None

    def fetch_fund_flow(self, symbol: str = "即时", symbol_type: str = "individual") -> Any:
        """获取资金流向数据.

        Args:
            symbol: "即时" / "3日排行" / "5日排行" / "10日排行" / "20日排行"
            symbol_type: "individual" / "concept" / "industry"

        Returns:
            DataFrame with fund flow data
        """
        http = self._http()
        result = vendors.ths.fetch_fund_flow(http, symbol=symbol, symbol_type=symbol_type)
        if result is not None and not getattr(result, "empty", True):
            return result

        # H4 FIX: use AkShare EastMoney as fallback (instead of Baostock which always returns None)
        result = vendors.misc.fetch_fund_flow_em(http)
        if result is not None and not getattr(result, "empty", True):
            return result

        return None

    def fetch_index_spot(self) -> Any:
        """获取主要指数实时行情.

        Returns:
            DataFrame with index spot data
        """
        http = self._http()
        # Primary - Tencent 直连
        result = vendors.tencent.fetch_index_direct(http)
        if result is not None and not getattr(result, "empty", True):
            return result

        # Secondary - AkShare Sina
        result = vendors.sina.fetch_index(http)
        if result is not None and not getattr(result, "empty", True):
            return result

        # Tertiary - AkShare Tencent
        result = vendors.tencent.fetch_index_akshare(http)
        if result is not None and not getattr(result, "empty", True):
            return result

        return None

    def fetch_index_constituents(self, index_code: str) -> Any:
        """获取指数成分股列表（真实成分股，非指数代码本身）.

        使用 akshare 的 index_stock_cons_weight_csindex 接口，
        返回格式：成分券代码, 成分券名称, 权重, 交易所 等字段。

        Args:
            index_code: 指数代码，如 "000300"（沪深300）、"000905"（中证500）、"399006"（创业板）等

        Returns:
            DataFrame with columns: 日期, 指数代码, 成分券代码, 成分券名称, 权重, 交易所, ...
            空结果返回 None
        """
        return vendors.sina.fetch_index_cons_weight(self._http(), index_code)

    def fetch_tick_data(self, symbol: str) -> Any:
        """获取分笔成交明细.

        Args:
            symbol: 带市场前缀的股票代码, 如 "sz000001"

        Returns:
            DataFrame with columns: time, price, change, volume, amount, type
        """
        http = self._http()
        result = vendors.tencent.fetch_tick_akshare(http, symbol)
        if result is not None and not getattr(result, "empty", True):
            return result

        result = vendors.sina.fetch_tick(http, symbol)
        if result is not None and not getattr(result, "empty", True):
            return result

        return None

    # -------------------------------------------------------------------------
    # 辅助数据 (Baidu)
    # -------------------------------------------------------------------------

    def fetch_valuation_baidu(self) -> Any:
        """获取A股估值数据 (Baostock/Baidu 辅助)."""
        return vendors.misc.fetch_valuation_baidu()

    def fetch_vote_baidu(self, symbol: str = "000001") -> Any:
        """获取股票人气投票数据."""
        return vendors.misc.fetch_vote_baidu(symbol=symbol)
