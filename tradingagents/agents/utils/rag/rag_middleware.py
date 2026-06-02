"""
RAG增强中间件。

自动拦截新闻类工具调用，根据配置进行RAG增强。
提供智能结果合并，无需修改原有工具代码。

使用方式:
    from tradingagents.agents.utils.rag.rag_middleware import RAGMiddleware

    # 创建中间件
    middleware = RAGMiddleware()

    # 方式1: 自动拦截
    result = middleware.execute("get_news", ticker="AAPL", start_date="2025-01-01")

    # 方式2: 显式RAG增强
    result = middleware.execute_with_rag("get_news", ticker="AAPL")
"""

import os
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from tradingagents.dataflows.interface import route_to_vendor

logger = logging.getLogger(__name__)


class MergeStrategy(Enum):
    """RAG与原始数据的合并策略."""
    PREFIX = "prefix"           # RAG结果在前
    APPEND = "append"           # RAG结果在后
    INTERLEAVE = "interleave"   # 交替混合
    BEST_SCORE = "best_score"   # 只保留高分结果


@dataclass
class RAGMiddlewareConfig:
    """RAG中间件配置."""
    enabled: bool = True
    auto_intercept: bool = True  # 自动拦截新闻类工具

    # 拦截哪些方法
    intercept_methods: Tuple[str, ...] = (
        "get_news",
        "get_global_news",
        "get_cn_tech_sector_news",
        "get_cn_new_energy_news",
        "get_cn_pharma_news",
        "get_cn_real_estate_news",
        "get_cn_fintech_news",
        "get_cn_policy_news",
    )

    # 合并策略
    merge_strategy: MergeStrategy = MergeStrategy.PREFIX

    # 合并比例 (RAG结果占的字符比例)
    rag_ratio: float = 0.6

    # RAG结果最大字符数
    max_rag_chars: int = 2000

    # 原始结果最大字符数
    max_raw_chars: int = 2000

    @classmethod
    def from_env(cls) -> "RAGMiddlewareConfig":
        """从环境变量创建配置."""
        return cls(
            enabled=os.environ.get("TRADINGAGENTS_RAG_ENABLED", "false").lower() in ("true", "1", "yes"),
            auto_intercept=os.environ.get("TRADINGAGENTS_RAG_AUTO_INTERCEPT", "true").lower() in ("true", "1", "yes"),
            merge_strategy=MergeStrategy(
                os.environ.get("TRADINGAGENTS_RAG_MERGE_STRATEGY", "prefix")
            ),
            rag_ratio=float(os.environ.get("TRADINGAGENTS_RAG_RATIO", "0.6")),
            max_rag_chars=int(os.environ.get("TRADINGAGENTS_RAG_MAX_CHARS", "2000")),
            max_raw_chars=int(os.environ.get("TRADINGAGENTS_RAG_MAX_RAW_CHARS", "2000")),
        )


