"""Tests for RAG module components."""

import unittest
import numpy as np
from unittest.mock import patch, MagicMock
from typing import List, Dict, Any

from tradingagents.agents.utils.rag.config import (
    VectorStoreType, EmbeddingModelType,
    VectorStoreConfig, EmbeddingModelConfig,
    RetrieverConfig, RerankerConfig,
    CNNewsRetrievalConfig,
)
from tradingagents.agents.utils.rag.vector_store import (
    VectorStore, MemoryVectorStore, Document,
    VectorStoreBase,
)
from tradingagents.agents.utils.rag.retriever import (
    Retriever, BM25, RetrievalResult, RetrievalOutput,
)
from tradingagents.agents.utils.rag.reranker import (
    Reranker, SimpleReranker, RerankedResult,
)


class TestVectorStore(unittest.TestCase):
    """Tests for vector store implementations."""

    def test_memory_vector_store_basic(self):
        """Test basic operations of memory vector store."""
        store = MemoryVectorStore()

        # Create documents
        docs = [
            Document(id="doc1", content="苹果是一家科技公司", metadata={"source": "test"}),
            Document(id="doc2", content="谷歌是搜索引擎公司", metadata={"source": "test"}),
            Document(id="doc3", content="微软开发软件产品", metadata={"source": "test"}),
        ]

        # Generate fake embeddings (in real use, would use actual embeddings)
        embeddings = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9],
        ], dtype=np.float32)

        # Add documents
        doc_ids = store.add_documents(docs, embeddings)
        self.assertEqual(len(doc_ids), 3)

        # Search
        query_embedding = np.array([0.15, 0.25, 0.35], dtype=np.float32)
        results = store.search(query_embedding, top_k=2)

        self.assertLessEqual(len(results), 2)
        for doc, score in results:
            self.assertIsInstance(doc, Document)
            self.assertGreater(score, 0)

    def test_vector_store_filter(self):
        """Test vector store with metadata filtering."""
        store = MemoryVectorStore()

        docs = [
            Document(id="doc1", content="科技新闻", metadata={"sector": "tech"}),
            Document(id="doc2", content="能源新闻", metadata={"sector": "energy"}),
            Document(id="doc3", content="医药新闻", metadata={"sector": "pharma"}),
        ]

        embeddings = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9],
        ], dtype=np.float32)

        store.add_documents(docs, embeddings)

        # Search with filter
        query_embedding = np.array([0.5, 0.5, 0.5], dtype=np.float32)
        results = store.search(
            query_embedding,
            top_k=10,
            filters={"sector": "tech"},
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].id, "doc1")

    def test_vector_store_delete(self):
        """Test document deletion."""
        store = MemoryVectorStore()

        docs = [
            Document(id="doc1", content="测试内容1", metadata={}),
            Document(id="doc2", content="测试内容2", metadata={}),
        ]

        embeddings = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]], dtype=np.float32)
        store.add_documents(docs, embeddings)

        # Delete one document
        store.delete(["doc1"])

        # Verify deletion
        stats = store.get_stats()
        self.assertEqual(stats["total_documents"], 1)


class TestBM25(unittest.TestCase):
    """Tests for BM25 retrieval."""

    def test_bm25_basic(self):
        """Test basic BM25 retrieval."""
        bm25 = BM25(k1=1.5, b=0.75)

        documents = [
            "苹果公司发布新款iPhone",
            "谷歌推出新版搜索引擎",
            "微软云计算业务增长",
            "亚马逊电商平台销售额创新高",
        ]

        bm25.index(documents)

        # Search for relevant documents
        results = bm25.search("苹果 iPhone", top_k=2)

        self.assertGreater(len(results), 0)
        # First result should be document about Apple
        self.assertEqual(results[0][0], 0)  # "苹果公司发布新款iPhone" should be first

    def test_bm25_chinese(self):
        """Test BM25 with Chinese text."""
        bm25 = BM25()

        chinese_docs = [
            "半导体行业迎来新一轮增长周期",
            "光伏产业出口数据创新高",
            "医药板块研发投入持续增加",
            "房地产市场调控政策解读",
        ]

        bm25.index(chinese_docs)

        results = bm25.search("半导体 芯片", top_k=2)

        self.assertGreater(len(results), 0)
        # Should find semiconductor document
        self.assertEqual(results[0][0], 0)


