"""
RAG (Retrieval Augmented Generation) Module for TradingAgents.

This module provides retrieval capabilities for financial news and documents,
enhancing the LLM's context with relevant external knowledge.

Components:
- VectorStore: Abstraction layer for vector databases (ChromaDB/FAISS/Qdrant)
- EmbeddingModel: Integration with embedding models (OpenAI/BGE/MiniLM)
- Retriever: Two-stage retrieval (BM25 + Vector search)
- Reranker: Re-ranking results using cross-encoders
- CNNewsRetriever: China A-share specific news retriever
- RAGManager: Global singleton for managing retriever instances
"""

from .vector_store import VectorStore, VectorStoreConfig, VectorStoreType, Document
from .embedding_model import EmbeddingModel, EmbeddingModelConfig, EmbeddingModelType
from .retriever import Retriever, RetrieverConfig, RetrievalResult, LRUCache
from .reranker import Reranker, RerankerConfig, RerankedResult
from .config import (
    RAGConfig,
    CNNewsRetrievalConfig,
    DEFAULT_RAG_CONFIG,
    DEFAULT_CN_NEWS_CONFIG,
)
from .cn_news_retriever import (
    CNNewsRetriever,
    RAGManager,
    get_rag_manager,
    get_cn_news_retriever,
)
from .rag_middleware import (
    RAGMiddleware,
    RAGMiddlewareConfig,
    MergeStrategy,
    get_middleware,
    rag_execute,
)
from .performance import (
    ModelPreloader,
    PreloadConfig,
    LoadStatus,
    preload_rag_models,
    ensure_rag_ready,
)
from .security import (
    SecurityConfig,
    SecurityLevel,
    SecurityResult,
    InputValidator,
    APIKeyChecker,
    RateLimiter,
    get_security_config,
    get_validator,
    get_rate_limiter,
    check_api_keys,
    validate_input,
)

__all__ = [
    # Vector Store
    "VectorStore",
    "VectorStoreConfig",
    "VectorStoreType",
    "Document",
    # Embedding
    "EmbeddingModel",
    "EmbeddingModelConfig",
    "EmbeddingModelType",
    # Retriever
    "Retriever",
    "RetrieverConfig",
    "RetrievalResult",
    "LRUCache",
    # Reranker
    "Reranker",
    "RerankerConfig",
    "RerankedResult",
    # Config
    "RAGConfig",
    "CNNewsRetrievalConfig",
    "DEFAULT_RAG_CONFIG",
    "DEFAULT_CN_NEWS_CONFIG",
    # CN News
    "CNNewsRetriever",
    # Middleware
    "RAGMiddleware",
    "RAGMiddlewareConfig",
    "MergeStrategy",
    "get_middleware",
    "rag_execute",
    # Performance
    "ModelPreloader",
    "PreloadConfig",
    "LoadStatus",
    "preload_rag_models",
    "ensure_rag_ready",
    # Security
    "SecurityConfig",
    "SecurityLevel",
    "SecurityResult",
    "InputValidator",
    "APIKeyChecker",
    "RateLimiter",
    "get_security_config",
    "get_validator",
    "get_rate_limiter",
    "check_api_keys",
    "validate_input",
    # Global Manager
    "RAGManager",
    "get_rag_manager",
    "get_cn_news_retriever",
]
