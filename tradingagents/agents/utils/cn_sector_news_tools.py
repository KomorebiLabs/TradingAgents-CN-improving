"""
China A-share sector-specific news tools.

This module provides specialized news tools for different industry sectors
in the mainland China stock market, including:
- Technology/Semiconductor (科创板/科技)
- New Energy (新能源)
- Pharmaceutical (医药)
- Real Estate (房地产)
- Financial Technology (金融科技)

These tools are dynamically mounted based on the instrument's segment profile.
All tools support automatic RAG enhancement when enabled.
"""

try:  # pragma: no cover - optional runtime dependency
    from langchain_core.tools import tool
except Exception:  # pragma: no cover
    def tool(func=None, **kwargs):
        if func is None:
            return lambda f: f
        setattr(func, "name", getattr(func, "__name__", "tool"))
        return func
from typing import Annotated
from datetime import datetime, timedelta

from tradingagents.dataflows.interface import route_to_vendor

# Import RAG middleware
try:
    from tradingagents.agents.utils.rag import get_middleware
    MIDDLEWARE_AVAILABLE = True
except ImportError:
    MIDDLEWARE_AVAILABLE = False
    get_middleware = None


def _get_rag_middleware():
    """Get or create the RAG middleware instance."""
    if not MIDDLEWARE_AVAILABLE:
        return None
    return get_middleware()


# Keyword filters for each sector
SECTOR_KEYWORDS = {
    "tech": [
        "半导体", "芯片", "集成电路", "AI", "人工智能", "云计算", "大数据",
        "软件", "信息技术", "5G", "通信设备", "电子", "半导体设备", "IC设计",
        "科技创新", "硬科技", "国产替代", "自主可控", "算力", "服务器"
    ],
    "new_energy": [
        "锂电池", "锂电", "新能源", "光伏", "储能", "电动汽车", "电动车",
        "动力电池", "正极材料", "负极材料", "隔膜", "电解液", "固态电池",
        "风电", "氢能", "充电桩", "新能源汽车", "碳中和", "可再生能源"
    ],
    "pharma": [
        "创新药", "医药", "医疗器械", "中药", "生物医药", "疫苗", "抗体",
        "化学制药", "原料药", "CXO", "CRO", "CDMO", "制药设备",
        "医疗耗材", "体外诊断", "IVD", "手术机器人", "医疗影像"
    ],
    "real_estate": [
        "房地产", "地产", "万科", "碧桂园", "恒大", "购房", "房贷",
        "土地拍卖", "限购", "限售", "调控", "保障房", "长租公寓",
        "物业", "商业地产", "园区开发", "新型城镇化"
    ],
    "fintech": [
        "金融科技", "数字货币", "区块链", "支付", "第三方支付", "移动支付",
        "银行科技", "保险科技", "证券科技", "互联网金融", "金融信息化",
        "云计算金融", "大数据金融", "人工智能金融", "智能投顾"
    ],
}


def _build_sector_keyword_pattern(keywords: list) -> str:
    """Build a regex-like pattern from keywords."""
    return "|".join(keywords)


