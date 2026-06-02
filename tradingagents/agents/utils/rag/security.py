"""
RAG安全模块。

提供安全性检查和防护功能：
1. 输入验证
2. Prompt注入检测
3. 敏感信息过滤
4. API密钥检查
5. 速率限制
"""

import re
import os
import logging
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import time

logger = logging.getLogger(__name__)


# ============================================================================
# 安全配置
# ============================================================================

class SecurityLevel(Enum):
    """安全级别."""
    DISABLED = "disabled"
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"


@dataclass
class SecurityConfig:
    """安全配置."""
    # 启用状态
    enabled: bool = True
    level: SecurityLevel = SecurityLevel.STANDARD

    # 输入验证
    max_query_length: int = 1000
    max_ticker_length: int = 20
    max_date_range_days: int = 365
    allowed_ticker_pattern: str = r"^[A-Z0-9\.\-]+$"

    # Prompt注入检测
    enable_injection_detection: bool = True
    injection_patterns: List[str] = field(default_factory=lambda: [
        r"(?i)(ignore\s+(previous|above|all)\s+(instructions?|rules?|prompts?))",
        r"(?i)(forget\s+(everything|all|what)\s+(you|i)\s+(know|learned))",
        r"(?i)(you\s+are\s+now\s+(a|an)\s+)",
        r"(?i)(pretend\s+you\s+(are|were)\s+)",
        r"(?i)(disregard\s+(your|all)\s+(instructions?|constraints?))",
        r"(?i)(new\s+instructions?:)",
        r"(?i)(system\s*:\s*)",
        r"(?i)(\<\|system\|\>)",
        r"(?i)(\n\n\n)",
    ])

    # 敏感信息过滤
    enable_pii_detection: bool = True
    pii_patterns: Dict[str, str] = field(default_factory=lambda: {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "api_key": r"\b[A-Za-z0-9]{32,}\b",  # 通用长API密钥模式
    })

    # API密钥检查
    check_api_keys: bool = True
    required_env_vars: List[str] = field(default_factory=lambda: [
        "OPENAI_API_KEY",
        # 添加其他必需的API密钥
    ])

    # 速率限制
    enable_rate_limit: bool = True
    max_requests_per_minute: int = 60
    max_requests_per_day: int = 10000

    def __post_init__(self):
        if isinstance(self.level, str):
            self.level = SecurityLevel(self.level)


# ============================================================================
# 安全检查结果
# ============================================================================

@dataclass
class SecurityResult:
    """安全检查结果."""
    passed: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    sanitized_input: Optional[str] = None

    def __bool__(self):
        return self.passed and not self.errors


# ============================================================================
# 输入验证器
# ============================================================================