class TestRetriever(unittest.TestCase):
    """Tests for hybrid retriever."""

    def _create_mock_retriever(self):
        """Create a retriever with mocked embedding model."""
        from tradingagents.agents.utils.rag.vector_store import MemoryVectorStore
        from tradingagents.agents.utils.rag.embedding_model import EmbeddingModelBase

        # Create a mock embedding model
        class MockEmbeddingModel(EmbeddingModelBase):
            def __init__(self):
                self._dimension = 384

            def embed(self, texts):
                if isinstance(texts, str):
                    texts = [texts]
                # Return random embeddings
                return np.random.rand(len(texts), self._dimension).astype(np.float32)

            def get_dimension(self):
                return self._dimension

        return Retriever(
            embedding_model=MockEmbeddingModel(),
            vector_store=MemoryVectorStore(),
        )

    def test_retriever_initialization(self):
        """Test retriever can be initialized."""
        # Skip if sentence-transformers not available
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            self.skipTest("sentence-transformers not installed")

        config = RetrieverConfig(
            bm25_weight=0.3,
            vector_weight=0.7,
            initial_top_k=20,
            final_top_k=5,
        )

        retriever = Retriever(config=config)

        self.assertIsNotNone(retriever.bm25)
        self.assertIsNotNone(retriever.embedding_model)
        self.assertIsNotNone(retriever.vector_store)

    def test_retriever_index_documents(self):
        """Test document indexing."""
        retriever = self._create_mock_retriever()

        documents = [
            Document(
                id="doc1",
                content="宁德时代是锂电池龙头企业",
                metadata={"sector": "tech", "ticker": "300750"},
            ),
            Document(
                id="doc2",
                content="隆基绿能是光伏行业龙头",
                metadata={"sector": "energy", "ticker": "601012"},
            ),
        ]

        retriever.index_documents(documents)

        stats = retriever.get_stats()
        self.assertEqual(stats["indexed_documents"], 2)

    def test_retriever_retrieve(self):
        """Test retrieval with a query."""
        retriever = self._create_mock_retriever()

        documents = [
            Document(
                id="doc1",
                content="科创板半导体公司研发投入持续增加",
                metadata={"sector": "tech"},
            ),
            Document(
                id="doc2",
                content="新能源汽车销量增长带动锂电池需求",
                metadata={"sector": "auto"},
            ),
            Document(
                id="doc3",
                content="医药行业创新药研发进展",
                metadata={"sector": "pharma"},
            ),
        ]

        retriever.index_documents(documents)

        # Retrieve
        results = retriever.retrieve(
            query="半导体 芯片 科技",
            top_k=2,
        )

        self.assertIsInstance(results, RetrievalOutput)
        # Should return results
        self.assertGreaterEqual(len(results.results), 1)

    def test_retrieval_output_format(self):
        """Test retrieval output formatting."""
        output = RetrievalOutput(
            results=[
                RetrievalResult(
                    document_id="doc1",
                    content="测试内容",
                    metadata={"source": "test"},
                    score=0.85,
                    source="hybrid",
                    rank=1,
                ),
            ],
            query="测试",
            total_candidates=10,
            retrieval_time_ms=50.5,
        )

        formatted = output.format_for_context(max_results=1, max_chars=100)

        self.assertIn("测试内容", formatted)
        # Check for score in output
        self.assertIn("0.850", formatted)
        self.assertIn("hybrid", formatted)


class TestReranker(unittest.TestCase):
    """Tests for reranker."""

    def test_simple_reranker_initialization(self):
        """Test simple reranker can be initialized."""
        reranker = Reranker.create(RerankerConfig(use_cross_encoder=False))

        self.assertIsInstance(reranker, SimpleReranker)

    def test_simple_reranker_rerank(self):
        """Test simple reranking."""
        reranker = SimpleReranker()

        results = [
            {
                "id": "doc1",
                "content": "苹果公司发布了新款iPhone手机",
                "score": 0.5,
                "metadata": {"date": "2025-01-01"},
            },
            {
                "id": "doc2",
                "content": "谷歌搜索引入AI新技术",
                "score": 0.3,
                "metadata": {"date": "2025-01-05"},
            },
            {
                "id": "doc3",
                "content": "苹果和谷歌都是科技公司",
                "score": 0.7,
                "metadata": {"date": "2025-01-03"},
            },
        ]

        output = reranker.rerank(
            query="苹果公司",
            results=results,
            top_k=3,
        )

        self.assertEqual(output.final_count, 3)
        # Document with "苹果公司" should rank higher due to keyword matching
        self.assertIn("doc1", [r.document_id for r in output.results[:2]])


