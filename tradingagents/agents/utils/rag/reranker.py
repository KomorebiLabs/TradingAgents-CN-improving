"""
Reranker Module.

Provides cross-encoder based reranking for retrieval results.
Improves precision by re-scoring initial candidates using a more accurate model.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import numpy as np

from .config import RerankerConfig


@dataclass
class RerankedResult:
    """Represents a reranked result."""
    document_id: str
    content: str
    metadata: Dict[str, Any]
    original_score: float
    rerank_score: float
    final_score: float
    rank: int


@dataclass
class RerankerOutput:
    """Collection of reranked results."""
    results: List[RerankedResult]
    query: str
    original_count: int
    final_count: int
    rerank_time_ms: float
    metadata: Dict[str, Any]

    def __len__(self) -> int:
        return len(self.results)

    def __iter__(self):
        return iter(self.results)


class CrossEncoderReranker:
    """Cross-encoder based reranker."""

    def __init__(self, config: RerankerConfig = None):
        self.config = config or RerankerConfig()
        self._model = None
        self._initialized = False

    def _init_model(self):
        """Lazy initialization of the model."""
        if self._initialized:
            return

        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(
                self.config.model_name,
                max_length=512,
                device=self.config.device,
            )
            self._initialized = True
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. Install with: pip install sentence-transformers"
            )

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = None,
    ) -> RerankerOutput:
        """Rerank search results using cross-encoder.

        Args:
            query: The search query
            results: List of result dictionaries with 'id', 'content', 'metadata', 'score'
            top_k: Number of final results to return

        Returns:
            RerankedOutput with reranked results
        """
        import time
        start = time.time()

        if not results:
            return RerankerOutput(
                results=[],
                query=query,
                original_count=0,
                final_count=0,
                rerank_time_ms=0,
                metadata={},
            )

        self._init_model()

        top_k = top_k or self.config.top_k

        # Prepare query-document pairs for cross-encoder
        pairs = [(query, result.get("content", "")) for result in results]

        # Get rerank scores
        rerank_scores = self._model.predict(pairs, show_progress_bar=False)

        # Convert to numpy for easier manipulation
        rerank_scores = np.array(rerank_scores)

        # Normalize rerank scores to 0-1 range
        if rerank_scores.max() != rerank_scores.min():
            rerank_scores_norm = (rerank_scores - rerank_scores.min()) / (
                rerank_scores.max() - rerank_scores.min() + 1e-8
            )
        else:
            rerank_scores_norm = rerank_scores

        # Combine original and rerank scores
        # Weight: 30% original + 70% rerank
        original_scores = np.array([r.get("score", 0) for r in results])
        if original_scores.max() != original_scores.min():
            original_scores_norm = (original_scores - original_scores.min()) / (
                original_scores.max() - original_scores.min() + 1e-8
            )
        else:
            original_scores_norm = original_scores

        final_scores = 0.3 * original_scores_norm + 0.7 * rerank_scores_norm

        # Create reranked results
        reranked = []
        for i, (result, rerank_score, final_score) in enumerate(
            zip(results, rerank_scores, final_scores)
        ):
            reranked.append(RerankedResult(
                document_id=result.get("id", result.get("document_id", f"doc_{i}")),
                content=result.get("content", ""),
                metadata=result.get("metadata", {}),
                original_score=float(original_scores[i]),
                rerank_score=float(rerank_score),
                final_score=float(final_score),
                rank=0,  # Will be set after sorting
            ))

        # Sort by final score and limit
        reranked.sort(key=lambda x: x.final_score, reverse=True)
        for i, result in enumerate(reranked[:top_k], 1):
            result.rank = i

        rerank_time = (time.time() - start) * 1000

        return RerankerOutput(
            results=reranked[:top_k],
            query=query,
            original_count=len(results),
            final_count=min(top_k, len(results)),
            rerank_time_ms=rerank_time,
            metadata={
                "model": self.config.model_name,
                "original_top_k": len(results),
                "final_top_k": top_k,
            },
        )


class SimpleReranker:
    """Simple rule-based reranker (fallback when cross-encoder not available)."""

    def __init__(self, config: RerankerConfig = None):
        self.config = config or RerankerConfig()

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = None,
    ) -> RerankerOutput:
        """Simple reranking based on keyword matching and recency.

        Args:
            query: The search query
            results: List of result dictionaries
            top_k: Number of final results to return

        Returns:
            RerankedOutput with reranked results
        """
        import time
        start = time.time()

        if not results:
            return RerankerOutput(
                results=[],
                query=query,
                original_count=0,
                final_count=0,
                rerank_time_ms=0,
                metadata={"type": "simple"},
            )

        import re
        top_k = top_k or self.config.top_k

        # Extract query keywords
        query_keywords = set(re.findall(r'\w+', query.lower()))

        # Score each result
        scored = []
        for i, result in enumerate(results):
            content = result.get("content", "").lower()
            metadata = result.get("metadata", {})

            # Keyword matching score
            content_keywords = set(re.findall(r'\w+', content))
            keyword_matches = len(query_keywords & content_keywords)
            keyword_score = keyword_matches / max(len(query_keywords), 1)

            # Recency bonus (if date available)
            recency_score = 0.0
            date = metadata.get("date") or metadata.get("trade_date")
            if date:
                try:
                    from datetime import datetime
                    doc_date = datetime.strptime(str(date), "%Y-%m-%d")
                    days_ago = (datetime.now() - doc_date).days
                    recency_score = max(0, 1.0 - (days_ago / 30))  # Decay over 30 days
                except ValueError:
                    pass

            # Original score
            original_score = result.get("score", 0)

            # Combine scores: 40% keyword + 20% recency + 40% original
            final_score = 0.4 * keyword_score + 0.2 * recency_score + 0.4 * original_score

            scored.append((final_score, i, result, original_score, keyword_score))

        # Sort by final score
        scored.sort(key=lambda x: x[0], reverse=True)

        # Create reranked results
        reranked = []
        for rank, (final_score, idx, result, orig_score, kw_score) in enumerate(
            scored[:top_k], 1
        ):
            reranked.append(RerankedResult(
                document_id=result.get("id", result.get("document_id", f"doc_{idx}")),
                content=result.get("content", ""),
                metadata=result.get("metadata", {}),
                original_score=orig_score,
                rerank_score=kw_score,
                final_score=final_score,
                rank=rank,
            ))

        rerank_time = (time.time() - start) * 1000

        return RerankerOutput(
            results=reranked,
            query=query,
            original_count=len(results),
            final_count=len(reranked),
            rerank_time_ms=rerank_time,
            metadata={"type": "simple"},
        )


class Reranker:
    """Factory class for creating rerankers."""

    @staticmethod
    def create(config: RerankerConfig = None) -> Any:
        """Create a reranker instance.

        Returns CrossEncoderReranker if sentence-transformers is available,
        otherwise SimpleReranker as fallback.
        """
        config = config or RerankerConfig()

        if config.use_cross_encoder:
            try:
                from sentence_transformers import CrossEncoder
                return CrossEncoderReranker(config)
            except ImportError:
                pass

        return SimpleReranker(config)