class RAGMiddleware:
    """
    RAG增强中间件。

    提供三种使用模式:
    1. auto_intercept: 自动拦截并增强所有新闻类工具调用
    2. execute_with_rag: 显式指定使用RAG增强
    3. execute: 根据配置决定是否增强

    集成安全检查:
    - 自动验证输入参数
    - 检测Prompt注入
    - 过滤敏感信息
    """

    def __init__(self, config: RAGMiddlewareConfig = None, enable_security: bool = True):
        """
        初始化中间件.

        Args:
            config: 配置对象, None则从环境变量加载
            enable_security: 是否启用安全检查 (默认启用)
        """
        self.config = config or RAGMiddlewareConfig.from_env()
        self._retriever = None
        self._initialized = False
        self._enable_security = enable_security
        self._validator = None
        self._rate_limiter = None

    def _get_validator(self):
        """获取验证器 (延迟加载)."""
        if self._validator is None and self._enable_security:
            try:
                from tradingagents.agents.utils.rag.security import get_validator
                self._validator = get_validator()
            except ImportError:
                self._enable_security = False
        return self._validator

    def _get_rate_limiter(self):
        """获取速率限制器 (延迟加载)."""
        if self._rate_limiter is None and self._enable_security:
            try:
                from tradingagents.agents.utils.rag.security import get_rate_limiter
                self._rate_limiter = get_rate_limiter()
            except ImportError:
                self._enable_security = False
        return self._rate_limiter

    def _validate_input(self, method: str, kwargs: Dict[str, Any]) -> Tuple[bool, str]:
        """
        验证输入安全性.

        Returns:
            (is_valid, error_message)
        """
        validator = self._get_validator()
        if validator is None:
            return True, ""

        # 检查速率限制
        rate_limiter = self._get_rate_limiter()
        if rate_limiter:
            allowed, reason = rate_limiter.check_rate_limit(method)
            if not allowed:
                return False, f"Rate limit exceeded: {reason}"

        # 验证ticker
        ticker = kwargs.get("ticker")
        if ticker:
            result = validator.validate_ticker(ticker)
            if not result.passed:
                return False, f"Invalid ticker: {result.errors[0] if result.errors else 'validation failed'}"

        # 验证日期范围
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        if start_date and end_date:
            result = validator.validate_date_range(start_date, end_date)
            if not result.passed:
                return False, f"Invalid date range: {result.errors[0] if result.errors else 'validation failed'}"

        # 验证查询内容 (如果有)
        query = kwargs.get("query")
        if query:
            result = validator.validate_query(query)
            if not result.passed:
                return False, f"Invalid query: {result.errors[0] if result.errors else 'validation failed'}"

        return True, ""

    def _init_rag(self):
        """延迟初始化RAG组件."""
        if self._initialized or not self.config.enabled:
            return

        try:
            from tradingagents.agents.utils.rag import get_cn_news_retriever
            self._retriever = get_cn_news_retriever()
            self._initialized = True
            logger.info("RAG middleware initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize RAG: {e}")
            self._initialized = True  # Mark as initialized to avoid retry

    def _should_intercept(self, method: str) -> bool:
        """检查是否应该拦截该方法."""
        if not self.config.enabled or not self.config.auto_intercept:
            return False
        return method in self.config.intercept_methods

    def _get_rag_results(
        self,
        method: str,
        kwargs: Dict[str, Any],
    ) -> Optional[str]:
        """获取RAG增强结果."""
        if not self.config.enabled:
            return None

        self._init_rag()

        if self._retriever is None:
            return None

        try:
            ticker = kwargs.get("ticker")
            start_date = kwargs.get("start_date") or ""
            end_date = kwargs.get("end_date") or ""
            look_back_days = kwargs.get("look_back_days", 7)

            # 构建查询
            query = self._build_query(method, ticker, kwargs)

            # 日期范围
            date_range = None
            if start_date and end_date:
                date_range = (start_date, end_date)

            # 执行检索
            if method.startswith("get_cn_"):
                results = self._retriever.retrieve_sector_news(
                    sector=self._extract_sector(method),
                    query=query,
                    lookback_days=look_back_days,
                    top_k=10,
                )
            else:
                results = self._retriever.retrieve(
                    query=query,
                    ticker=ticker,
                    date_range=date_range,
                    top_k=10,
                )

            if results:
                return self._retriever.format_for_llm_context(
                    results,
                    max_results=10,
                    max_chars_per_result=self.config.max_rag_chars // 10,
                )

        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")

        return None

    def _build_query(self, method: str, ticker: str, kwargs: Dict) -> str:
        """构建RAG查询."""
        parts = []
        if ticker:
            parts.append(str(ticker))
        if method == "get_global_news":
            parts.append(kwargs.get("topic", "market"))
        elif method == "get_cn_policy_news":
            parts.append("政策 监管")
        return " ".join(parts) if parts else (ticker or "")

    def _extract_sector(self, method: str) -> str:
        """从方法名提取行业."""
        sector_map = {
            "get_cn_tech_sector_news": "tech",
            "get_cn_new_energy_news": "new_energy",
            "get_cn_pharma_news": "pharma",
            "get_cn_real_estate_news": "real_estate",
            "get_cn_fintech_news": "fintech",
        }
        return sector_map.get(method, "")

    def _merge_results(self, rag_result: str, raw_result: str) -> str:
        """合并RAG和原始结果."""
        if not rag_result:
            return raw_result
        if not raw_result:
            return rag_result

        # 截断
        rag_truncated = rag_result[:self.config.max_rag_chars]
        raw_truncated = raw_result[:self.config.max_raw_chars]

        # 根据策略合并
        if self.config.merge_strategy == MergeStrategy.PREFIX:
            return f"{rag_truncated}\n\n{'='*50}\n\n{raw_truncated}"
        elif self.config.merge_strategy == MergeStrategy.APPEND:
            return f"{raw_truncated}\n\n{'='*50}\n\n{rag_truncated}"
        elif self.config.merge_strategy == MergeStrategy.INTERLEAVE:
            return self._interleave_results(rag_truncated, raw_truncated)
        else:  # BEST_SCORE
            # 只保留RAG结果（假设RAG质量更高）
            return rag_truncated

    def _interleave_results(self, rag: str, raw: str) -> str:
        """交替混合RAG和原始结果."""
        rag_lines = rag.split("\n")
        raw_lines = raw.split("\n")

        result = []
        result.append("=== RAG增强 ===")
        result.append(rag[:len(rag)//2])  # RAG前半部分
        result.append("\n=== 原始数据 ===")
        result.append(raw[:len(raw)//2])  # Raw前半部分
        result.append("\n=== RAG增强(续) ===")
        result.append(rag[len(rag)//2:])  # RAG后半部分
        result.append("\n=== 原始数据(续) ===")
        result.append(raw[len(raw)//2:])  # Raw后半部分

        return "".join(result)

    def execute(
        self,
        method: str,
        *args,
        **kwargs,
    ) -> str:
        """
        执行工具调用，自动决定是否使用RAG增强.

        Args:
            method: 工具方法名
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            工具结果（可能被RAG增强）
        """
        # 安全检查
        is_valid, error_msg = self._validate_input(method, kwargs)
        if not is_valid:
            logger.warning(f"Security validation failed for {method}: {error_msg}")
            return f"[Security Error] {error_msg}"

        # 获取原始结果
        raw_result = route_to_vendor(method, *args, **kwargs)

        # 检查是否应该RAG增强
        if not self._should_intercept(method):
            return raw_result

        # 获取RAG结果
        rag_result = self._get_rag_results(method, kwargs)

        # 合并
        return self._merge_results(rag_result, raw_result)

    def execute_with_rag(
        self,
        method: str,
        *args,
        **kwargs,
    ) -> str:
        """
        强制使用RAG增强执行工具调用.

        Args:
            method: 工具方法名
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            RAG增强后的结果
        """
        # 安全检查
        is_valid, error_msg = self._validate_input(method, kwargs)
        if not is_valid:
            logger.warning(f"Security validation failed for {method}: {error_msg}")
            return f"[Security Error] {error_msg}"

        # 强制初始化RAG
        self._init_rag()

        # 获取RAG结果
        rag_result = self._get_rag_results(method, kwargs)
        self._init_rag()

        # 获取原始结果
        raw_result = route_to_vendor(method, *args, **kwargs)

        # 获取RAG结果
        rag_result = self._get_rag_results(method, kwargs)

        # 合并
        return self._merge_results(rag_result, raw_result)

    def execute_raw(
        self,
        method: str,
        *args,
        **kwargs,
    ) -> str:
        """
        执行工具调用，不使用RAG增强.

        Args:
            method: 工具方法名
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            原始结果（无RAG增强）
        """
        return route_to_vendor(method, *args, **kwargs)


# 全局中间件实例
_middleware: Optional[RAGMiddleware] = None


def get_middleware(config: RAGMiddlewareConfig = None) -> RAGMiddleware:
    """获取全局中间件实例."""
    global _middleware
    if _middleware is None or config is not None:
        _middleware = RAGMiddleware(config)
    return _middleware


def rag_execute(method: str, *args, **kwargs) -> str:
    """快捷函数：使用RAG增强执行."""
    return get_middleware().execute_with_rag(method, *args, **kwargs)
