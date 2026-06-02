"""
Retriever Module.

Provides two-stage retrieval:
1. First stage: BM25 lexical search
2. Second stage: Vector similarity search (hybrid)
Includes LRU cache for query results.

Logging:
    - Set TRADINGAGENTS_LOG_LEVEL=DEBUG for verbose logging
    - Default level is WARNING
"""

import os
import logging

# Configure module logger
_logger = logging.getLogger(__name__)
_log_level = os.environ.get("TRADINGAGENTS_LOG_LEVEL", "WARNING").upper()
if _log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
    _log_level = "WARNING"
logging.getLogger(__name__).setLevel(_log_level)


def _log_debug(msg: str, **kwargs):
    _logger.debug(msg, **kwargs)


def _log_info(msg: str, **kwargs):
    _logger.info(msg, **kwargs)


def _log_warning(msg: str, **kwargs):
    _logger.warning(msg, **kwargs)


def _log_error(msg: str, **kwargs):
    _logger.error(msg, **kwargs)


from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import re
import hashlib
import json
import time
import threading
from collections import OrderedDict
from collections import Counter

from .vector_store import VectorStore, VectorStoreBase, Document, VectorStoreConfig, VectorStoreType
from .embedding_model import EmbeddingModel, EmbeddingModelBase, EmbeddingModelConfig
from .config import RetrieverConfig


# ================================================================================
# LRU缓存实现
# ================================================================================

class LRUCache:
    """Thread-safe LRU cache for retrieval results."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        Initialize LRU cache.

        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
        """
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def _make_key(self, query: str, filters: Optional[Dict] = None, top_k: int = None) -> str:
        """Generate cache key from query parameters."""
        key_data = {
            "query": query,
            "filters": filters,
            "top_k": top_k,
        }
        key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, query: str, filters: Optional[Dict] = None, top_k: int = None) -> Optional[Any]:
        """Get cached result."""
        with self._lock:
            key = self._make_key(query, filters, top_k)

            # Check TTL
            if key in self._timestamps:
                if time.time() - self._timestamps[key] > self._ttl:
                    # Expired
                    self._cache.pop(key, None)
                    self._timestamps.pop(key, None)
                    self._misses += 1
                    return None

            if key in self._cache:
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]

            self._misses += 1
            return None

    def put(self, query: str, filters: Optional[Dict] = None, top_k: int = None, value: Any = None) -> None:
        """Put result into cache."""
        if value is None:
            return

        with self._lock:
            key = self._make_key(query, filters, top_k)

            # Remove oldest if at capacity
            while len(self._cache) >= self._max_size:
                oldest_key = next(iter(self._cache))
                self._cache.pop(oldest_key)
                self._timestamps.pop(oldest_key, None)

            self._cache[key] = value
            self._timestamps[key] = time.time()
            self._cache.move_to_end(key)

    def invalidate(self, pattern: str = None) -> int:
        """Invalidate cache entries. If pattern is None, clear all."""
        with self._lock:
            if pattern is None:
                count = len(self._cache)
                self._cache.clear()
                self._timestamps.clear()
                return count

            # Partial invalidation by pattern (not implemented for simplicity)
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.2%}",
                "ttl_seconds": self._ttl,
            }


@dataclass
class RetrievalResult:
    """Represents a single retrieval result."""
    document_id: str
    content: str
    metadata: Dict[str, Any]
    score: float
    source: str = "hybrid"  # "bm25", "vector", "hybrid"
    rank: int = 0


@dataclass
class RetrievalOutput:
    """Collection of retrieval results."""
    results: List[RetrievalResult]
    query: str
    total_candidates: int
    retrieval_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.results)

    def __iter__(self):
        return iter(self.results)

    def format_for_context(self, max_results: int = 5, max_chars: int = 2000) -> str:
        """Format results as a string suitable for LLM context."""
        output_parts = [f"=== Retrieved Documents ({len(self.results)} results) ===\n"]

        for i, result in enumerate(self.results[:max_results], 1):
            content = result.content
            if len(content) > max_chars:
                content = content[:max_chars] + "..."

            metadata_str = ", ".join(f"{k}={v}" for k, v in result.metadata.items() if v)

            output_parts.append(
                f"\n--- Document {i} (Score: {result.score:.3f}, Source: {result.source}) ---\n"
                f"Source: {metadata_str}\n"
                f"Content: {content}\n"
            )

        return "\n".join(output_parts)