class InputValidator:
    """输入验证器."""

    def __init__(self, config: SecurityConfig = None):
        self.config = config or SecurityConfig()

    def validate_query(self, query: str) -> SecurityResult:
        """
        验证查询输入.

        Args:
            query: 用户查询字符串

        Returns:
            SecurityResult: 验证结果
        """
        result = SecurityResult(passed=True)

        if not query:
            result.errors.append("Query cannot be empty")
            result.passed = False
            return result

        # 检查长度
        if len(query) > self.config.max_query_length:
            result.warnings.append(
                f"Query too long ({len(query)} > {self.config.max_query_length}), truncating"
            )
            result.sanitized_input = query[:self.config.max_query_length]
        else:
            result.sanitized_input = query

        # 检查注入模式
        if self.config.enable_injection_detection:
            injection_result = self._check_injection(result.sanitized_input)
            if injection_result:
                result.warnings.append(f"Potential injection detected: {injection_result}")

        # 检查PII
        if self.config.enable_pii_detection:
            pii_found = self._check_pii(result.sanitized_input)
            if pii_found:
                result.warnings.append(f"Potential sensitive data detected: {', '.join(pii_found)}")
                result.sanitized_input = self._redact_pii(result.sanitized_input)

        return result

    def validate_ticker(self, ticker: str) -> SecurityResult:
        """
        验证股票代码.

        Args:
            ticker: 股票代码

        Returns:
            SecurityResult: 验证结果
        """
        result = SecurityResult(passed=True)

        if not ticker:
            result.errors.append("Ticker cannot be empty")
            result.passed = False
            return result

        # 检查长度
        if len(ticker) > self.config.max_ticker_length:
            result.errors.append(
                f"Ticker too long ({len(ticker)} > {self.config.max_ticker_length})"
            )
            result.passed = False
            return result

        # 检查格式
        pattern = re.compile(self.config.allowed_ticker_pattern)
        if not pattern.match(ticker.upper()):
            result.errors.append(
                f"Invalid ticker format: {ticker}. Allowed: A-Z, 0-9, ., -"
            )
            result.passed = False
            return result

        result.sanitized_input = ticker.upper()
        return result

    def validate_date_range(
        self,
        start_date: str,
        end_date: str
    ) -> SecurityResult:
        """
        验证日期范围.

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            SecurityResult: 验证结果
        """
        result = SecurityResult(passed=True)

        # 日期格式检查
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")

        if not date_pattern.match(start_date):
            result.errors.append(f"Invalid start date format: {start_date}. Use YYYY-MM-DD")
            result.passed = False

        if not date_pattern.match(end_date):
            result.errors.append(f"Invalid end date format: {end_date}. Use YYYY-MM-DD")
            result.passed = False

        if not result.passed:
            return result

        # 计算天数差
        from datetime import datetime
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            days = (end - start).days

            if days < 0:
                result.errors.append("Start date must be before end date")
                result.passed = False
            elif days > self.config.max_date_range_days:
                result.warnings.append(
                    f"Date range too large ({days} > {self.config.max_date_range_days}), limiting"
                )
                # 自动调整
                from datetime import timedelta
                result.sanitized_input = end_date
        except ValueError as e:
            result.errors.append(f"Invalid date: {e}")
            result.passed = False

        return result

    def _check_injection(self, text: str) -> Optional[str]:
        """检查Prompt注入模式."""
        text_lower = text.lower()

        for pattern in self.config.injection_patterns:
            if re.search(pattern, text_lower):
                # 返回匹配的模式（不返回敏感内容）
                return pattern[:50] + "..."

        return None

    def _check_pii(self, text: str) -> List[str]:
        """检查敏感信息."""
        found = []

        for pii_type, pattern in self.config.pii_patterns.items():
            if re.search(pattern, text):
                found.append(pii_type)

        return found

    def _redact_pii(self, text: str) -> str:
        """脱敏敏感信息."""
        redacted = text

        for pii_type, pattern in self.config.pii_patterns.items():
            redacted = re.sub(pattern, f"[{pii_type}_REDACTED]", redacted)

        return redacted


# ============================================================================
# API密钥检查器
# ============================================================================

class APIKeyChecker:
    """API密钥检查器."""

    def __init__(self, config: SecurityConfig = None):
        self.config = config or SecurityConfig()
        self._checked_keys: Dict[str, bool] = {}

    def check_required_keys(self) -> Tuple[bool, List[str]]:
        """
        检查必需的API密钥.

        Returns:
            (all_present, missing_keys)
        """
        if not self.config.check_api_keys:
            return True, []

        missing = []

        for key in self.config.required_env_vars:
            if key not in os.environ or not os.environ[key]:
                missing.append(key)

        return len(missing) == 0, missing

    def check_key_format(self, key_name: str, key_value: str) -> SecurityResult:
        """
        检查密钥格式是否有效.

        Args:
            key_name: 密钥名称
            key_value: 密钥值

        Returns:
            SecurityResult: 检查结果
        """
        result = SecurityResult(passed=True)

        if not key_value:
            result.errors.append(f"{key_name} is empty")
            result.passed = False
            return result

        # 检查是否为默认值或占位符
        placeholders = ["your_key_here", "sk-xxx", "test", "placeholder", "-key-"]
        if any(p in key_value.lower() for p in placeholders):
            result.errors.append(f"{key_name} appears to be a placeholder")
            result.passed = False
            return result

        # 检查是否包含可疑字符
        if re.search(r'[<>"\']', key_value):
            result.errors.append(f"{key_name} contains suspicious characters")
            result.passed = False
            return result

        # 通用格式检查
        if len(key_value) < 10:
            result.errors.append(f"{key_name} too short")
            result.passed = False

        return result


# ============================================================================
# 速率限制器
# ============================================================================