class TestConfigClasses(unittest.TestCase):
    """Tests for configuration classes."""

    def test_vector_store_config(self):
        """Test VectorStoreConfig."""
        config = VectorStoreConfig(
            store_type=VectorStoreType.MEMORY,
            collection_name="test",
        )

        self.assertEqual(config.store_type, VectorStoreType.MEMORY)
        self.assertEqual(config.collection_name, "test")

    def test_embedding_model_config(self):
        """Test EmbeddingModelConfig with auto-dimension detection."""
        config = EmbeddingModelConfig(
            model_type=EmbeddingModelType.MINI_LM,
            model_name="sentence-transformers/all-MiniLM-L6-v2",
        )

        config.__post_init__()

        self.assertEqual(config.dimension, 384)  # MiniLM dimension

    def test_retriever_config_defaults(self):
        """Test RetrieverConfig defaults."""
        config = RetrieverConfig()

        self.assertEqual(config.bm25_weight, 0.3)
        self.assertEqual(config.vector_weight, 0.7)
        self.assertEqual(config.initial_top_k, 50)
        self.assertEqual(config.final_top_k, 10)


class TestCNNewsRetrievalResult(unittest.TestCase):
    """Tests for CN news retrieval result formatting."""

    def test_format_for_context(self):
        """Test result formatting for LLM context."""
        from tradingagents.agents.utils.rag.cn_news_retriever import CNNewsRetrievalResult

        result = CNNewsRetrievalResult(
            content="这是一条测试新闻内容，用于验证格式化功能。",
            metadata={"sector": "tech"},
            score=0.85,
            source="test_source",
            title="测试标题",
            date="2025-01-01",
        )

        formatted = result.format_for_context(max_length=30)

        self.assertIn("测试标题", formatted)
        self.assertIn("test_source", formatted)
        self.assertIn("2025-01-01", formatted)


class TestRAGIntegration(unittest.TestCase):
    """Integration tests for RAG components."""

    def _create_mock_retriever(self):
        """Create a retriever with mocked embedding model."""
        from tradingagents.agents.utils.rag.vector_store import MemoryVectorStore
        from tradingagents.agents.utils.rag.embedding_model import EmbeddingModelBase

        class MockEmbeddingModel(EmbeddingModelBase):
            def __init__(self):
                self._dimension = 384

            def embed(self, texts):
                if isinstance(texts, str):
                    texts = [texts]
                return np.random.rand(len(texts), self._dimension).astype(np.float32)

            def get_dimension(self):
                return self._dimension

        return Retriever(
            embedding_model=MockEmbeddingModel(),
            vector_store=MemoryVectorStore(),
        )

    def test_full_retrieval_pipeline(self):
        """Test complete retrieval + reranking pipeline."""
        retriever = self._create_mock_retriever()
        reranker = SimpleReranker()

        # Index documents
        documents = [
            Document(
                id=f"doc{i}",
                content=f"测试文档{i}包含一些关于科技公司的内容",
                metadata={"sector": "tech", "index": i},
            )
            for i in range(5)
        ]

        retriever.index_documents(documents)

        # Retrieve
        retrieval_output = retriever.retrieve(
            query="科技公司",
            top_k=5,
        )

        # Rerank
        rerank_input = [
            {
                "id": r.document_id,
                "content": r.content,
                "score": r.score,
                "metadata": r.metadata,
            }
            for r in retrieval_output.results
        ]

        rerank_output = reranker.rerank(
            query="科技公司",
            results=rerank_input,
            top_k=3,
        )

        # Verify
        self.assertGreater(retrieval_output.total_candidates, 0)
        self.assertEqual(rerank_output.final_count, 3)

    def test_empty_query_handling(self):
        """Test handling of empty queries."""
        retriever = self._create_mock_retriever()

        # Should not crash on empty results
        output = retriever.retrieve(query="不存在的关键词xyz123", top_k=5)

        # Should return empty results (no crash)
        self.assertIsInstance(output, RetrievalOutput)


if __name__ == "__main__":
    unittest.main()
