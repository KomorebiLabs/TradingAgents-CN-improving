"""
RAG Module Configuration.

Provides configuration classes and defaults for the RAG components.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class VectorStoreType(Enum):
    """Supported vector store types."""
    CHROMADB = "chromadb"
    FAISS = "faiss"
    QDRANT = "qdrant"
    MEMORY = "memory"  # In-memory fallback


class EmbeddingModelType(Enum):
    """Supported embedding model types."""
    OPENAI = "openai"
    BGE = "bge"  # BAAI BGE
    MINI_LM = "mini_lm"  # Sentence-BERT MiniLM
    HUGGINGFACE = "huggingface"


@dataclass
class VectorStoreConfig:
    """Configuration for vector store."""
    store_type: VectorStoreType = VectorStoreType.MEMORY
    persist_directory: Optional[str] = None
    collection_name: str = "tradingagents_documents"
    distance_metric: str = "cosine"  # cosine, euclidean, dotproduct
    extra_config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.store_type, str):
            self.store_type = VectorStoreType(self.store_type)


@dataclass
class EmbeddingModelConfig:
    """Configuration for embedding model."""
    model_type: EmbeddingModelType = EmbeddingModelType.MINI_LM
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    dimension: int = 384
    batch_size: int = 32
    max_length: int = 512
    device: str = "cpu"  # cpu, cuda, mps

    # Performance optimization
    quantize: bool = False  # Enable INT8 quantization
    use_fp16: bool = False  # Use FP16 instead of FP32

    def __post_init__(self):
        if isinstance(self.model_type, str):
            self.model_type = EmbeddingModelType(self.model_type)

        # Auto-detect dimension based on model name
        if "all-MiniLM-L6-v2" in self.model_name:
            self.dimension = 384
        elif "bge-base" in self.model_name:
            self.dimension = 768
        elif "bge-large" in self.model_name:
            self.dimension = 1024
        elif "text-embedding-3" in self.model_name:
            self.dimension = 1536  # Default, may vary


@dataclass
class RerankerConfig:
    """Configuration for reranker."""
    enabled: bool = True
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    top_k: int = 10  # Number of results to return after reranking
    device: str = "cpu"

    # Cross-encoder specific
    use_cross_encoder: bool = True
    batch_size: int = 32


@dataclass
class RetrieverConfig:
    """Configuration for retriever."""
    # BM25 parameters
    bm25_k1: float = 1.5
    bm25_b: float = 0.75

    # Hybrid search weights
    bm25_weight: float = 0.3
    vector_weight: float = 0.7

    # Retrieval limits
    initial_top_k: int = 50  # Initial retrieval before reranking
    final_top_k: int = 10   # Final results after reranking

    # Filter options
    enable_filter: bool = True
    filter_fields: List[str] = field(default_factory=lambda: ["sector", "date", "source"])


@dataclass
class CNNewsRetrievalConfig:
    """Configuration for China A-share news retrieval."""
    # Sector filtering
    default_sectors: List[str] = field(default_factory=lambda: [
        "tech", "new_energy", "pharma", "real_estate", "fintech"
    ])

    # Date range
    default_lookback_days: int = 7
    max_lookback_days: int = 30

    # Content limits
    max_news_per_query: int = 20
    max_summary_length: int = 2000  # Max characters per news summary

    # RAG settings
    enable_rag: bool = True
    vector_store_config: VectorStoreConfig = field(default_factory=VectorStoreConfig)
    embedding_config: EmbeddingModelConfig = field(default_factory=EmbeddingModelConfig)
    reranker_config: RerankerConfig = field(default_factory=RerankerConfig)
    retriever_config: RetrieverConfig = field(default_factory=RetrieverConfig)

    # Chinese text processing
    chinese_tokenizer: str = "jieba"
    enable_chunking: bool = True
    chunk_size: int = 500  # Characters per chunk
    chunk_overlap: int = 50


@dataclass
class RAGConfig:
    """Top-level RAG configuration."""
    enabled: bool = False  # Global enable/disable
    default_retrieval_config: CNNewsRetrievalConfig = field(default_factory=CNNewsRetrievalConfig)

    # Fallback settings
    fallback_to_raw: bool = True  # Fall back to raw data if RAG fails
    cache_results: bool = True

    # Performance settings
    async_mode: bool = True
    max_concurrent_requests: int = 5

    # Persistence
    config_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "enabled": self.enabled,
            "fallback_to_raw": self.fallback_to_raw,
            "cache_results": self.cache_results,
            "async_mode": self.async_mode,
            "max_concurrent_requests": self.max_concurrent_requests,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RAGConfig":
        """Create config from dictionary."""
        return cls(
            enabled=data.get("enabled", False),
            fallback_to_raw=data.get("fallback_to_raw", True),
            cache_results=data.get("cache_results", True),
            async_mode=data.get("async_mode", True),
            max_concurrent_requests=data.get("max_concurrent_requests", 5),
        )

    def save(self, path: str = None) -> None:
        """Save configuration to JSON file."""
        import json
        path = path or self.config_path
        if not path:
            raise ValueError("No config path specified")

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "RAGConfig":
        """Load configuration from JSON file."""
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        config = cls.from_dict(data)
        config.config_path = path
        return config


# Default configuration instance
DEFAULT_RAG_CONFIG = RAGConfig(
    enabled=False,
    fallback_to_raw=True,
    cache_results=True,
    async_mode=True,
    max_concurrent_requests=5,
)

# Default Chinese news RAG config
DEFAULT_CN_NEWS_CONFIG = CNNewsRetrievalConfig(
    enable_rag=True,
    default_lookback_days=7,
    max_news_per_query=20,
    max_summary_length=2000,
)
