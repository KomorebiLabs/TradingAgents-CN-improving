"""Official CNINFO listed-company announcement adapter.

CNINFO is the official disclosure platform operated by Shenzhen Securities
Information Co., Ltd., a wholly owned subsidiary of SZSE.  The adapter only
returns announcement metadata and links; it does not treat media articles as
regulatory disclosures.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Dict, List

import requests


CNINFO_QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_URL = "https://static.cninfo.com.cn/"
_CODE_RE = re.compile(r"(?<!\d)(\d{6})(?:\.(?:SH|SZ|BJ|XSHG|XSHE))?$", re.IGNORECASE)


def _normalize_code(ticker: str) -> tuple[str, str, str]:
    raw = str(ticker or "").strip().upper()
    match = _CODE_RE.search(raw) or re.search(r"(\d{6})", raw)
    if not match:
        raise ValueError(f"Unsupported CNINFO ticker: {ticker}")
    code = match.group(1)
    if code.startswith(("60", "68")) or raw.endswith((".SH", ".XSHG")):
        return code, "sse", f"gssh0{code}"
    if code.startswith(("4", "8")) or raw.endswith(".BJ"):
        return code, "bj", f"gsbj0{code}"
    return code, "szse", f"gssz0{code}"


def _announcement_date(value: Any) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    return str(value or "")[:10]


def _normalize_announcement(item: Dict[str, Any]) -> Dict[str, str]:
    relative = str(item.get("adjunctUrl") or "").lstrip("/")
    return {
        "ticker": str(item.get("secCode") or ""),
        "company": str(item.get("secName") or ""),
        "title": str(item.get("announcementTitle") or "").strip(),
        "source_date": _announcement_date(item.get("announcementTime")),
        "url": f"{CNINFO_STATIC_URL}{relative}" if relative else "",
    }


def get_cninfo_announcements(
    ticker: str,
    start_date: str,
    end_date: str,
    limit: int = 10,
) -> str:
    """Fetch official disclosure metadata for one Chinese listed company."""
    code, column, org_id = _normalize_code(ticker)
    response = requests.post(
        CNINFO_QUERY_URL,
        data={
            "pageNum": 1,
            "pageSize": max(1, min(int(limit), 30)),
            "column": "szse",
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{code},{org_id}",
            "searchkey": "",
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": f"{start_date}~{end_date}",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        },
        headers={
            "User-Agent": "TradingAgents-CN/official-disclosure-client",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.cninfo.com.cn/",
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "announcements" not in payload:
        raise ValueError("CNINFO announcement response schema changed")

    records: List[Dict[str, str]] = []
    for raw in payload.get("announcements") or []:
        item = _normalize_announcement(raw)
        if start_date <= item["source_date"] <= end_date and item["title"]:
            records.append(item)
    if not records:
        return f"No official CNINFO announcements found for {code} between {start_date} and {end_date}"

    lines = [
        f"# Official listed-company announcements for {code} ({column})",
        f"# Vendor: cninfo.official",
        f"# Query date range: {start_date} to {end_date}",
        f"# Total announcements: {len(records)}",
        "",
    ]
    for item in records:
        lines.extend(
            [
                f"- {item['title']}",
                f"  Company: {item['company']} | Source date: {item['source_date']}",
                f"  Official document: {item['url']}",
            ]
        )
    return "\n".join(lines)
