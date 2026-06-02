"""
RAG-Enhanced News Tools.

This module provides RAG-augmented versions of the news tools,
enhancing the raw data with semantic search capabilities.

Usage:
    # Enable RAG for news retrieval
    from tradingagents.agents.utils.rag_news_tools import get_rag_news

    # Get news with RAG enhancement
    result = get_rag_news.invoke({
        "ticker": "600519.SH",
        "curr_date": "2025-05-05",
        "look_back_days": 7,
        "enable_rag": True,
    })

Environment Variables:
    TRADINGAGENTS_RAG_ENABLED: Enable/disable RAG (default: false)
    TRADINGAGENTS_EMBEDDING_MODEL: Embedding model type
    TRADINGAGENTS_VECTOR_STORE_TYPE: Vector store type (memory/chromadb/faiss)
"""

import os
from typing import Annotated, Optional
try:  # pragma: no cover - optional runtime dependency
    from langchain_core.tools import tool
except Exception:  # pragma: no cover
    def tool(func=None, **kwargs):
        if func is None:
            return lambda f: f
        setattr(func, "name", getattr(func, "__name__", "tool"))
        return func
from datetime import datetime, timedelta

from tradingagents.dataflows.interface import route_to_vendor
from tradingagents.agents.utils.rag import (
    get_cn_news_retriever,
    CNNewsRetrievalConfig,
    RAGConfig,
)


