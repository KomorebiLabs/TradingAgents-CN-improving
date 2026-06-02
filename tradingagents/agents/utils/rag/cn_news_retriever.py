"""
China A-share News Retriever.

Provides RAG capabilities for mainland China stock market news and documents.
Integrates with existing CN tools (cn_sector_news_tools, cn_macro_tools, cn_event_tools).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable, TYPE_CHECKING
from datetime import datetime, timedelta
import json
import re
import threading

from .vector_store import VectorStore, VectorStoreBase, Document, VectorStoreConfig, VectorStoreType
from .embedding_model import EmbeddingModel, EmbeddingModelBase, EmbeddingModelConfig, EmbeddingModelType
from .retriever import Retriever, RetrievalResult, RetrievalOutput
from .reranker import Reranker, RerankedResult, RerankerOutput
from .config import CNNewsRetrievalConfig, RetrieverConfig, EmbeddingModelConfig, RerankerConfig

# Avoid circular import - only for type checking
if TYPE_CHECKING:
    from .cn_news_retriever import CNNewsRetriever


@dataclass
class NewsDocument(Document):
    """Enhanced document for news articles."""
    title: str = ""
    source: str = ""
    date: str = ""
    sector: str = ""
    ticker: str = ""
    summary: str = ""

    def __post_init__(self):
        # Build full content from components
        if not self.content and (self.title or self.summary):
            self.content = self._build_content()

    def _build_content(self) -> str:
        """Build content string from components."""
        parts = []
        if self.title:
            parts.append(f"标题: {self.title}")
        if self.summary:
            parts.append(f"摘要: {self.summary}")
        if self.content:
            parts.append(f"正文: {self.content}")
        if self.source:
            parts.append(f"来源: {self.source}")
        if self.date:
            parts.append(f"日期: {self.date}")
        return "\n".join(parts)


@dataclass
class CNNewsRetrievalResult:
    """Result from CN news retrieval."""
    content: str
    metadata: Dict[str, Any]
    score: float
    source: str
    title: str = ""
    date: str = ""

    def format_for_context(self, max_length: int = 500) -> str:
        """Format as a readable news snippet."""
        content = self.content
        if len(content) > max_length:
            content = content[:max_length] + "..."

        parts = [f"[{self.source}] {self.title} ({self.date})"]
        parts.append(content)
        return "\n".join(parts)


class CNNewsRetriever:
    """Retriever for China A-share market news.

    Features:
    - Sector-specific retrieval (tech, new_energy, pharma, real_estate, fintech)
    - Temporal filtering (recent news prioritized)
    - Hybrid retrieval (BM25 + vector)
    - Cross-encoder reranking
    - Integration with existing CN tools
    """

    def __init__(
        self,
        config: CNNewsRetrievalConfig = None,
        retriever: Retriever = None,
        reranker: Reranker = None,
    ):
        self.config = config or CNNewsRetrievalConfig()
        self.retriever = retriever
        self.reranker = reranker
        self._initialized = False

    def _initialize(self):
        """Lazy initialization of components."""
        if self._initialized:
            return

        # Create embedding model
        embedding_config = self.config.embedding_config or EmbeddingModelConfig(
            model_type=EmbeddingModelType.BGE,
            model_name="BAAI/bge-base-zh-v1.5",
            dimension=768,
        )
        embedding_model = EmbeddingModel.create(embedding_config)

        # Create vector store
        vector_config = self.config.vector_store_config or VectorStoreConfig(
            store_type=VectorStoreType.MEMORY,
            collection_name="cn_news",
        )
        vector_store = VectorStore.create(vector_config.store_type, vector_config)

        # Create retriever
        retriever_config = self.config.retriever_config or RetrieverConfig()
        self.retriever = Retriever(
            config=retriever_config,
            embedding_model=embedding_model,
            vector_store=vector_store,
        )

        # Create reranker
        reranker_config = self.config.reranker_config or RerankerConfig()
        self.reranker = Reranker.create(reranker_config)

        self._initialized = True

    def index_documents(
        self,
        documents: List[Dict[str, Any]],
    ) -> int:
        """Index news documents.

        Args:
            documents: List of document dictionaries with keys:
                - content: Full text content
                - title: News title
                - source: News source
                - date: Publication date (YYYY-MM-DD)
                - sector: Industry sector
                - ticker: Related ticker (optional)
                - summary: Brief summary (optional)

        Returns:
            Number of documents indexed
        """
        self._initialize()

        news_docs = []
        for i, doc in enumerate(documents):
            news_doc = NewsDocument(
                id=doc.get("id", f"cn_news_{i}"),
                content=doc.get("content", ""),
                metadata={
                    "title": doc.get("title", ""),
                    "source": doc.get("source", ""),
                    "date": doc.get("date", ""),
                    "sector": doc.get("sector", ""),
                    "ticker": doc.get("ticker", ""),
                    "summary": doc.get("summary", ""),
                    "type": "cn_news",
                },
                title=doc.get("title", ""),
                source=doc.get("source", ""),
                date=doc.get("date", ""),
                sector=doc.get("sector", ""),
                ticker=doc.get("ticker", ""),
                summary=doc.get("summary", ""),
            )
            news_docs.append(news_doc)

        self.retriever.index_documents(news_docs)
        return len(news_docs)

    def add_news(
        self,
        content: str,
        title: str = "",
        source: str = "",
        date: str = "",
        sector: str = "",
        ticker: str = "",
        summary: str = "",
    ) -> str:
        """Add a single news article.

        Returns:
            Document ID
        """
        self._initialize()

        doc_id = f"cn_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        news_doc = NewsDocument(
            id=doc_id,
            content=content,
            metadata={
                "title": title,
                "source": source,
                "date": date or datetime.now().strftime("%Y-%m-%d"),
                "sector": sector,
                "ticker": ticker,
                "summary": summary,
                "type": "cn_news",
            },
            title=title,
            source=source,
            date=date or datetime.now().strftime("%Y-%m-%d"),
            sector=sector,
            ticker=ticker,
            summary=summary,
        )

        self.retriever.add_documents([news_doc])
        return doc_id

    def retrieve(
        self,
        query: str,
        sector: str = None,
        ticker: str = None,
        date_range: tuple = None,
        top_k: int = None,
        use_reranker: bool = None,
    ) -> List[CNNewsRetrievalResult]:
        """Retrieve relevant news for a query.

        Args:
            query: Search query (can be in Chinese or English)
            sector: Filter by sector (tech, new_energy, pharma, real_estate, fintech)
            ticker: Filter by ticker
            date_range: Tuple of (start_date, end_date) in YYYY-MM-DD format
            top_k: Number of results to return
            use_reranker: Whether to use cross-encoder reranking (default: config.enabled)

        Returns:
            List of CNNewsRetrievalResult
        """
        self._initialize()

        use_reranker = use_reranker if use_reranker is not None else self.config.reranker_config.enabled

        # Build filters
        filters = {}
        if sector:
            filters["sector"] = sector
        if ticker:
            filters["ticker"] = ticker
        if date_range:
            filters["date"] = {"$gte": date_range[0], "$lte": date_range[1]}

        # Initial retrieval
        top_k = top_k or self.config.max_news_per_query
        initial_top_k = top_k * 2  # Retrieve more for reranking

        output = self.retriever.retrieve(
            query=query,
            top_k=initial_top_k,
            filters=filters if filters else None,
        )

        if not output.results:
            return []

        # Prepare results for reranker
        result_dicts = [
            {
                "id": r.document_id,
                "content": r.content,
                "metadata": r.metadata,
                "score": r.score,
            }
            for r in output.results
        ]

        # Rerank if enabled
        if use_reranker:
            rerank_output = self.reranker.rerank(query, result_dicts, top_k=top_k)
            results = self._convert_rerank_results(rerank_output)
        else:
            # Use retrieval results directly
            results = self._convert_retrieval_results(output, top_k=top_k)

        return results

    def retrieve_sector_news(
        self,
        sector: str,
        query: str = "",
        lookback_days: int = None,
        top_k: int = None,
    ) -> List[CNNewsRetrievalResult]:
        """Retrieve news for a specific sector.

        Args:
            sector: One of tech, new_energy, pharma, real_estate, fintech
            query: Optional additional query
            lookback_days: Number of days to look back
            top_k: Number of results

        Returns:
            List of CNNewsRetrievalResult
        """
        lookback_days = lookback_days or self.config.default_lookback_days
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        # Build query
        full_query = query
        if sector:
            sector_keywords = self._get_sector_keywords(sector)
            if full_query:
                full_query = f"{full_query} {' '.join(sector_keywords)}"
            else:
                full_query = " ".join(sector_keywords)

        return self.retrieve(
            query=full_query,
            sector=sector,
            date_range=(start_date, end_date),
            top_k=top_k,
        )

    def retrieve_ticker_news(
        self,
        ticker: str,
        query: str = "",
        lookback_days: int = None,
        top_k: int = None,
    ) -> List[CNNewsRetrievalResult]:
        """Retrieve news for a specific ticker.

        Args:
            ticker: Stock ticker (e.g., "600519.SH", "688981.SH")
            query: Optional additional query
            lookback_days: Number of days to look back
            top_k: Number of results

        Returns:
            List of CNNewsRetrievalResult
        """
        lookback_days = lookback_days or self.config.default_lookback_days
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        full_query = f"{ticker} {query}" if query else ticker

        return self.retrieve(
            query=full_query,
            ticker=ticker,
            date_range=(start_date, end_date),
            top_k=top_k,
        )

    def format_for_llm_context(
        self,
        results: List[CNNewsRetrievalResult],
        max_results: int = 5,
        max_chars_per_result: int = 500,
        include_metadata: bool = True,
    ) -> str:
        """Format results for injection into LLM context.

        Args:
            results: List of CNNewsRetrievalResult
            max_results: Maximum number of results to include
            max_chars_per_result: Maximum characters per result
            include_metadata: Whether to include metadata

        Returns:
            Formatted string suitable for LLM context
        """
        if not results:
            return "No relevant news found."

        output_parts = [f"=== 相关新闻 ({len(results)} 条结果) ===\n"]

        for i, result in enumerate(results[:max_results], 1):
            parts = [f"\n--- 新闻 {i} (相关度: {result.score:.2%}) ---"]

            if include_metadata:
                meta_parts = []
                if result.title:
                    meta_parts.append(f"标题: {result.title}")
                if result.date:
                    meta_parts.append(f"日期: {result.date}")
                if result.source:
                    meta_parts.append(f"来源: {result.source}")
                if meta_parts:
                    parts.append(" | ".join(meta_parts))

            # Content
            content = result.content
            if len(content) > max_chars_per_result:
                content = content[:max_chars_per_result] + "..."
            parts.append(f"内容: {content}")

            output_parts.append("\n".join(parts))

        return "\n".join(output_parts)

    def _convert_retrieval_results(
        self,
        output: RetrievalOutput,
        top_k: int,
    ) -> List[CNNewsRetrievalResult]:
        """Convert RetrievalOutput to CNNewsRetrievalResult."""
        results = []
        for i, result in enumerate(output.results[:top_k], 1):
            meta = result.metadata
            results.append(CNNewsRetrievalResult(
                content=result.content,
                metadata=meta,
                score=result.score,
                source=meta.get("source", ""),
                title=meta.get("title", ""),
                date=meta.get("date", ""),
            ))
        return results

    def _convert_rerank_results(
        self,
        output: RerankerOutput,
    ) -> List[CNNewsRetrievalResult]:
        """Convert RerankerOutput to CNNewsRetrievalResult."""
        results = []
        for result in output.results:
            meta = result.metadata
            results.append(CNNewsRetrievalResult(
                content=result.content,
                metadata=meta,
                score=result.final_score,
                source=meta.get("source", ""),
                title=meta.get("title", ""),
                date=meta.get("date", ""),
            ))
        return results

    def _get_sector_keywords(self, sector: str) -> List[str]:
        """Get keywords for a sector."""
        # Import from the CN tools module using absolute path
        try:
            from tradingagents.agents.utils.cn_sector_news_tools import SECTOR_KEYWORDS
        except ImportError:
            # Fallback keywords if import fails
            FALLBACK_KEYWORDS = {
                "tech": ["半导体", "芯片", "AI", "人工智能", "云计算"],
                "new_energy": ["新能源", "光伏", "储能", "电动汽车"],
                "pharma": ["医药", "创新药", "医疗器械", "生物医药"],
                "real_estate": ["房地产", "地产", "购房", "房贷"],
                "fintech": ["金融科技", "数字货币", "区块链", "支付"],
            }
            return FALLBACK_KEYWORDS.get(sector, [])

        keywords = SECTOR_KEYWORDS.get(sector, [])
        return keywords[:5] if keywords else []

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the retriever."""
        if not self._initialized:
            return {"initialized": False}

        retriever_stats = self.retriever.get_stats()
        return {
            "initialized": True,
            "indexed_documents": retriever_stats.get("indexed_documents", 0),
            "vector_store": retriever_stats.get("vector_store", {}),
            "reranker_enabled": self.config.reranker_config.enabled,
        }