class RateLimiter:
    """简单的速率限制器."""

    def __init__(self, config: SecurityConfig = None):
        self.config = config or SecurityConfig()
        self._request_times: List[float] = []
        self._daily_counts: Dict[str, int] = {}
        self._last_reset_day: int = 0

    def check_rate_limit(self, identifier: str = "default") -> Tuple[bool, Optional[str]]:
        """
        检查速率限制.

        Args:
            identifier: 请求标识符

        Returns:
            (allowed, reason_if_blocked)
        """
        if not self.config.enable_rate_limit:
            return True, None

        current_time = time.time()
        current_day = int(current_time // 86400)

        # 每日重置
        if current_day > self._last_reset_day:
            self._daily_counts.clear()
            self._last_reset_day = current_day

        # 清理超过1分钟的请求记录
        self._request_times = [
            t for t in self._request_times
            if current_time - t < 60
        ]

        # 检查每分钟限制
        if len(self._request_times) >= self.config.max_requests_per_minute:
            return False, "Rate limit exceeded (per minute)"

        # 检查每日限制
        daily_count = self._daily_counts.get(identifier, 0)
        if daily_count >= self.config.max_requests_per_day:
            return False, "Rate limit exceeded (per day)"

        # 记录请求
        self._request_times.append(current_time)
        self._daily_counts[identifier] = daily_count + 1

        return True, None

    def get_remaining(self, identifier: str = "default") -> Dict[str, int]:
        """获取剩余配额."""
        current_time = time.time()

        recent_requests = sum(
            1 for t in self._request_times
            if current_time - t < 60
        )

        daily_count = self._daily_counts.get(identifier, 0)

        return {
            "requests_per_minute_remaining": max(0, self.config.max_requests_per_minute - recent_requests),
            "requests_per_day_remaining": max(0, self.config.max_requests_per_day - daily_count),
        }


# ============================================================================
# 安全检查装饰器
# ============================================================================

def secure_operation(validator: InputValidator = None):
    """
    安全操作装饰器.

    用法:
        @secure_operation()
        def process_query(query: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            config = SecurityConfig() if validator is None else validator.config

            if not config.enabled:
                return func(*args, **kwargs)

            # 获取第一个字符串参数作为查询
            query = kwargs.get("query") or (args[0] if args and isinstance(args[0], str) else None)

            if query:
                val = validator or InputValidator(config)
                result = val.validate_query(query)

                if not result.passed:
                    raise ValueError(f"Security validation failed: {result.errors}")

                if result.sanitized_input != query:
                    logger.warning(f"Input was sanitized: {result.warnings}")

            return func(*args, **kwargs)

        return wrapper
    return decorator


# ============================================================================
# 全局安全实例
# ============================================================================

_security_config: Optional[SecurityConfig] = None
_validator: Optional[InputValidator] = None
_rate_limiter: Optional[RateLimiter] = None


def get_security_config() -> SecurityConfig:
    """获取或创建安全配置."""
    global _security_config
    if _security_config is None:
        # 从环境变量加载配置
        level = os.environ.get("TRADINGAGENTS_SECURITY_LEVEL", "standard")
        _security_config = SecurityConfig(
            level=SecurityLevel(level.lower()),
            enabled=os.environ.get("TRADINGAGENTS_SECURITY_ENABLED", "true").lower() == "true",
        )
    return _security_config


def get_validator() -> InputValidator:
    """获取或创建输入验证器."""
    global _validator
    if _validator is None:
        _validator = InputValidator(get_security_config())
    return _validator


def get_rate_limiter() -> RateLimiter:
    """获取或创建速率限制器."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(get_security_config())
    return _rate_limiter


def check_api_keys() -> Tuple[bool, List[str]]:
    """检查API密钥（便捷函数）."""
    checker = APIKeyChecker(get_security_config())
    return checker.check_required_keys()


def validate_input(
    query: str = None,
    ticker: str = None,
    start_date: str = None,
    end_date: str = None,
) -> SecurityResult:
    """
    验证输入（便捷函数）.

    Args:
        query: 查询字符串
        ticker: 股票代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        SecurityResult: 验证结果
    """
    validator = get_validator()
    result = SecurityResult(passed=True)

    if query is not None:
        query_result = validator.validate_query(query)
        if not query_result.passed:
            result.errors.extend(query_result.errors)
            result.passed = False
        if query_result.warnings:
            result.warnings.extend(query_result.warnings)

    if ticker is not None:
        ticker_result = validator.validate_ticker(ticker)
        if not ticker_result.passed:
            result.errors.extend(ticker_result.errors)
            result.passed = False

    if start_date is not None and end_date is not None:
        date_result = validator.validate_date_range(start_date, end_date)
        if not date_result.passed:
            result.errors.extend(date_result.errors)
            result.passed = False

    return result
