"""
Embedding Model Integration.

Provides unified interface for different embedding models:
- OpenAI (text-embedding-3-small, text-embedding-3-large)
- BGE (BAAI BGE models)
- MiniLM (Sentence-BERT MiniLM)
- HuggingFace (generic sentence transformers)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Union
import numpy as np

from .config import EmbeddingModelConfig, EmbeddingModelType


class EmbeddingModelBase(ABC):
    """Abstract base class for embedding models."""

    @abstractmethod
    def embed(self, texts: Union[str, List[str]]) -> np.ndarray:
        """Generate embeddings for text(s)."""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the embedding dimension."""
        pass


class OpenAIEmbedding(EmbeddingModelBase):
    """OpenAI embedding model implementation."""

    def __init__(self, config: EmbeddingModelConfig):
        self.config = config
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
            )
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")

    def embed(self, texts: Union[str, List[str]]) -> np.ndarray:
        """Generate embeddings using OpenAI API."""
        if isinstance(texts, str):
            texts = [texts]

        response = self._client.embeddings.create(
            model=self.config.model_name,
            input=texts,
        )

        embeddings = [item.embedding for item in response.data]
        return np.array(embeddings, dtype=np.float32)

    def get_dimension(self) -> int:
        return self.config.dimension


class HuggingFaceEmbedding(EmbeddingModelBase):
    """HuggingFace sentence transformer implementation."""

    def __init__(self, config: EmbeddingModelConfig):
        self.config = config
        self._model = None
        self._tokenizer = None
        self._init_model()

    def _init_model(self):
        """Initialize the model."""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                self.config.model_name,
                device=self.config.device,
            )

            # 应用量化优化（如果配置启用）
            if getattr(self.config, "quantize", False):
                self._apply_quantization()

        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. Install with: pip install sentence-transformers"
            )

    def _apply_quantization(self):
        """应用动态量化以减少内存占用."""
        try:
            # 使用 torch 量化
            import torch
            if hasattr(self._model, "sf") and hasattr(self._model.sf, "auto_model"):
                # 对 transformer 模型应用动态量化
                model_to_quantize = self._model.sf.auto_model
                if hasattr(model_to_quantize, "quantize"):
                    # INT8 量化
                    model_to_quantize = torch.quantization.quantize_dynamic(
                        model_to_quantize,
                        {torch.nn.Linear},
                        dtype=torch.qint8
                    )
                    self._model.sf.auto_model = model_to_quantize
                    self._quantized = True
                    logger = __import__("logging").getLogger(__name__)
                    logger.info("Embedding model quantized to INT8")
        except Exception:
            pass  # 量化失败不影响正常功能

    def embed(self, texts: Union[str, List[str]]) -> np.ndarray:
        """Generate embeddings using sentence transformers."""
        if isinstance(texts, str):
            texts = [texts]

        embeddings = self._model.encode(
            texts,
            batch_size=self.config.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
        )
        return embeddings.astype(np.float32)

    def get_dimension(self) -> int:
        if self._model:
            return self._model.get_sentence_embedding_dimension()
        return self.config.dimension


class MiniLMEmbedding(HuggingFaceEmbedding):
    """MiniLM specific implementation with optimizations."""

    def __init__(self, config: EmbeddingModelConfig = None):
        if config is None:
            config = EmbeddingModelConfig(
                model_type=EmbeddingModelType.MINI_LM,
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                dimension=384,
            )
        super().__init__(config)


class BGEEmbedding(HuggingFaceEmbedding):
    """BGE specific implementation with Chinese support."""

    def __init__(self, config: EmbeddingModelConfig = None):
        if config is None:
            config = EmbeddingModelConfig(
                model_type=EmbeddingModelType.BGE,
                model_name="BAAI/bge-base-zh-v1.5",  # Chinese BGE model
                dimension=768,
            )
        super().__init__(config)

    def embed(self, texts: Union[str, List[str]]) -> np.ndarray:
        """Generate embeddings with BGE-specific processing."""
        if isinstance(texts, str):
            texts = [texts]

        # BGE models benefit from instruction prefix for retrieval tasks
        instruction_prefix = "Represent this sentence for searching: "
        texts_with_prefix = [instruction_prefix + t if t else t for t in texts]

        embeddings = self._model.encode(
            texts_with_prefix,
            batch_size=self.config.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.astype(np.float32)


class EmbeddingModel:
    """Factory class for creating embedding models."""

    @staticmethod
    def create(config: EmbeddingModelConfig) -> EmbeddingModelBase:
        """Create an embedding model instance."""
        model_type = config.model_type

        if model_type == EmbeddingModelType.OPENAI:
            return OpenAIEmbedding(config)
        elif model_type == EmbeddingModelType.MINI_LM:
            return MiniLMEmbedding(config)
        elif model_type == EmbeddingModelType.BGE:
            return BGEEmbedding(config)
        elif model_type == EmbeddingModelType.HUGGINGFACE:
            return HuggingFaceEmbedding(config)
        else:
            # Default to MiniLM
            return MiniLMEmbedding(config)

    @staticmethod
    def create_default() -> EmbeddingModelBase:
        """Create a default embedding model (MiniLM)."""
        config = EmbeddingModelConfig(
            model_type=EmbeddingModelType.MINI_LM,
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            dimension=384,
            device="cpu",
        )
        return EmbeddingModel.create(config)


class EmbeddingCache:
    """Simple in-memory cache for embeddings."""

    def __init__(self, max_size: int = 10000):
        self._cache: dict = {}
        self._access_order: List[str] = []
        self._max_size = max_size

    def get(self, text: str) -> Optional[np.ndarray]:
        """Get cached embedding."""
        text_hash = hash(text)
        result = self._cache.get(text_hash)
        if result is not None:
            # Move to end of access order
            if text_hash in self._access_order:
                self._access_order.remove(text_hash)
            self._access_order.append(text_hash)
        return result

    def put(self, text: str, embedding: np.ndarray) -> None:
        """Cache an embedding."""
        text_hash = hash(text)
        self._cache[text_hash] = embedding
        self._access_order.append(text_hash)

        # Evict oldest if over capacity
        while len(self._cache) > self._max_size:
            oldest = self._access_order.pop(0)
            self._cache.pop(oldest, None)

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._access_order.clear()

    def stats(self) -> dict:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hit_rate": 0.0,  # Would need tracking for actual hit rate
        }
