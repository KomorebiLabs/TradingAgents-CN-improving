"""Pure ticker-format conversion functions.

One reason to change: a vendor changes its symbol format. No I/O, no state —
every function is trivially unit-testable.

Extracted from ScreenerDataAccess (data_access.py) during the Phase 4 split.
"""

from __future__ import annotations

__all__ = [
    "safe_float",
    "normalize_date_for_tencent",
    "normalize_ticker_for_sina",
    "normalize_ticker_for_tencent",
    "normalize_ticker_for_baostock",
    "normalize_ticker_for_yfinance",
]


def safe_float(val) -> float | None:
    """安全转换为 float，失败返回 None."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def normalize_date_for_tencent(s: str) -> str:
    """Tencent kline API only accepts YYYY-MM-DD; convert YYYYMMDD input."""
    s = s.strip()
    if not s:
        return s
    if "-" in s:
        return s
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def normalize_ticker_for_sina(ticker: str) -> str:
    """转换代码为 Sina 格式 (sh600519 / sz000001).

    Handles: 000001, sh600519, sz000001, 600519, 600519.SS, 000001.SZ
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


def normalize_ticker_for_tencent(ticker: str) -> tuple[str, str]:
    """转换代码为腾讯格式 (code, exchange).

    Handles: 000001, sz000001, sh600519, 600519.SS, 000001.SZ
    """
    t = ticker.strip()
    lower = t.lower()

    # 先尝试识别市场前缀
    if lower.startswith("sh"):
        return t[2:], "sh"
    if lower.startswith("sz"):
        return t[2:], "sz"
    if lower.startswith("bj"):
        return t[2:], "bj"

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


def normalize_ticker_for_baostock(ticker: str) -> str:
    """转换代码为 Baostock 格式 (sh.600519 / sz.000001).

    Handles: 000001, sz000001, sh600519, 600519.SS, 000001.SZ, sz.000001
    """
    t = ticker.strip()

    # 直接处理带点前缀格式
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


def normalize_ticker_for_yfinance(ticker: str) -> str:
    """转换代码为 yfinance 格式 (600519.SS / 000001.SZ)."""
    t = ticker.strip().upper()
    lower = t.lower()

    if lower.startswith(("sh", "sz", "bj")):
        code = t[2:]
        if lower.startswith("sh"):
            return f"{code}.SS"
        if lower.startswith("bj"):
            return f"{code}.BJ"
        return f"{code}.SZ"
    if "." in t:
        code, suffix = t.rsplit(".", 1)
        suffix = {"SH": "SS", "XSHG": "SS", "XSHE": "SZ", "BSE": "BJ"}.get(
            suffix, suffix
        )
        return f"{code}.{suffix}"
    # 纯数字
    if t.startswith(("6", "9")):
        return f"{t}.SS"
    if t.startswith(("4", "8")):
        return f"{t}.BJ"
    return f"{t}.SZ"