class BM25:
    """BM25 ranking algorithm implementation."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[str] = []
        self.tokenized_docs: List[List[str]] = []
        self.avg_doc_len = 0
        self.doc_freqs: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize Chinese and English text."""
        # Simple tokenization: split on whitespace and extract Chinese characters
        tokens = []
        # Split on whitespace and punctuation
        words = re.split(r'[\s,，.。!！?？;；:：()（）\[\]【】""''""\'"]+', text)
        for word in words:
            word = word.strip()
            if word:
                tokens.append(word.lower())
        return tokens

    def index(self, documents: List[str]) -> None:
        """Build the BM25 index from documents."""
        self.documents = documents
        self.tokenized_docs = [self._tokenize(doc) for doc in documents]

        # Calculate average document length
        doc_lens = [len(tokens) for tokens in self.tokenized_docs]
        self.avg_doc_len = sum(doc_lens) / len(doc_lens) if doc_lens else 1

        # Calculate document frequencies
        self.doc_freqs = Counter()
        for tokens in self.tokenized_docs:
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] += 1

        # Calculate IDF
        n_docs = len(documents)
        for token, df in self.doc_freqs.items():
            self.idf[token] = np.log((n_docs - df + 0.5) / (df + 0.5) + 1)

    def search(self, query: str, top_k: int = 20) -> List[Tuple[int, float]]:
        """Search for documents matching the query."""
        query_tokens = self._tokenize(query)
        scores = []

        for i, doc_tokens in enumerate(self.tokenized_docs):
            score = self._calculate_score(query_tokens, doc_tokens)
            scores.append((i, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def _calculate_score(self, query_tokens: List[str], doc_tokens: List[str]) -> float:
        """Calculate BM25 score for a single document."""
        doc_len = len(doc_tokens)
        doc_tf = Counter(doc_tokens)

        score = 0.0
        for token in query_tokens:
            if token not in self.idf:
                continue

            tf = doc_tf.get(token, 0)
            idf = self.idf[token]

            # BM25 formula
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)
            score += idf * numerator / (denominator + 1e-8)

        return score


class Retriever:
    """Hybrid retriever combining BM25 and vector search with LRU caching."""

    def __init__(
        self,
        config: RetrieverConfig = None,
        embedding_model: EmbeddingModelBase = None,
        vector_store: VectorStoreBase = None,
        cache_size: int = 1000,
        cache_ttl: int = 3600,
    ):
        self.config = config or RetrieverConfig()
        self.embedding_model = embedding_model or EmbeddingModel.create_default()
        self.vector_store = vector_store or VectorStore.create(VectorStoreType.MEMORY)

        self.bm25 = BM25(k1=self.config.bm25_k1, b=self.config.bm25_b)
        self._is_indexed = False

        # Initialize cache
        import os
        max_cache_size = int(os.environ.get("TRADINGAGENTS_RAG_CACHE_SIZE", str(cache_size)))
        cache_ttl = int(os.environ.get("TRADINGAGENTS_RAG_CACHE_TTL", str(cache_ttl)))
        self._cache = LRUCache(max_size=max_cache_size, ttl_seconds=cache_ttl)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_stats()

    def clear_cache(self) -> int:
        """Clear the query cache. Returns number of entries cleared."""
        return self._cache.invalidate()

    def index_documents(
        self,
        documents: List[Document],
    ) -> None:
        """Index documents for retrieval."""
        import time
        start = time.time()

        # Extract texts and metadata
        texts = [doc.content for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        # Build BM25 index
        self.bm25.index(texts)

        # Generate embeddings
        embeddings = self.embedding_model.embed(texts)

        # Add to vector store
        self.vector_store.add_documents(documents, embeddings)

        self._is_indexed = True
        self._index_time_ms = (time.time() - start) * 1000

    def add_documents(
        self,
        documents: List[Document],
    ) -> None:
        """Add documents to existing index."""
        if not self._is_indexed:
            self.index_documents(documents)
            return

        import time
        start = time.time()

        # Extract texts
        texts = [doc.content for doc in documents]

        # Update BM25 (rebuild for simplicity)
        all_texts = self.bm25.documents + texts
        self.bm25.index(all_texts)

        # Generate embeddings and add to vector store
        embeddings = self.embedding_model.embed(texts)
        self.vector_store.add_documents(documents, embeddings)

        self._add_time_ms = (time.time() - start) * 1000

    def retrieve(
        self,
        query: str,
        top_k: int = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RetrievalOutput:
        """Retrieve relevant documents for a query.

        Uses LRU cache to avoid redundant retrievals for the same query.
        """
        import time
        start = time.time()

        _log_debug(f"Retrieving query: {query[:50]}... (top_k={top_k})")

        # Check cache first
        cached_result = self._cache.get(query, filters, top_k)
        if cached_result is not None:
            # Add cache hit indicator to metadata
            cached_result.retrieval_time_ms = (time.time() - start) * 1000
            cached_result.metadata["cache_hit"] = True
            _log_debug(f"Cache hit for query: {query[:50]}...")
            return cached_result

        top_k = top_k or self.config.initial_top_k
        final_top_k = self.config.final_top_k

        _log_debug(f"Cache miss, performing retrieval for: {query[:50]}...")

        # Generate query embedding
        query_embedding = self.embedding_model.embed(query)[0]

        # BM25 search
        bm25_results = self.bm25.search(query, top_k * 2)
        bm25_doc_ids = {idx: score for idx, score in bm25_results}

        # Vector search
        vector_results = self.vector_store.search(
            query_embedding,
            top_k=top_k * 2,
            filters=filters,
        )

        # Hybrid scoring
        hybrid_scores: Dict[int, Dict[str, float]] = {}

        # Add BM25 scores
        for idx, bm25_score in bm25_doc_ids.items():
            if idx not in hybrid_scores:
                hybrid_scores[idx] = {"bm25": 0.0, "vector": 0.0, "doc": None}
            hybrid_scores[idx]["bm25"] = bm25_score

        # Add vector scores
        for doc, vector_score in vector_results:
            doc_idx = self._find_doc_idx(doc.id)
            if doc_idx is not None:
                if doc_idx not in hybrid_scores:
                    hybrid_scores[doc_idx] = {"bm25": 0.0, "vector": 0.0, "doc": None}
                hybrid_scores[doc_idx]["vector"] = vector_score
                hybrid_scores[doc_idx]["doc"] = doc

        # Calculate hybrid scores
        results = []
        for idx, scores in hybrid_scores.items():
            doc = scores["doc"]
            if doc is None:
                # Get document from BM25 results
                if idx < len(self.bm25.documents):
                    doc = Document(
                        id=f"doc_{idx}",
                        content=self.bm25.documents[idx],
                        metadata={},
                    )
                else:
                    continue

            # Normalize and combine scores
            bm25_norm = self._normalize_bm25(scores["bm25"], bm25_doc_ids)
            vector_score = scores["vector"]

            hybrid_score = (
                self.config.bm25_weight * bm25_norm +
                self.config.vector_weight * vector_score
            )

            source = "hybrid"
            if scores["bm25"] > 0 and scores["vector"] == 0:
                source = "bm25"
            elif scores["vector"] > 0 and scores["bm25"] == 0:
                source = "vector"

            results.append(RetrievalResult(
                document_id=doc.id,
                content=doc.content,
                metadata=doc.metadata,
                score=hybrid_score,
                source=source,
            ))

        # Sort by score and limit
        results.sort(key=lambda x: x.score, reverse=True)
        results = results[:final_top_k]

        # Add rank
        for i, result in enumerate(results, 1):
            result.rank = i

        retrieval_time = (time.time() - start) * 1000

        output = RetrievalOutput(
            results=results,
            query=query,
            total_candidates=len(hybrid_scores),
            retrieval_time_ms=retrieval_time,
            metadata={
                "bm25_weight": self.config.bm25_weight,
                "vector_weight": self.config.vector_weight,
                "indexed_documents": len(self.bm25.documents),
                "cache_hit": False,
            },
        )

        # Cache the result
        self._cache.put(query, filters, top_k, output)

        return output

    def _normalize_bm25(self, score: float, all_scores: Dict[int, float]) -> float:
        """Normalize BM25 scores to 0-1 range."""
        if not all_scores:
            return 0.0
        max_score = max(all_scores.values())
        if max_score == 0:
            return 0.0
        return score / max_score

    def _find_doc_idx(self, doc_id: str) -> Optional[int]:
        """Find document index by ID."""
        # Try to extract index from ID
        if doc_id.startswith("doc_"):
            try:
                return int(doc_id[4:])
            except ValueError:
                pass

        # Search in BM25 documents
        for i, doc in enumerate(self.bm25.documents):
            if f"doc_{i}" == doc_id:
                return i

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get retriever statistics."""
        return {
            "indexed_documents": len(self.bm25.documents),
            "bm25_terms": len(self.bm25.idf),
            "vector_store": self.vector_store.get_stats(),
            "cache": self._cache.get_stats(),
        }