class CNNewsToolWrapper:
    """Wrapper to integrate CN news retrieval with existing tools.

    Provides seamless fallback:
    1. Try RAG retrieval first
    2. Fall back to raw tool results if RAG unavailable or fails
    """

    def __init__(
        self,
        retriever: CNNewsRetriever = None,
        rag_config: CNNewsRetrievalConfig = None,
    ):
        self.retriever = retriever
        self.config = rag_config or CNNewsRetrievalConfig()

        if self.retriever is None and self.config.enable_rag:
            self.retriever = CNNewsRetriever(self.config)

    def get_news(
        self,
        ticker: str,
        curr_date: str,
        look_back_days: int = 7,
        limit: int = 10,
        query: str = "",
    ) -> str:
        """Get news with RAG enhancement.

        Args:
            ticker: Stock ticker
            curr_date: Current date
            look_back_days: Days to look back
            limit: Maximum results
            query: Optional search query

        Returns:
            Formatted news string
        """
        # Try RAG if enabled
        default_start_date = (
            datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=look_back_days)
        ).strftime("%Y-%m-%d")

        if self.retriever:
            try:
                full_query = f"{ticker} {query}" if query else ticker
                results = self.retriever.retrieve(
                    query=full_query,
                    ticker=ticker,
                    date_range=(default_start_date, curr_date),
                    top_k=limit,
                )

                if results:
                    return self.retriever.format_for_llm_context(results, max_results=limit)

            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")  # 记录日志

        # Fall back to raw tool
        from tradingagents.agents.utils.news_data_tools import get_news
        return get_news.invoke({
            "ticker": ticker,
            "start_date": default_start_date,
            "end_date": curr_date,
        })