@tool
def get_cn_tech_sector_news(
    ticker: Annotated[str, "Ticker symbol of the technology/semiconductor stock"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of tech-sector news to return"] = 6,
) -> str:
    """
    Retrieve technology and semiconductor sector news for a specific stock.
    Automatically enhanced with RAG when enabled.
    """
    middleware = _get_rag_middleware()
    if middleware and middleware.config.auto_intercept:
        return middleware.execute(
            "get_cn_tech_sector_news",
            ticker=ticker,
            curr_date=curr_date,
            look_back_days=look_back_days,
            limit=limit,
        )
    return route_to_vendor(
        "get_cn_tech_sector_news",
        ticker,
        curr_date,
        look_back_days,
        limit
    )


@tool
def get_cn_new_energy_news(
    ticker: Annotated[str, "Ticker symbol of the new energy stock"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of new energy news to return"] = 6,
) -> str:
    """
    Retrieve new energy sector news for a specific stock.
    Automatically enhanced with RAG when enabled.
    """
    middleware = _get_rag_middleware()
    if middleware and middleware.config.auto_intercept:
        return middleware.execute(
            "get_cn_new_energy_news",
            ticker=ticker,
            curr_date=curr_date,
            look_back_days=look_back_days,
            limit=limit,
        )
    return route_to_vendor(
        "get_cn_new_energy_news",
        ticker,
        curr_date,
        look_back_days,
        limit
    )


@tool
def get_cn_pharma_news(
    ticker: Annotated[str, "Ticker symbol of the pharmaceutical/healthcare stock"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of pharma/healthcare news to return"] = 6,
) -> str:
    """
    Retrieve pharmaceutical and healthcare sector news for a specific stock.
    Automatically enhanced with RAG when enabled.
    """
    middleware = _get_rag_middleware()
    if middleware and middleware.config.auto_intercept:
        return middleware.execute(
            "get_cn_pharma_news",
            ticker=ticker,
            curr_date=curr_date,
            look_back_days=look_back_days,
            limit=limit,
        )
    return route_to_vendor(
        "get_cn_pharma_news",
        ticker,
        curr_date,
        look_back_days,
        limit
    )


@tool
def get_cn_real_estate_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of real estate news to return"] = 6,
) -> str:
    """
    Retrieve real estate sector news (market-wide, no specific ticker required).
    Automatically enhanced with RAG when enabled.
    """
    middleware = _get_rag_middleware()
    if middleware and middleware.config.auto_intercept:
        return middleware.execute(
            "get_cn_real_estate_news",
            curr_date=curr_date,
            look_back_days=look_back_days,
            limit=limit,
        )
    return route_to_vendor(
        "get_cn_real_estate_news",
        curr_date,
        look_back_days,
        limit
    )


@tool
def get_cn_fintech_news(
    ticker: Annotated[str, "Ticker symbol of the financial technology stock"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of fintech news to return"] = 6,
) -> str:
    """
    Retrieve financial technology sector news for a specific stock.
    Automatically enhanced with RAG when enabled.
    """
    middleware = _get_rag_middleware()
    if middleware and middleware.config.auto_intercept:
        return middleware.execute(
            "get_cn_fintech_news",
            ticker=ticker,
            curr_date=curr_date,
            look_back_days=look_back_days,
            limit=limit,
        )
    return route_to_vendor(
        "get_cn_fintech_news",
        ticker,
        curr_date,
        look_back_days,
        limit
    )


# ============================================================================
# Sector mapping utilities for internal use
# ============================================================================

# Mapping from segment/style to sector tools
SEGMENT_SECTOR_MAP = {
    "cn_star_equity": "tech",           # STAR Market -> Tech
    "cn_chinext_equity": "tech",        # ChiNext (300 prefix) -> Tech
    "cn_main_board_equity": None,       # Main Board -> Depends on industry
    "cn_bse_equity": None,              # BSE -> Depends on industry
}

# Mapping from style bucket to sector tools
STYLE_SECTOR_MAP = {
    "growth_style_candidate": "tech",   # Growth style often implies tech
}

# Mapping from industry code to sector tools (used for finer granularity)
INDUSTRY_SECTOR_MAP = {
    # Technology
    "计算机": "tech",
    "电子": "tech",
    "通信": "tech",
    "软件": "tech",
    "半导体": "tech",
    "IT设备": "tech",
    # New Energy
    "电气设备": "new_energy",
    "汽车": "new_energy",
    "化工": "new_energy",
    "有色金属": "new_energy",
    # Pharma
    "医药生物": "pharma",
    "医疗器械": "pharma",
    "中药": "pharma",
    # Real Estate
    "房地产": "real_estate",
    "建筑建材": "real_estate",
    # Fintech
    "非银金融": "fintech",
    "银行": "fintech",
}


def get_sector_for_ticker(ticker: str, industry: str = None) -> str | None:
    """
    Determine the sector for a given ticker.

    Args:
        ticker: Stock ticker symbol
        industry: Optional industry name from fundamentals

    Returns:
        Sector name ('tech', 'new_energy', 'pharma', 'real_estate', 'fintech')
        or None if no specific sector match
    """
    value = ticker.strip().upper()
    code = value.split(".")[0] if "." in value else value

    # Check by prefix (STAR Market / ChiNext)
    if code.startswith("688"):
        return "tech"  # STAR Market is predominantly tech
    if code.startswith("300"):
        return "tech"  # ChiNext includes many tech/growth companies

    # Check by industry if provided
    if industry:
        for key, sector in INDUSTRY_SECTOR_MAP.items():
            if key in industry:
                return sector

    # Default: no specific sector match
    return None


def get_sector_tools_for_ticker(ticker: str, industry: str = None) -> list:
    """
    Get the list of sector-specific tools for a given ticker.

    Args:
        ticker: Stock ticker symbol
        industry: Optional industry name from fundamentals

    Returns:
        List of tool functions for the matched sector
    """
    sector = get_sector_for_ticker(ticker, industry)

    tools_map = {
        "tech": [get_cn_tech_sector_news],
        "new_energy": [get_cn_new_energy_news],
        "pharma": [get_cn_pharma_news],
        "fintech": [get_cn_fintech_news],
        "real_estate": [get_cn_real_estate_news],
    }

    return tools_map.get(sector, [])
