from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import random
import time
from typing import Any, Callable, Dict, List, Optional
from contextlib import nullcontext

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screener.http_spoof import patch_requests_browser_headers
from tradingagents.screener.throttling import AntiBanConfig, ThrottledRequester


def _safe_float(val) -> float | None:
    """安全转换为 float，失败返回 None."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# DataSourceConfig - 全局数据源配置
# ---------------------------------------------------------------------------

@dataclass
class DataSourceConfig:
    request_timeout: float = 10.0
    probe_timeout: float = 30.0
    max_retries: int = 2
    retry_delay: float = 1.0
    sina_page_interval: float = 0.5
    ths_interval: float = 1.0
    random_jitter: float = 0.1
    graceful_degrade: bool = True


# ---------------------------------------------------------------------------
# ProbeResult - 单个接口探测结果
# ---------------------------------------------------------------------------

@dataclass
class ProbeResult:
    name: str
    ok: bool
    elapsed: float = 0.0
    shape: Any = None
    detail: str = ""
    classification: str = "unknown"
    vendor: str = ""


# ---------------------------------------------------------------------------
# ScreenerDataAccess - 多源金融数据访问层
# ---------------------------------------------------------------------------

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
        self._tushare_token: str = self._load_tushare_token()
        self._ths_js_ctx: Any = None
        # B-11.1: process-level cache to avoid duplicate hist requests across Stage A and Stage B
        self._hist_cache: Dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # 公共 API
    # -------------------------------------------------------------------------

    def get_interface_capability_summary(self) -> Dict[str, Any]:
        """返回接口能力摘要 (不执行 live probe)."""
        libs = self._check_libraries()
        vendors = self._vendors_config()
        summary = {
            "akshare_importable": libs["akshare"],
            "baostock_importable": libs["baostock"],
            "tushare_importable": libs["tushare"],
            "py_mini_racer_importable": libs["py_mini_racer"],
            # 各模块验证状态 (未知, 待 probe)
            "spot_snapshot_verified": False,
            "hist_fetch_verified": False,
            "concept_list_verified": False,
            "industry_list_verified": False,
            "fund_flow_verified": False,
            "index_spot_verified": False,
            "tick_data_verified": False,
            # 各模块数据源
            "spot_primary_vendor": vendors.get("spot_primary", "tencent_direct"),
            "hist_primary_vendor": vendors.get("hist_primary", "tencent_direct"),
            "concept_primary_vendor": vendors.get("concept_primary", "ths"),
            "industry_primary_vendor": vendors.get("industry_primary", "ths"),
            "fund_flow_primary_vendor": vendors.get("fund_flow_primary", "ths"),
            "index_primary_vendor": vendors.get("index_primary", "tencent_direct"),
            # 各模块备源
            "spot_secondary_vendor": vendors.get("spot_secondary", "tencent"),
            "hist_secondary_vendor": vendors.get("hist_secondary", "tencent"),
            "hist_tertiary_vendor": vendors.get("hist_tertiary", "sina"),
            "hist_quaternary_vendor": vendors.get("hist_quaternary", "baostock"),
            "fund_flow_secondary_vendor": vendors.get("fund_flow_secondary", "em"),
            "index_secondary_vendor": vendors.get("index_secondary", "sina"),
            "index_tertiary_vendor": vendors.get("index_tertiary", "tencent"),
            # Tushare
            "tushare_configured": bool(self._tushare_token),
            "warnings": [],
            "freshness": [],
            "validated": False,
        }
        summary["vendor_baseline"] = self._build_vendor_baseline(summary)
        summary["strategy_capabilities"] = self._build_strategy_capabilities(summary)
        return summary

    def validate_interface_assumptions(
        self, trade_date: str | None = None
    ) -> Dict[str, Any]:
        """执行全量 live probe，返回探测摘要."""
        summary = self._load_or_run_probes(trade_date=trade_date)
        summary = self._apply_legacy_capability_aliases(summary)
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
        # B-6.1: surface throttle warnings at the top level alongside probe warnings
        throttle_warnings = summary["request_stats"].get("warnings", [])
        for w in throttle_warnings:
            if w not in summary["warnings"]:
                summary["warnings"].append(w)
        return summary

    # -------------------------------------------------------------------------
    # 数据获取 API (高层)
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
        vendors = self._vendors_config()
        primary = vendors.get("hist_primary", "tencent")
        secondary = vendors.get("hist_secondary", "sina")
        tertiary = vendors.get("hist_tertiary", "baostock")
        yfinance = vendors.get("enable_yfinance_backup", True)

        # B-11.1: check cache before attempting any vendor request
        cache_key = f"{ticker}_{start_date}_{end_date}_{adjust}"
        if cache_key in self._hist_cache:
            return self._hist_cache[cache_key]

        # Primary: Tencent 直连
        result = self._fetch_hist_tencent_direct(ticker, start_date, end_date, adjust)
        if result is not None and not getattr(result, "empty", True):
            self._hist_cache[cache_key] = result
            return result

        # Secondary: AkShare Tencent
        result = self._fetch_hist_tencent(ticker, start_date, end_date, adjust)
        if result is not None and not getattr(result, "empty", True):
            self._hist_cache[cache_key] = result
            return result

        # Tertiary: AkShare Sina
        result = self._fetch_hist_sina(ticker, start_date, end_date, adjust)
        if result is not None and not getattr(result, "empty", True):
            self._hist_cache[cache_key] = result
            return result

        # Quaternary: AkShare Baostock
        result = self._fetch_hist_baostock(ticker, start_date, end_date, adjust)
        if result is not None and not getattr(result, "empty", True):
            self._hist_cache[cache_key] = result
            return result

        # Last resort: yfinance
        if yfinance:
            result = self._fetch_hist_yfinance(ticker, start_date, end_date)
            if result is not None and not getattr(result, "empty", True):
                self._hist_cache[cache_key] = result
                return result

        return None

    def fetch_tencent_hist(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ):
        return self._fetch_hist_tencent(ticker, start_date, end_date, adjust)

    def fetch_yfinance_hist(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
    ):
        return self._fetch_hist_yfinance(ticker, start_date, end_date)

    def fetch_spot_snapshot(self, market: str = "all") -> Any:
        """获取全市场实时行情快照.

        Args:
            market: "all" (全部A股) / "kcb" (科创板) / "bj" (北交所)

        Returns:
            DataFrame with columns: symbol, name, trade, pricechange, changepercent,
            open, high, low, volume, amount, turnover, ...
        """
        vendors = self._vendors_config()
        primary = vendors.get("spot_primary", "tencent")
        secondary = vendors.get("spot_secondary", "sina")

        tried = []
        # Primary - Tencent 直连
        result = self._fetch_spot_tencent_direct(market=market)
        if result is not None and not getattr(result, "empty", True):
            return result
        tried.append("tencent_direct")

        # Secondary - AkShare Tencent
        result = self._fetch_spot_tencent(market=market)
        if result is not None and not getattr(result, "empty", True):
            return result
        tried.append("tencent_akshare")

        # Tertiary - AkShare Sina
        result = self._fetch_spot_sina(market=market)
        if result is not None and not getattr(result, "empty", True):
            return result
        tried.append("sina")

        return None

    def fetch_concept_boards(self) -> Any:
        """获取概念板块列表.

        Returns:
            DataFrame with columns: code, name, source
        """
        vendors = self._vendors_config()
        primary = vendors.get("concept_primary", "ths")
        secondary = vendors.get("concept_secondary", "sina")

        tried = []
        if primary == "ths":
            result = self._fetch_concept_ths()
            if result is not None and not getattr(result, "empty", True):
                return result
            tried.append("ths")

        if secondary == "sina":
            result = self._fetch_concept_sina()
            if result is not None and not getattr(result, "empty", True):
                return result
            tried.append("sina")

        return None

    def fetch_policy_news_baidu(
        self,
        curr_date: str,
        look_back_days: int = 7,
        limit: int = 12,
    ) -> Any:
        """获取政策/监管/流动性敏感宏观事件."""
        try:
            import pandas as pd
            import akshare as ak

            target_date = datetime.strptime(curr_date, "%Y-%m-%d")
            frames = []
            for offset in range(max(look_back_days, 1)):
                date_str = (target_date - timedelta(days=offset)).strftime("%Y%m%d")
                try:
                    self._sleep_for_vendor("baidu")
                    with self._maybe_spoof_headers():
                        frames.append(ak.news_economic_baidu(date=date_str))
                except Exception:
                    continue

            if not frames:
                return None

            df = pd.concat(frames, ignore_index=True)
            if "地区" in df.columns:
                region_mask = df["地区"].astype(str).str.contains("中国|China", case=False, na=False)
                df = df.loc[region_mask].copy()
            if "事件" in df.columns:
                keyword_mask = df["事件"].astype(str).str.contains(
                    "政策|监管|央行|利率|LPR|MLF|科技|半导体|创新|制造|补贴|算力|人工智能|机器人|新能源",
                    case=False,
                    na=False,
                )
                df = df.loc[keyword_mask].copy()
            if df.empty:
                return None
            return df.head(limit).reset_index(drop=True)
        except Exception:
            return None

    def fetch_lhb_sina(self, trade_date: str) -> Any:
        """获取龙虎榜明细."""
        try:
            import akshare as ak

            target = trade_date.replace("-", "")
            self._sleep_for_vendor("sina")
            with self._maybe_spoof_headers():
                return ak.stock_lhb_detail_daily_sina(date=target)
        except Exception:
            return None

    def fetch_lhb_stats_sina(self, recent_days: str = "5") -> Any:
        """获取龙虎榜个股上榜统计."""
        try:
            import akshare as ak

            self._sleep_for_vendor("sina")
            with self._maybe_spoof_headers():
                return ak.stock_lhb_ggtj_sina(symbol=recent_days)
        except Exception:
            return None

    def fetch_lhb_institutional_stats_sina(self, recent_days: str = "5") -> Any:
        """获取龙虎榜机构席位追踪."""
        try:
            import akshare as ak

            self._sleep_for_vendor("sina")
            with self._maybe_spoof_headers():
                return ak.stock_lhb_jgzz_sina(symbol=recent_days)
        except Exception:
            return None

    def fetch_concept_constituents(self, concept_name: str) -> Any:
        """获取概念板块成分股, 以 THS HTML scraping > THS API > EastMoney 顺序尝试."""
        try:
            import akshare as ak

            # Strategy 1: THS HTML scraping (most reliable for constituent stocks)
            try:
                df = self._fetch_concept_constituents_ths_html(concept_name)
                if df is not None and not getattr(df, "empty", True):
                    enriched = df.copy()
                    enriched["source"] = "ths_html"
                    return enriched
            except Exception:
                pass

            # Strategy 2: THS info API (returns concept metadata, not constituents)
            try:
                self._sleep_for_vendor("ths")
                with self._maybe_spoof_headers():
                    df = ak.stock_board_concept_info_ths(symbol=concept_name)
                if df is not None and not getattr(df, "empty", True):
                    enriched = df.copy()
                    enriched["source"] = "ths_info"
                    return enriched
            except Exception:
                pass

            # Strategy 3: EastMoney constituents API
            try:
                self._sleep_for_vendor("sina")
                with self._maybe_spoof_headers():
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
        vendors = self._vendors_config()
        primary = vendors.get("industry_primary", "ths")

        if primary == "ths":
            result = self._fetch_industry_ths()
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
        vendors = self._vendors_config()
        primary = vendors.get("fund_flow_primary", "ths")
        secondary = vendors.get("fund_flow_secondary", "baostock")

        tried = []
        if primary == "ths":
            result = self._fetch_fund_flow_ths(symbol=symbol, symbol_type=symbol_type)
            if result is not None and not getattr(result, "empty", True):
                return result
            tried.append("ths")

        # H4 FIX: use AkShare EastMoney as fallback (instead of Baostock which always returns None)
        if secondary == "em":
            result = self._fetch_fund_flow_em()
            if result is not None and not getattr(result, "empty", True):
                return result
            tried.append("em")

        return None

    def fetch_index_spot(self) -> Any:
        """获取主要指数实时行情.

        Returns:
            DataFrame with index spot data
        """
        vendors = self._vendors_config()
        primary = vendors.get("index_primary", "sina")
        secondary = vendors.get("index_secondary", "tencent")

        tried = []
        # Primary - Tencent 直连
        result = self._fetch_index_tencent_direct()
        if result is not None and not getattr(result, "empty", True):
            return result
        tried.append("tencent_direct")

        # Secondary - AkShare Sina
        result = self._fetch_index_sina()
        if result is not None and not getattr(result, "empty", True):
            return result
        tried.append("sina")

        # Tertiary - AkShare Tencent
        result = self._fetch_index_tencent()
        if result is not None and not getattr(result, "empty", True):
            return result
        tried.append("tencent_akshare")

        return None

    def fetch_index_constituents(self, index_code: str) -> Any:
        """获取指数成分股列表（真实成分股，非指数代码本身）。

        使用 akshare 的 index_stock_cons_weight_csindex 接口，
        返回格式：成分券代码, 成分券名称, 权重, 交易所 等字段。

        Args:
            index_code: 指数代码，如 "000300"（沪深300）、"000905"（中证500）、"399006"（创业板）等

        Returns:
            DataFrame with columns: 日期, 指数代码, 成分券代码, 成分券名称, 权重, 交易所, ...
            空结果返回 None
        """
        try:
            import akshare as ak

            self._sleep_for_vendor("sina")
            with self._maybe_spoof_headers():
                return ak.index_stock_cons_weight_csindex(symbol=index_code)
        except Exception:
            return None

    def fetch_tick_data(self, symbol: str) -> Any:
        """获取分笔成交明细.

        Args:
            symbol: 带市场前缀的股票代码, 如 "sz000001"

        Returns:
            DataFrame with columns: time, price, change, volume, amount, type
        """
        result = self._fetch_tick_tencent(symbol)
        if result is not None and not getattr(result, "empty", True):
            return result

        result = self._fetch_tick_sina(symbol)
        if result is not None and not getattr(result, "empty", True):
            return result

        return None

    # -------------------------------------------------------------------------
    # 内部: 各数据源具体实现
    # -------------------------------------------------------------------------

    # -- Sina (新浪财经) -----------------------------------------------

    def _fetch_spot_sina(self, market: str = "all") -> Any:
        import akshare as ak

        try:
            self._sleep_for_vendor("sina")
            with self._maybe_spoof_headers():
                if market == "kcb":
                    return ak.stock_zh_kcb_spot()
                elif market == "bj":
                    return None  # Sina 不直接支持北交所
                else:
                    return ak.stock_zh_a_spot()
        except Exception:
            return None

    def _fetch_hist_sina(
        self, ticker: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> Any:
        import akshare as ak

        try:
            # 转换格式: sh600519 -> sh600519
            sym = self._normalize_ticker_for_sina(ticker)
            sd = start_date.replace("-", "")
            ed = end_date.replace("-", "")
            self._sleep_for_vendor("sina")
            with self._maybe_spoof_headers():
                return ak.stock_zh_a_daily(symbol=sym, start_date=sd, end_date=ed, adjust=adjust)
        except Exception:
            return None

    def _fetch_concept_sina(self) -> Any:
        """获取新浪概念板块 (需要正确的 symbol 参数).

        注意: stock_classify_sina 需要中文参数，当前环境可能有编码问题。
        如果失败，返回 None 让备源 THS 接管。
        """
        try:
            import akshare as ak

            try:
                self._sleep_for_vendor("sina")
                with self._maybe_spoof_headers():
                    df = ak.stock_classify_sina(symbol="概念分类")
            except Exception:
                return None
            if df is not None and not df.empty:
                df = df.copy()
                df["source"] = "sina"
                return df
            return None
        except Exception:
            return None

    def _fetch_index_sina(self) -> Any:
        import akshare as ak

        try:
            self._sleep_for_vendor("sina")
            with self._maybe_spoof_headers():
                return ak.stock_zh_index_spot_sina()
        except Exception:
            return None

    def _fetch_tick_sina(self, symbol: str) -> Any:
        import akshare as ak

        try:
            sym = symbol.lower()
            self._sleep_for_vendor("sina")
            with self._maybe_spoof_headers():
                return ak.stock_intraday_sina(symbol=sym)
        except Exception:
            return None

    # -- Tencent (腾讯证券) --------------------------------------------

    def _fetch_hist_tencent(
        self, ticker: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> Any:
        import akshare as ak

        try:
            code, exchange = self._normalize_ticker_for_tencent(ticker)
            tx_symbol = f"{exchange}{code}"
            sd = start_date.replace("-", "")
            ed = end_date.replace("-", "")
            # adjust: ""=不复权, "qfq"=前复权, "hfq"=后复权
            adj_map = {"qfq": "qfq", "hfq": "hfq", "": ""}
            adj = adj_map.get(adjust, "qfq")
            self._sleep_for_vendor("tencent")
            with self._maybe_spoof_headers():
                return ak.stock_zh_a_hist_tx(
                    symbol=tx_symbol, start_date=sd, end_date=ed, adjust=adj
                )
        except Exception:
            return None

    def _fetch_spot_tencent(self, market: str = "all") -> Any:
        try:
            # stock_zh_a_spot_tx 未在 __init__ 导出, 需直接导入
            from akshare.stock.stock_zh_a_tx import stock_zh_a_spot_tx

            self._sleep_for_vendor("tencent")
            with self._maybe_spoof_headers():
                df = stock_zh_a_spot_tx()
            if df is not None and not df.empty:
                df = df.copy()
                df["source"] = "tencent"
            return df
        except Exception:
            return None

    def _fetch_tick_tencent(self, symbol: str) -> Any:
        import akshare as ak

        try:
            self._sleep_for_vendor("tencent")
            with self._maybe_spoof_headers():
                return ak.stock_zh_a_tick_tx_js(symbol=symbol.lower())
        except Exception:
            return None

    def _fetch_index_tencent(self) -> Any:
        import akshare as ak

        try:
            # 获取主要指数历史数据
            self._sleep_for_vendor("tencent")
            with self._maybe_spoof_headers():
                df = ak.stock_zh_index_daily_tx(symbol="sh000001", start_date="20260101", end_date="20260110")
            return df
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # 内部: 腾讯直连 HTTP（绕过 AkShare，以腾讯为主源）
    # -------------------------------------------------------------------------

    def _tencent_direct(self, url: str, timeout: float = 10.0) -> str | None:
        """执行腾讯直连 HTTP GET，返回原始文本，失败返回 None."""
        try:
            import requests

            self._sleep_for_vendor("tencent")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://finance.qq.com/",
                "Accept": "*/*",
            }
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None

    def _fetch_hist_tencent_direct(
        self, ticker: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> Any:
        """直接 HTTP 调用腾讯财经历史K线接口（主源）。

        API: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={ticker},day,{start},{end},{count},{adjust}

        返回字段顺序: date, open, close, high, low, volume
        格式: [["2025-01-02", open, close, high, low, vol], ...]

        注意: 腾讯 API 只接受 YYYY-MM-DD 格式, 不接受 YYYYMMDD 格式。
        传入 YYYYMMDD 格式会返回 {"code":0,"msg":"param error","data":[]}。
        """
        import pandas as pd
        from datetime import datetime

        code, exchange = self._normalize_ticker_for_tencent(ticker)
        tx_symbol = f"{exchange}{code}"

        # 腾讯 API 只接受 YYYY-MM-DD 格式; 标准化输入日期
        def _normalize_date(s: str) -> str:
            s = s.strip()
            if not s:
                return s
            # 已经是 YYYY-MM-DD 格式
            if "-" in s:
                return s
            # YYYYMMDD -> YYYY-MM-DD
            if len(s) == 8 and s.isdigit():
                return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
            return s

        sd = _normalize_date(start_date)
        ed = _normalize_date(end_date)
        adj_map = {"qfq": "qfq", "hfq": "hfq", "": ""}
        adj = adj_map.get(adjust, "qfq")
        # 最多取 500 条
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tx_symbol},day,{sd},{ed},500,{adj}"
        text = self._tencent_direct(url)
        if text is None:
            return None
        try:
            import json

            # 腾讯返回 "var kline_dayqfq={...}" 包裹的 JSON
            raw = text.strip()
            if raw.startswith("var "):
                raw = raw[raw.index("=") + 1 :]
            data = json.loads(raw)

            # 检查 API 返回错误 (param error, etc.)
            if data.get("code") != 0 or not data.get("data"):
                # data 为空列表表示 param error 或无数据
                return None

            # data 可能是 dict (正常情况) 或空列表 (param error)
            data_payload = data.get("data", {})
            if isinstance(data_payload, list):
                return None  # param error, no data

            qt_data = data_payload.get(tx_symbol, {})
            arr_key = "qfqday" if adj == "qfq" else ("hfqday" if adj == "hfq" else "day")
            candles = qt_data.get(arr_key, qt_data.get("day", []))
            if not candles or not isinstance(candles, list):
                return None
            rows = []
            for c in candles:
                if not isinstance(c, (list, tuple)) or len(c) < 6:
                    continue
                rows.append(
                    {
                        "date": c[0],
                        "open": _safe_float(c[1]),
                        "close": _safe_float(c[2]),
                        "high": _safe_float(c[3]),
                        "low": _safe_float(c[4]),
                        "volume": _safe_float(c[5]),
                    }
                )
            if not rows:
                return None
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            df["amount"] = None
            return df
        except Exception:
            return None

    def _fetch_spot_tencent_direct(self, market: str = "all") -> Any:
        """直接 HTTP 调用腾讯财经实时行情接口（主源）。

        API: https://qt.gtimg.cn/q={symbol1},{symbol2},...
        每行格式: v_{symbol}="1~name~code~price~prev_close~open~vol~..."
        返回 DataFrame: symbol, name, price, change, changepercent, open, high, low, volume, amount, ...
        """
        import pandas as pd

        try:
            text = self._tencent_direct("https://qt.gtimg.cn/q=sh600519,sz000001")
            if text is None:
                return None
            lines = text.strip().split("\n")
            rows = []
            for line in lines:
                line = line.strip()
                if not line or not line.startswith("v_"):
                    continue
                eq_idx = line.index("=")
                val = line[eq_idx + 1 :].strip('"; ')
                parts = val.split("~")
                if len(parts) < 32:
                    continue
                try:
                    symbol_raw = parts[2]
                    # 腾讯 symbol: sh600519 / sz000001 -> normalize
                    sym = symbol_raw.lower()
                    if sym.startswith("sh") or sym.startswith("sz"):
                        ticker_out = sym
                    else:
                        ticker_out = symbol_raw
                    rows.append(
                        {
                            "symbol": ticker_out,
                            "name": parts[1],
                            "trade": _safe_float(parts[3]),
                            "prev_close": _safe_float(parts[4]),
                            "open": _safe_float(parts[5]),
                            "volume": _safe_float(parts[6]),
                            "amount": _safe_float(parts[37]) if len(parts) > 37 else None,
                            "change": _safe_float(parts[31]) if len(parts) > 31 else None,
                            "changepercent": _safe_float(parts[32]) if len(parts) > 32 else None,
                            "high": _safe_float(parts[33]) if len(parts) > 33 else None,
                            "low": _safe_float(parts[34]) if len(parts) > 34 else None,
                        }
                    )
                except (IndexError, ValueError):
                    continue
            if not rows:
                return None
            df = pd.DataFrame(rows)
            df["source"] = "tencent_direct"
            return df
        except Exception:
            return None

    def _fetch_index_tencent_direct(self) -> Any:
        """直接 HTTP 调用腾讯财经指数实时行情接口（主源）。

        API: https://qt.gtimg.cn/q=s_sh000001,s_sz399001,...
        返回格式: 1~name~code~price~change~changepct~volume~amount~...
        注意: 指数字段数量比股票少，不足 32 列，不能用股票解析逻辑。
        """
        import pandas as pd

        try:
            symbols = "s_sh000001,s_sz399001,s_sz399006,s_sh000688,s_sh000300,s_sh000905,s_sz399673"
            text = self._tencent_direct(f"https://qt.gtimg.cn/q={symbols}")
            if text is None:
                return None
            lines = text.strip().split("\n")
            rows = []
            for line in lines:
                line = line.strip()
                if not line or not line.startswith("v_"):
                    continue
                eq_idx = line.index("=")
                val = line[eq_idx + 1 :].strip('"; ')
                parts = val.split("~")
                if len(parts) < 6:
                    continue
                try:
                    rows.append(
                        {
                            "symbol": parts[2],
                            "name": parts[1],
                            "price": _safe_float(parts[3]),
                            "change": _safe_float(parts[4]),
                            "changepercent": _safe_float(parts[5]),
                            "volume": _safe_float(parts[6]) if len(parts) > 6 else None,
                            "amount": _safe_float(parts[8]) if len(parts) > 8 else None,
                        }
                    )
                except (IndexError, ValueError):
                    continue
            if not rows:
                return None
            return pd.DataFrame(rows)
        except Exception:
            return None

    # -- THS (同花顺) -------------------------------------------------

    def _fetch_concept_ths(self) -> Any:
        import akshare as ak

        try:
            self._sleep_for_vendor("ths")
            with self._maybe_spoof_headers():
                df = ak.stock_board_concept_name_ths()
            if df is not None and not df.empty:
                df = df.copy()
                df = df.rename(columns={"name": "name", "code": "code"})
                df["source"] = "ths"
            return df
        except Exception:
            return None

    def _fetch_concept_constituents_ths_html(self, concept_name: str, max_stocks: int = 50) -> Any:
        """Fetch concept constituents by scraping the THS board detail page.

        The standard AkShare THS APIs return concept metadata (like total market cap)
        instead of constituent stocks. This method scrapes the HTML board detail page
        which contains the actual constituent stock table.

        URL pattern: http://q.10jqka.com.cn/gn/detail/code/{ths_code}/

        The page table has columns:
        - Rank (序号)
        - Code (股票代码) - 6-digit
        - Name (股票简称) - Chinese name
        - Price (现价)
        - Change% (涨跌幅)
        - Turnover (换手率)
        - Volume (成交额)
        - ...
        """
        import pandas as pd
        import re

        # First, get the THS code for this concept name
        ths_code = self._resolve_ths_concept_code(concept_name)
        if ths_code is None:
            return None

        # Scrape the board detail page
        url = f"http://q.10jqka.com.cn/gn/detail/code/{ths_code}/"
        text = self._tencent_direct(url, timeout=15.0)
        if text is None:
            return None

        # Parse the stock table from HTML
        rows = self._parse_ths_board_table(text, max_stocks)
        if not rows:
            return None

        return pd.DataFrame(rows)

    def _resolve_ths_concept_code(self, concept_name: str) -> str | None:
        """Resolve a concept name to its THS board code (e.g., "AI PC" -> "309121").

        Uses the THS concept name list as a lookup table.
        """
        cache_key = f"_ths_concept_code_map"
        if not hasattr(self, "_concept_code_cache"):
            self._concept_code_cache: Dict[str, str] = {}
            try:
                import akshare as ak
                self._sleep_for_vendor("ths")
                with self._maybe_spoof_headers():
                    df = ak.stock_board_concept_name_ths()
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        name = str(row.get("name", ""))
                        code = str(row.get("code", ""))
                        if name and code:
                            self._concept_code_cache[name] = code
            except Exception:
                pass

        # Direct lookup
        if concept_name in self._concept_code_cache:
            return self._concept_code_cache[concept_name]

        # Fuzzy match: try contains
        for cached_name, cached_code in self._concept_code_cache.items():
            if concept_name in cached_name or cached_name in concept_name:
                return cached_code

        return None

    def _parse_ths_board_table(self, html_content: str, max_stocks: int = 50) -> List[Dict[str, Any]]:
        """Parse the constituent stock table from THS board HTML.

        The table has columns:
        - rank (排名)
        - code (股票代码) - 6-digit string
        - name (股票简称)
        - price (现价)
        - change_pct (涨跌幅)
        - turnover (换手率)
        - amount (成交额)
        - ...
        """
        import re

        rows = []
        # Find the tbody with stock rows
        tbody_match = re.search(r"<tbody>(.*?)</tbody>", html_content, re.DOTALL)
        if not tbody_match:
            return rows

        tbody = tbody_match.group(1)
        tr_matches = re.findall(r"<tr>(.*?)</tr>", tbody, re.DOTALL)

        for tr_html in tr_matches[:max_stocks]:
            # Extract all cells
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr_html, re.DOTALL)
            if len(cells) < 5:
                continue

            # Parse each cell (strip HTML tags)
            def clean_cell(cell_html: str) -> str:
                return re.sub(r"<[^>]+>", "", cell_html).strip()

            # Column mapping (from THS board detail page):
            # 0: rank, 1: code, 2: name, 3: price, 4: change_pct,
            # 5: turnover, 6: amount, 7: volume, 8: amplitude, ...
            try:
                rank = clean_cell(cells[0])
                code = clean_cell(cells[1])
                name = clean_cell(cells[2])
                # Validate: code should be 6 digits
                if not re.match(r"^\d{6}$", code):
                    continue

                # Parse change_pct (e.g., "10.02" or "-5.23%")
                change_str = clean_cell(cells[4])
                change_str = change_str.replace("%", "").strip()
                try:
                    change_pct = float(change_str)
                except ValueError:
                    change_pct = None

                # Parse turnover (e.g., "5.96")
                turnover_str = clean_cell(cells[5])
                try:
                    turnover = float(turnover_str)
                except ValueError:
                    turnover = None

                # Parse amount (成交额, in 亿元)
                amount_str = clean_cell(cells[6])
                try:
                    amount_raw = float(amount_str)
                    # Convert to full units (亿 -> 元)
                    amount = amount_raw * 1e8
                except ValueError:
                    amount = None

                rows.append({
                    "code": code,
                    "name": name,
                    "rank": rank,
                    "change_pct": change_pct,
                    "turnover": turnover,
                    "amount": amount,
                })
            except (IndexError, ValueError):
                continue

        return rows

    def _fetch_industry_ths(self) -> Any:
        import akshare as ak

        try:
            self._sleep_for_vendor("ths")
            with self._maybe_spoof_headers():
                df = ak.stock_board_industry_name_ths()
            if df is not None and not df.empty:
                df = df.copy()
                df["source"] = "ths"
            return df
        except Exception:
            return None

    def _fetch_fund_flow_ths(
        self, symbol: str = "即时", symbol_type: str = "individual"
    ) -> Any:
        import akshare as ak

        try:
            self._sleep_for_vendor("ths")
            with self._maybe_spoof_headers():
                if symbol_type == "individual":
                    return ak.stock_fund_flow_individual(symbol=symbol)
                elif symbol_type == "concept":
                    return ak.stock_fund_flow_concept(symbol=symbol)
                elif symbol_type == "industry":
                    return ak.stock_fund_flow_industry(symbol=symbol)
        except Exception:
            return None
        return None

    # -- AkShare EastMoney fund flow fallback ---------------------------------

    def _fetch_fund_flow_em(self) -> Any:
        """获取东方财富资金流向大盘数据（个股资金流向排名）。

        H4 FIX: 当 THS 主源失败时，使用 AkShare 的 stock_individual_fund_flow_em
        获取个股资金流向数据（东方财富排行数据）。
        这比 Baostock 更可靠且数据更丰富。
        """
        import akshare as ak

        try:
            self._sleep_for_vendor("sina")
            with self._maybe_spoof_headers():
                # stock_individual_fund_flow_em 返回大盘资金流向排行（按主力净流入排序）
                return ak.stock_individual_fund_flow_em(symbol="即时")
        except Exception:
            return None

    # -- Baostock -----------------------------------------------------

    def _fetch_hist_baostock(
        self, ticker: str, start_date: str, end_date: str, adjust: str = "qfq"
    ) -> Any:
        try:
            import baostock as bs

            sym = self._normalize_ticker_for_baostock(ticker)
            sd = start_date.replace("-", "")
            ed = end_date.replace("-", "")

            login_result = bs.login()
            if login_result is None or login_result.error_code != "0":
                return None
            try:
                adjflag_map = {"qfq": "3", "hfq": "2", "": "1"}
                adjflag = adjflag_map.get(adjust, "3")
                rs = bs.query_history_k_data_plus(
                    sym,
                    "date,open,high,low,close,volume",
                    start_date=sd,
                    end_date=ed,
                    frequency="d",
                    adjustflag=adjflag,
                )
                if rs is None or rs.error_code != "0":
                    return None
                data = rs.get_data()
            finally:
                bs.logout()

            if data is not None and not data.empty and len(data) > 0:
                import pandas as pd

                data.columns = ["date", "open", "high", "low", "close", "volume"]
                for col in ["open", "high", "low", "close", "volume"]:
                    data[col] = pd.to_numeric(data[col], errors="coerce")
                data = data.dropna(subset=["date"])
                data["amount"] = None
                data = data.reset_index(drop=True)
                return data
            return None
        except Exception:
            return None

    def _fetch_fund_flow_baostock(self) -> Any:
        # Baostock 资金流数据有限, 返回 None 让上层使用 placeholder
        return None

    # -- yfinance -----------------------------------------------------

    def _fetch_hist_yfinance(
        self, ticker: str, start_date: str, end_date: str
    ) -> Any:
        try:
            import yfinance as yf

            sym = self._normalize_ticker_for_yfinance(ticker)
            ticker_obj = yf.Ticker(sym)
            with self._maybe_spoof_headers():
                result = self.requester.request(
                    ticker_obj.history, start=start_date, end=end_date
                )
            return self._normalize_yfinance_hist_frame(result)
        except Exception:
            return None

    # -- Baidu (辅助数据) ---------------------------------------------

    def fetch_valuation_baidu(self) -> Any:
        """获取A股估值数据 (Baostock/Baidu 辅助)."""
        import akshare as ak

        try:
            return ak.stock_zh_valuation_baidu()
        except Exception:
            return None

    def fetch_vote_baidu(self, symbol: str = "000001") -> Any:
        """获取股票人气投票数据."""
        import akshare as ak

        try:
            return ak.stock_zh_vote_baidu(symbol=symbol)
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # 内部: probe 系统
    # -------------------------------------------------------------------------

    def _run_live_probes(self) -> Dict[str, Any]:
        """执行全量 live probe, 测试所有接口可用性."""
        print("[SCREENER] Stage DataProbe: running live API probes (this may take ~10-20s)...")

        summary = self.get_interface_capability_summary()
        vendors = self._vendors_config()
        probe_config = self.config.get("a0_probe", {})
        sample_symbol = probe_config.get("sample_symbol", "000001")
        sample_start = probe_config.get("sample_hist_start", "20250101")
        sample_end = probe_config.get("sample_hist_end", "20250110")

        probe_results: Dict[str, ProbeResult] = {}
        warnings: List[str] = []

        # ---- Spot Snapshot probes ----
        print("[SCREENER] Stage DataProbe: probing spot_snapshot...", end=" ", flush=True)
        spot_probes = [
            ("spot_tencent_direct", lambda: self._fetch_spot_tencent_direct()),
            ("spot_tencent_akshare", lambda: self._fetch_spot_tencent()),
            ("spot_sina", lambda: self._fetch_spot_sina()),
        ]
        spot_result = self._probe_multi(f"spot_snapshot", spot_probes)
        probe_results.update(spot_result)
        summary["spot_snapshot_verified"] = any(
            r.ok for r in spot_result.values()
        )
        spot_ok = [k for k, v in spot_result.items() if v.ok]
        print(f"{len(spot_ok)}/{len(spot_probes)} passed -> [{', '.join(spot_ok) or 'none'}]")

        # ---- Historical bars probes ----
        print("[SCREENER] Stage DataProbe: probing hist_fetch...", end=" ", flush=True)
        hist_probes = [
            ("hist_tencent_direct", lambda: self._fetch_hist_tencent_direct(
                sample_symbol, sample_start, sample_end)),
            ("hist_tencent_akshare", lambda: self._fetch_hist_tencent(
                sample_symbol, sample_start, sample_end)),
            ("hist_sina", lambda: self._fetch_hist_sina(
                sample_symbol, sample_start, sample_end)),
            ("hist_baostock", lambda: self._fetch_hist_baostock(
                sample_symbol, sample_start, sample_end)),
        ]
        hist_result = self._probe_multi("hist_fetch", hist_probes)
        probe_results.update(hist_result)
        summary["hist_fetch_verified"] = any(r.ok for r in hist_result.values())
        hist_ok = [k for k, v in hist_result.items() if v.ok]
        print(f"{len(hist_ok)}/{len(hist_probes)} passed -> [{', '.join(hist_ok) or 'none'}]")

        # ---- Concept board probes ----
        print("[SCREENER] Stage DataProbe: probing concept_list...", end=" ", flush=True)
        concept_probes = [
            ("concept_ths", lambda: self._fetch_concept_ths()),
            ("concept_sina", lambda: self._fetch_concept_sina()),
        ]
        concept_result = self._probe_multi("concept_list", concept_probes)
        probe_results.update(concept_result)
        summary["concept_list_verified"] = any(
            r.ok for r in concept_result.values()
        )
        concept_ok = [k for k, v in concept_result.items() if v.ok]
        print(f"{len(concept_ok)}/{len(concept_probes)} passed -> [{', '.join(concept_ok) or 'none'}]")

        # ---- Industry board probes ----
        print("[SCREENER] Stage DataProbe: probing industry_list...", end=" ", flush=True)
        industry_probes = [
            ("industry_ths", lambda: self._fetch_industry_ths()),
        ]
        industry_result = self._probe_multi("industry_list", industry_probes)
        probe_results.update(industry_result)
        summary["industry_list_verified"] = any(
            r.ok for r in industry_result.values()
        )
        ind_ok = [k for k, v in industry_result.items() if v.ok]
        print(f"{len(ind_ok)}/{len(industry_probes)} passed -> [{', '.join(ind_ok) or 'none'}]")

        # ---- Fund flow probes ----
        print("[SCREENER] Stage DataProbe: probing fund_flow...", end=" ", flush=True)
        ff_probes = [
            ("fund_flow_ths", lambda: self._fetch_fund_flow_ths(symbol="即时")),
            ("fund_flow_em", lambda: self._fetch_fund_flow_em()),  # H4: em replaces baostock
        ]
        ff_result = self._probe_multi("fund_flow", ff_probes)
        probe_results.update(ff_result)
        summary["fund_flow_verified"] = any(r.ok for r in ff_result.values())
        ff_ok = [k for k, v in ff_result.items() if v.ok]
        print(f"{len(ff_ok)}/{len(ff_probes)} passed -> [{', '.join(ff_ok) or 'none'}]")

        # ---- Index spot probes ----
        print("[SCREENER] Stage DataProbe: probing index_spot...", end=" ", flush=True)
        index_probes = [
            ("index_tencent_direct", lambda: self._fetch_index_tencent_direct()),
            ("index_sina", lambda: self._fetch_index_sina()),
            ("index_tencent_akshare", lambda: self._fetch_index_tencent()),
        ]
        index_result = self._probe_multi("index_spot", index_probes)
        probe_results.update(index_result)
        summary["index_spot_verified"] = any(r.ok for r in index_result.values())
        idx_ok = [k for k, v in index_result.items() if v.ok]
        print(f"{len(idx_ok)}/{len(index_probes)} passed -> [{', '.join(idx_ok) or 'none'}]")

        # ---- Tick data probes ----
        print("[SCREENER] Stage DataProbe: probing tick_data...", end=" ", flush=True)
        tick_probes = [
            ("tick_tencent", lambda: self._fetch_tick_tencent("sz000001")),
            ("tick_sina", lambda: self._fetch_tick_sina("sz000001")),
        ]
        tick_result = self._probe_multi("tick_data", tick_probes)
        probe_results.update(tick_result)
        summary["tick_data_verified"] = any(r.ok for r in tick_result.values())
        tick_ok = [k for k, v in tick_result.items() if v.ok]
        print(f"{len(tick_ok)}/{len(tick_probes)} passed -> [{', '.join(tick_ok) or 'none'}]")

        # ---- yfinance fallback ----
        print("[SCREENER] Stage DataProbe: probing yfinance hist...", end=" ", flush=True)
        if vendors.get("enable_yfinance_backup", True):
            yf_result = self._probe_single(
                "hist_yfinance",
                lambda: self._fetch_hist_yfinance(
                    sample_symbol, sample_start, sample_end
                ),
            )
            probe_results["hist_yfinance"] = yf_result
            if yf_result.ok:
                warnings.append("[INFO] yfinance historical fallback probe succeeded")
            print("passed" if yf_result.ok else "failed")
        else:
            print("skipped")

        # ---- 构建返回摘要 ----
        print("[SCREENER] Stage DataProbe: done")
        failed_count = sum(1 for r in probe_results.values() if not r.ok)
        print(f"[SCREENER] Stage DataProbe: {len(probe_results) - failed_count}/{len(probe_results)} probes passed, {failed_count} failed")
        summary["probe_results"] = {
            k: {
                "name": v.name,
                "ok": v.ok,
                "elapsed": v.elapsed,
                "shape": v.shape,
                "detail": v.detail,
                "classification": v.classification,
                "vendor": v.vendor,
            }
            for k, v in probe_results.items()
        }
        summary["probed_at"] = datetime.now().isoformat()
        summary["request_stats"] = self.requester.get_stats()

        # 生成失败警告
        for result in probe_results.values():
            if not result.ok:
                warnings.append(
                    f"[WARN] {result.name} ({result.vendor}) probe failed: {result.detail[:120]}"
                )

        summary["warnings"] = warnings
        return summary

    def _probe_single(self, name: str, fn: Callable, timeout: float = 30.0) -> ProbeResult:
        """探测单个接口."""
        start = time.time()
        try:
            result = fn()
            elapsed = time.time() - start
            shape = getattr(result, "shape", None) if result is not None else None
            empty = bool(getattr(result, "empty", False)) if result is not None else True
            ok = shape is not None and not empty
            return ProbeResult(
                name=name,
                ok=ok,
                elapsed=elapsed,
                shape=shape,
                detail=f"shape={shape}, empty={empty}" if shape is not None else f"type={type(result).__name__ if result else 'None'}",
                classification="ok" if ok else "empty",
                vendor=name.split("_")[0] if "_" in name else name,
            )
        except Exception as exc:
            elapsed = time.time() - start
            return ProbeResult(
                name=name,
                ok=False,
                elapsed=elapsed,
                detail=repr(exc),
                classification=self._classify_probe_exception(repr(exc)),
                vendor=name.split("_")[0] if "_" in name else name,
            )

    def _probe_multi(
        self, module: str, probes: List[tuple]
    ) -> Dict[str, ProbeResult]:
        """探测多个同功能接口, 返回各接口结果."""
        results = {}
        for name, fn in probes:
            results[name] = self._probe_single(name, fn)
        return results

    def _apply_legacy_capability_aliases(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(summary)
        payload["fund_flow_bulk_verified"] = bool(payload.get("fund_flow_verified", False))
        payload["tencent_hist_verified"] = bool(
            payload.get("probe_results", {}).get("hist_tencent_direct", {}).get("ok", False)
        )
        payload["yfinance_hist_verified"] = bool(
            payload.get("probe_results", {}).get("hist_yfinance", {}).get("ok", False)
        )
        payload["fund_flow_fallback_vendor"] = payload.get("fund_flow_fallback_vendor") or "yfinance"
        payload["concept_list_fallback_vendor"] = payload.get("concept_list_fallback_vendor") or payload.get("concept_secondary_vendor", "")
        payload["hist_fetch_secondary_vendor"] = payload.get("hist_fetch_secondary_vendor") or payload.get("hist_secondary_vendor", "sina")
        payload["hist_fetch_fallback_vendor"] = payload.get("hist_fetch_fallback_vendor") or (
            "yfinance" if self._vendors_config().get("enable_yfinance_backup", True) else ""
        )
        payload["vendor_baseline"] = self._build_vendor_baseline(payload)
        payload["strategy_capabilities"] = self._build_strategy_capabilities(payload)
        return payload

    def _build_vendor_baseline(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "history": {
                "primary": summary.get("hist_primary_vendor", "tencent_direct"),
                "secondary": summary.get("hist_secondary_vendor", "tencent"),
                "tertiary": summary.get("hist_tertiary_vendor", "sina"),
                "quaternary": summary.get("hist_quaternary_vendor", "baostock"),
                "last_resort": "yfinance" if self._vendors_config().get("enable_yfinance_backup", True) else "",
                "eastmoney_role": "compatibility_only",
            },
            "spot": {
                "primary": summary.get("spot_primary_vendor", "tencent_direct"),
                "secondary": summary.get("spot_secondary_vendor", "tencent"),
                "tertiary": summary.get("spot_tertiary_vendor", "sina"),
            },
            "concept": {
                "primary": summary.get("concept_primary_vendor", "ths"),
                "secondary": summary.get("concept_secondary_vendor", "sina"),
            },
            "industry": {
                "primary": summary.get("industry_primary_vendor", "ths"),
            },
            "fund_flow": {
                "primary": summary.get("fund_flow_primary_vendor", "ths"),
                "secondary": summary.get("fund_flow_secondary_vendor", "em"),
            },
            "index": {
                "primary": summary.get("index_primary_vendor", "tencent_direct"),
                "secondary": summary.get("index_secondary_vendor", "sina"),
                "tertiary": summary.get("index_tertiary_vendor", "tencent"),
            },
            "tick": {
                "primary": "tencent",
                "secondary": "sina",
            },
            "auxiliary": {
                "valuation": "baidu",
                "sentiment": "baidu",
                "news": "baidu",
                "dragon_tiger": "sina",
            },
        }

    def _build_strategy_capabilities(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        vendors = self._vendors_config()
        hist_probe = summary.get("probe_results", {}).get("hist_tencent_direct", {})
        yfinance_probe = summary.get("probe_results", {}).get("hist_yfinance", {})
        concept_probe = summary.get("probe_results", {}).get("concept_ths", {})
        fund_flow_probe = summary.get("probe_results", {}).get("fund_flow_ths", {})

        technical_ready = bool(
            summary.get("fund_flow_verified", False) and summary.get("hist_fetch_verified", False)
        )
        policy_ready = bool(summary.get("concept_list_verified", False))
        smart_money_ready = bool(summary.get("hist_fetch_verified", False))

        return {
            "technical": {
                "status_hint": "ready" if technical_ready else "degraded",
                "required_capabilities": ["fund_flow", "hist_fetch"],
                "primary_dependencies": {
                    "fund_flow": summary.get("fund_flow_primary_vendor", "ths"),
                    "hist_fetch": summary.get("hist_primary_vendor", "tencent"),
                },
                "supports_tencent_primary_hist": summary.get("hist_primary_vendor", "tencent_direct") == "tencent_direct",
                "supports_yfinance_last_resort": bool(vendors.get("enable_yfinance_backup", True)),
                "notes": [
                    "Technical strategy should treat Tencent history as the canonical CN historical path.",
                    "THS fund flow remains required for full technical+flow readiness.",
                ],
            },
            "policy": {
                "status_hint": "ready" if policy_ready else "degraded",
                "required_capabilities": ["concept_list"],
                "primary_dependencies": {
                    "concept_list": summary.get("concept_primary_vendor", "ths"),
                    "concept_fallback": summary.get("concept_secondary_vendor", "sina"),
                    "news_auxiliary": "baidu",
                },
                "supports_tencent_primary_hist": False,
                "supports_yfinance_last_resort": False,
                "concept_source_verified": bool(concept_probe.get("ok", False)),
                "news_source_planned": "baidu",
                "notes": [
                    "Policy strategy does not require Tencent history to be ready.",
                    "Concept boards remain THS-first, with Sina as compatibility fallback.",
                ],
            },
            "smart_money": {
                "status_hint": "ready" if smart_money_ready else "degraded",
                "required_capabilities": ["hist_fetch"],
                "optional_capabilities": ["fund_flow", "tick_data", "valuation_auxiliary"],
                "primary_dependencies": {
                    "hist_fetch": summary.get("hist_primary_vendor", "tencent"),
                    "fund_flow": summary.get("fund_flow_primary_vendor", "ths"),
                    "tick_data": "tencent",
                    "valuation_auxiliary": "baidu",
                    "dragon_tiger_auxiliary": "sina",
                },
                "supports_tencent_primary_hist": bool(hist_probe.get("ok", False))
                or summary.get("hist_primary_vendor", "tencent") == "tencent",
                "supports_yfinance_last_resort": bool(vendors.get("enable_yfinance_backup", True)),
                "tencent_hist_verified": bool(hist_probe.get("ok", False)),
                "yfinance_hist_verified": bool(yfinance_probe.get("ok", False)),
                "fund_flow_verified": bool(fund_flow_probe.get("ok", False) or summary.get("fund_flow_verified", False)),
                "notes": [
                    "Smart-money minimum viable path is Tencent history plus optional Tencent tick detail.",
                    "THS/Sina/Baidu remain enhancement sources rather than hard blockers for MVP.",
                ],
            },
        }

    def _maybe_spoof_headers(self):
        if self._vendors_config().get("spoof_browser_headers", True):
            return patch_requests_browser_headers()
        return nullcontext()

    def _sleep_for_vendor(self, vendor: str) -> None:
        interval_map = {
            "sina": self._ds_config.sina_page_interval,
            "ths": self._ds_config.ths_interval,
            "tencent": 1.0,
            "baostock": 0.5,
            "baidu": 0.7,
        }
        base = float(interval_map.get(vendor, 0.5))
        jitter = random.uniform(0.0, max(0.0, self._ds_config.random_jitter))
        time.sleep(base + jitter)

    @staticmethod
    def _classify_probe_exception(text: str) -> str:
        lowered = text.lower()
        if "winerror 10013" in lowered or "winerror 10054" in lowered:
            return "network_blocked"
        if "remote end closed" in lowered or "remote end closed connection" in lowered:
            return "remote_closed"
        if "failed to establish a new connection" in lowered:
            return "connection_failed"
        if "maxretryerror" in lowered or "httpsconnectionpool" in lowered:
            return "network_unreachable"
        if "yfratelimit" in lowered or "too many requests" in lowered:
            return "rate_limited"
        if "unable to open database file" in lowered:
            return "local_runtime_error"
        if "syntaxerror" in lowered or "json" in lowered:
            return "parse_error"
        if "timeout" in lowered or "timed out" in lowered:
            return "timeout"
        return "unknown_error"

    # -------------------------------------------------------------------------
    # 内部: 缓存系统
    # -------------------------------------------------------------------------

    def _load_or_run_probes(self, trade_date: str | None = None) -> Dict[str, Any]:
        if self._probe_cache is not None:
            if trade_date is not None:
                self._probe_cache["trade_date"] = trade_date
                self._probe_cache["validated"] = True
            return self._probe_cache

        cached = self._load_probe_cache()
        if cached is not None:
            if trade_date is not None:
                cached["trade_date"] = trade_date
                cached["validated"] = True
            self._probe_cache = cached
            return cached

        summary = (
            self._run_live_probes()
            if self._live_probe_enabled()
            else self.get_interface_capability_summary()
        )
        if trade_date is not None:
            summary["trade_date"] = trade_date
            summary["validated"] = True
        self._save_probe_cache(summary)
        self._probe_cache = summary
        return summary

    def _live_probe_enabled(self) -> bool:
        return bool(self.config.get("a0_probe", {}).get("enable_live_probes", True))

    def _probe_cache_path(self) -> Path:
        cache_root = Path(self.config.get("data_cache_dir", DEFAULT_CONFIG["data_cache_dir"]))
        candidates = [
            cache_root / "screener",
            Path.cwd() / ".tradingagents" / "cache" / "screener",
        ]
        for candidate in candidates:
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                return candidate / "a0_probe_summary_v2.json"
            except OSError:
                continue
        return Path.cwd() / "a0_probe_summary_v2.json"

    def _load_probe_cache(self) -> Dict[str, Any] | None:
        cache_file = self._probe_cache_path()
        if not cache_file.exists():
            return None

        try:
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            created_at = payload.get("probed_at")
            ttl_minutes = int(self.config.get("a0_probe", {}).get("cache_ttl_minutes", 60))
            if created_at:
                probed_at = datetime.fromisoformat(created_at)
                if datetime.now() - probed_at > timedelta(minutes=ttl_minutes):
                    return None
            # 填充默认值
            defaults = {
                "spot_snapshot_verified": False,
                "hist_fetch_verified": False,
                "concept_list_verified": False,
                "industry_list_verified": False,
                "fund_flow_verified": False,
                "index_spot_verified": False,
                "tick_data_verified": False,
                "spot_primary_vendor": "tencent_direct",
                "hist_primary_vendor": "tencent_direct",
                "concept_primary_vendor": "ths",
                "industry_primary_vendor": "ths",
                "fund_flow_primary_vendor": "ths",
                "index_primary_vendor": "tencent_direct",
                "baostock_importable": False,
                "tushare_importable": False,
                "py_mini_racer_importable": False,
                "tushare_configured": bool(self._tushare_token),
            }
            for k, v in defaults.items():
                payload.setdefault(k, v)
            payload.setdefault("validated", False)
            return payload
        except Exception:
            return None

    def _save_probe_cache(self, summary: Dict[str, Any]) -> None:
        cache_file = self._probe_cache_path()
        try:
            cache_file.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    # -------------------------------------------------------------------------
    # 内部: 工具方法
    # -------------------------------------------------------------------------

    def _vendors_config(self) -> Dict[str, Any]:
        merged = dict(self.DEFAULT_VENDORS)
        merged.update(self.config.get("vendors", {}))
        return merged

    def _check_libraries(self) -> Dict[str, bool]:
        libs = {}
        for lib, module_name in [
            ("akshare", "akshare"),
            ("baostock", "baostock"),
            ("tushare", "tushare"),
            ("py_mini_racer", "py_mini_racer"),
        ]:
            try:
                __import__(module_name)
                libs[lib] = True
            except Exception:
                libs[lib] = False
        return libs

    def _load_tushare_token(self) -> str:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except Exception:
            pass
        return os.environ.get("TUSHARE_TOKEN", "")

    def _normalize_ticker_for_sina(self, ticker: str) -> str:
        """转换代码为 Sina 格式 (sh600519 / sz000001).

        Handles: 000001, sh600519, sz000001, sh600519, 600519, 600519.SS, 000001.SZ
        """
        t = ticker.strip()
        lower = t.lower()

        # 直接识别前缀
        if lower.startswith("sh"):
            return f"sh{t[2:]}"  # sh600519
        if lower.startswith("sz"):
            return f"sz{t[2:]}"  # sz000001
        if lower.startswith("bj"):
            return f"bj{t[2:]}"  # bj000001

        # yfinance 格式: 600519.SS / 000001.SZ
        if "." in t:
            code, suffix = t.split(".", 1)
            suffix = suffix.upper()
            if suffix in ("XSHG", "SS", "SH"):
                return f"sh{code}"
            if suffix in ("XSHE", "SZ"):
                return f"sz{code}"
            if suffix in ("BJ", "BSE"):
                return f"bj{code}"

        # 纯数字: 判断市场 (保留原始数字)
        if t.startswith(("6", "9")):
            return f"sh{t}"
        return f"sz{t}"

    def _normalize_ticker_for_tencent(self, ticker: str) -> tuple:
        """转换代码为腾讯格式 (sz000001 / sh600519).

        Handles: 000001, sz000001, sh600519, 600519.SS, 000001.SZ
        """
        t = ticker.strip()
        lower = t.lower()

        # 先尝试识别市场前缀
        if lower.startswith("sh"):
            code = t[2:] or t[2:]
            return code, "sh"
        if lower.startswith("sz"):
            code = t[2:] or t[2:]
            return code, "sz"
        if lower.startswith("bj"):
            code = t[2:] or t[2:]
            return code, "bj"

        # 处理 yfinance 格式: 600519.SS / 000001.SZ
        if "." in t:
            code, suffix = t.split(".", 1)
            suffix = suffix.upper()
            if suffix in ("XSHG", "SS", "SH"):
                return code, "sh"
            if suffix in ("XSHE", "SZ"):
                return code, "sz"

        # 纯数字: 判断市场
        if t.startswith(("6", "9")):
            return t, "sh"
        return t, "sz"

    def _normalize_ticker_for_baostock(self, ticker: str) -> str:
        """转换代码为 Baostock 格式 (sh.600519 / sz.000001).

        Handles: 000001, sz000001, sh600519, 600519.SS, 000001.SZ, sz.000001
        """
        t = ticker.strip()

        # 直接处理带前缀格式
        lower = t.lower()
        if lower.startswith("sh."):
            code = t[3:]
            return f"sh.{code}" if code else "sh."
        if lower.startswith("sz."):
            code = t[3:]
            return f"sz.{code}" if code else "sz."
        if lower.startswith("bj."):
            code = t[3:]
            return f"bj.{code}" if code else "bj."

        # 处理无点前缀格式 sh600519 / sz000001
        if lower.startswith("sh"):
            code = t[2:]  # 保留所有字符包括0
            return f"sh.{code}"
        if lower.startswith("sz"):
            code = t[2:]
            return f"sz.{code}"
        if lower.startswith("bj"):
            code = t[2:]
            return f"bj.{code}"

        # 处理 yfinance 格式: 600519.SS / 000001.SZ
        if "." in t:
            code, suffix = t.split(".", 1)
            suffix = suffix.upper()
            if suffix in ("XSHG", "SS", "SH"):
                return f"sh.{code}"
            if suffix in ("XSHE", "SZ"):
                return f"sz.{code}"
            if suffix in ("BJ", "BSE"):
                return f"bj.{code}"
            return t

        # 纯数字: 判断市场 (保留原始数字)
        if t.startswith(("6", "9")):
            return f"sh.{t}"
        return f"sz.{t}"

    def _normalize_ticker_for_yfinance(self, ticker: str) -> str:
        """转换代码为 yfinance 格式 (600519.SS / 000001.SZ)."""
        t = ticker.strip()
        lower = t.lower()

        if lower.startswith(("sh", "sz", "bj")):
            code = t[2:]
            if lower.startswith("sh"):
                return f"{code}.SS"
            return f"{code}.SZ"
        if "." in t:
            return ticker.strip()  # 已经是 600519.SS 格式
        # 纯数字
        if t.startswith(("6", "9")):
            return f"{t}.SS"
        return f"{t}.SZ"

    @staticmethod
    def _normalize_yfinance_hist_frame(df):
        if df is None or getattr(df, "empty", True):
            return df
        normalized = df.copy()
        try:
            normalized.index = normalized.index.astype(str)
        except Exception:
            pass
        return normalized