def _get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean from environment variable."""
    value = os.environ.get(key, "").lower()
    if value in ("true", "1", "yes"):
        return True
    if value in ("false", "0", "no"):
        return False
    return default


def _get_env_str(key: str, default: str = "") -> str:
    """Get string from environment variable."""
    return os.environ.get(key, default)


def _get_rag_retriever():
    """Get or create the shared RAG retriever instance."""
    if not _is_rag_enabled():
        return None

    config = CNNewsRetrievalConfig(
        enable_rag=True,
    )

    # Configure based on environment variables
    embedding_model = _get_env_str("TRADINGAGENTS_EMBEDDING_MODEL", "mini_lm")
    if embedding_model == "bge":
        from tradingagents.agents.utils.rag import EmbeddingModelType, EmbeddingModelConfig
        config.embedding_config = EmbeddingModelConfig(
            model_type=EmbeddingModelType.BGE,
            model_name=_get_env_str("TRADINGAGENTS_EMBEDDING_MODEL_NAME", "BAAI/bge-base-zh-v1.5"),
        )

    vector_store_type = _get_env_str("TRADINGAGENTS_VECTOR_STORE_TYPE", "memory")
    if vector_store_type:
        from tradingagents.agents.utils.rag import VectorStoreType, VectorStoreConfig
        type_map = {"memory": VectorStoreType.MEMORY, "chromadb": VectorStoreType.CHROMADB, "faiss": VectorStoreType.FAISS}
        config.vector_store_config = VectorStoreConfig(
            store_type=type_map.get(vector_store_type, VectorStoreType.MEMORY),
            persist_directory=_get_env_str("TRADINGAGENTS_VECTOR_STORE_PATH", None),
        )

    # Reranker config
    from tradingagents.agents.utils.rag import RerankerConfig
    config.reranker_config = RerankerConfig(
        enabled=_get_env_bool("TRADINGAGENTS_RERANKER_ENABLED", True),
    )

    return get_cn_news_retriever(config)


def _is_rag_enabled() -> bool:
    """Check if RAG is enabled via environment variable."""
    import os
    return os.environ.get("TRADINGAGENTS_RAG_ENABLED", "false").lower() == "true"


@tool
def get_rag_news(
    ticker: Annotated[str, "Stock ticker symbol"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    enable_rag: Annotated[bool, "Whether to use RAG enhancement"] = None,
) -> str:
    """Get news for a stock ticker with optional RAG enhancement.

    This tool first attempts to retrieve news from the vector store using
    semantic search, then falls back to raw data if RAG is unavailable
    or returns no results.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "600519.SH")
        curr_date: Current date in yyyy-mm-dd format
        look_back_days: Number of days to look back (default: 7)
        enable_rag: Override RAG enable setting (default: use env var or False)

    Returns:
        str: Formatted news data, optionally enhanced with RAG
    """
    # Determine if RAG should be used
    use_rag = enable_rag if enable_rag is not None else _is_rag_enabled()

    if not use_rag:
        # Pure raw data mode
        start_date = (
            datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=look_back_days)
        ).strftime("%Y-%m-%d")
        return route_to_vendor("get_news", ticker, start_date, curr_date)

    try:
        # Try RAG retrieval first
        retriever = _get_rag_retriever()

        if retriever is None:
            # RAG not configured, fall back to raw
            start_date = (
                datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=look_back_days)
            ).strftime("%Y-%m-%d")
            return route_to_vendor("get_news", ticker, start_date, curr_date)

        # RAG retrieval
        start_date = (
            datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=look_back_days)
        ).strftime("%Y-%m-%d")

        results = retriever.retrieve(
            query=ticker,
            ticker=ticker,
            date_range=(start_date, curr_date),
            top_k=10,
        )

        if results:
            # Format RAG results
            return retriever.format_for_llm_context(results, max_results=10)

    except Exception as e:
        # RAG failed, fall back to raw
        pass

    # Fall back to raw data
    start_date = (
        datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=look_back_days)
    ).strftime("%Y-%m-%d")
    return route_to_vendor("get_news", ticker, start_date, curr_date)


@tool
def get_rag_sector_news(
    sector: Annotated[str, "Sector name: tech, new_energy, pharma, real_estate, fintech"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of articles to return"] = 6,
    enable_rag: Annotated[bool, "Whether to use RAG enhancement"] = None,
) -> str:
    """Get sector-specific news with optional RAG enhancement.

    Args:
        sector: Industry sector (tech, new_energy, pharma, real_estate, fintech)
        curr_date: Current date in yyyy-mm-dd format
        look_back_days: Number of days to look back (default: 7)
        limit: Maximum number of articles (default: 6)
        enable_rag: Override RAG enable setting

    Returns:
        str: Formatted sector news data
    """
    use_rag = enable_rag if enable_rag is not None else _is_rag_enabled()

    if not use_rag:
        # Route to existing CN sector news tool
        return route_to_vendor(f"get_cn_{sector}_news", sector, curr_date, look_back_days, limit)

    try:
        retriever = _get_rag_retriever()

        if retriever is None:
            return route_to_vendor(f"get_cn_{sector}_news", sector, curr_date, look_back_days, limit)

        results = retriever.retrieve_sector_news(
            sector=sector,
            lookback_days=look_back_days,
            top_k=limit,
        )

        if results:
            return retriever.format_for_llm_context(results, max_results=limit)

    except Exception:
        pass

    # Fall back
    return route_to_vendor(f"get_cn_{sector}_news", sector, curr_date, look_back_days, limit)


@tool
def index_news_for_rag(
    ticker: Annotated[str, "Stock ticker symbol"],
    content: Annotated[str, "News content to index"],
    title: Annotated[str, "News title"] = "",
    source: Annotated[str, "News source"] = "",
    date: Annotated[str, "Publication date in yyyy-mm-dd format"] = "",
) -> str:
    """Index a news article into the RAG vector store.

    Use this tool to add custom news articles to the RAG index for
    semantic retrieval in subsequent queries.

    Args:
        ticker: Stock ticker symbol
        content: Full news content
        title: News title (optional)
        source: News source (optional)
        date: Publication date (optional, defaults to today)

    Returns:
        str: Confirmation message with document ID
    """
    try:
        retriever = _get_rag_retriever()

        if retriever is None:
            return "RAG not initialized. Set TRADINGAGENTS_RAG_ENABLED=true to enable."

        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        doc_id = retriever.add_news(
            content=content,
            title=title,
            source=source,
            date=date,
            ticker=ticker,
        )

        return f"Successfully indexed news: {title or 'Untitled'} (ID: {doc_id})"

    except Exception as e:
        return f"Failed to index news: {str(e)}"


def get_rag_status() -> dict:
    """Get the current RAG system status.

    Returns:
        dict: Status information about RAG components
    """
    try:
        retriever = _get_rag_retriever()

        if retriever is None:
            return {
                "enabled": False,
                "initialized": False,
                "message": "RAG not enabled. Set TRADINGAGENTS_RAG_ENABLED=true",
            }

        stats = retriever.get_stats()

        return {
            "enabled": True,
            "initialized": stats.get("initialized", False),
            "indexed_documents": stats.get("indexed_documents", 0),
            "vector_store": stats.get("vector_store", {}),
            "message": "RAG system operational",
        }

    except Exception as e:
        return {
            "enabled": False,
            "initialized": False,
            "error": str(e),
        }