# ================================================================================
# 全局RAG管理器单例
# ================================================================================

class RAGManager:
    """Global RAG manager singleton for managing shared retriever instances."""

    _instance: Optional["RAGManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._cn_news_retriever: Optional[CNNewsRetriever] = None
        self._config: Optional[CNNewsRetrievalConfig] = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "RAGManager":
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_cn_news_retriever(self, config: CNNewsRetrievalConfig = None) -> "CNNewsRetriever":
        """Get or create the CN news retriever instance.

        Args:
            config: Optional configuration to use

        Returns:
            CNNewsRetriever instance
        """
        if self._cn_news_retriever is None or config is not None:
            with self._lock:
                if self._cn_news_retriever is None or config is not None:
                    self._config = config or self._config or CNNewsRetrievalConfig()
                    self._cn_news_retriever = CNNewsRetriever(self._config)
                    self._initialized = True
        return self._cn_news_retriever

    def is_initialized(self) -> bool:
        """Check if the manager has been initialized."""
        return self._initialized

    def reset(self) -> None:
        """Reset the manager (for testing)."""
        with self._lock:
            self._cn_news_retriever = None
            self._config = None
            self._initialized = False


# Global convenience functions
def get_rag_manager() -> RAGManager:
    """Get the global RAG manager instance."""
    return RAGManager.get_instance()


def get_cn_news_retriever(config: CNNewsRetrievalConfig = None) -> CNNewsRetriever:
    """Get the global CN news retriever instance."""
    return get_rag_manager().get_cn_news_retriever(config)
