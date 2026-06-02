"""
Integration tests for RAG system.

These tests use real components (not mocks) to verify the full pipeline.
Tests are designed to run quickly without loading heavy ML models.
"""

import os
import shutil
import tempfile
import unittest
import sys
from pathlib import Path

# Ensure the project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set environment variables before imports
os.environ["TRADINGAGENTS_RAG_CACHE_SIZE"] = "100"
os.environ["TRADINGAGENTS_RAG_CACHE_TTL"] = "3600"


class TestRAGIntegrationFullPipeline(unittest.TestCase):
    """Full integration tests for RAG pipeline."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        cls.test_dir = tempfile.mkdtemp(prefix="rag_test_")
        cls.persist_dir = os.path.join(cls.test_dir, "rag_data")
        os.makedirs(cls.persist_dir, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up test fixtures."""
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_vector_store_persistence(self):
        """Test that memory vector store can persist and load."""
        from tradingagents.agents.utils.rag import VectorStore, VectorStoreConfig, VectorStoreType, Document
        import numpy as np

        # Create config with persist directory
        config = VectorStoreConfig(
            store_type=VectorStoreType.MEMORY,
            persist_directory=self.persist_dir,
            collection_name="test_persist",
        )

        # Create store and add documents
        store = VectorStore.create(VectorStoreType.MEMORY, config, auto_load=False)

        docs = [
            Document(
                id="doc1",
                content="Apple stock news",
                metadata={"source": "test"},
            ),
            Document(
                id="doc2",
                content="Tesla earnings report",
                metadata={"source": "test"},
            ),
        ]

        embeddings = np.array([[0.1, 0.2, 0.3] * 128, [0.4, 0.5, 0.6] * 128], dtype=np.float32)
        store.add_documents(docs, embeddings)

        # Verify documents added
        stats = store.get_stats()
        self.assertEqual(stats["total_documents"], 2)

        # Persist
        store.persist()

        # Create new store with same config (should load persisted data)
        store2 = VectorStore.create(VectorStoreType.MEMORY, config, auto_load=True)

        # Verify persisted data loaded
        stats2 = store2.get_stats()
        self.assertEqual(stats2["total_documents"], 2)
        self.assertTrue(stats2["persisted"])

        # Cleanup
        VectorStore.clear_cache()

    def test_lru_cache_basic(self):
        """Test basic LRU cache functionality."""
        from tradingagents.agents.utils.rag.retriever import LRUCache

        cache = LRUCache(max_size=10, ttl_seconds=3600)

        # Test put and get
        cache.put("key1", value="value1")
        result = cache.get("key1")
        self.assertEqual(result, "value1")

        # Test cache miss
        result = cache.get("nonexistent")
        self.assertIsNone(result)

        # Test stats
        stats = cache.get_stats()
        self.assertEqual(stats["size"], 1)
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)

        # Test clear
        cleared = cache.invalidate()
        self.assertEqual(cleared, 1)

    def test_lru_cache_eviction(self):
        """Test LRU cache eviction policy."""
        from tradingagents.agents.utils.rag.retriever import LRUCache

        cache = LRUCache(max_size=3, ttl_seconds=3600)

        # Fill cache
        for i in range(5):
            cache.put(f"key{i}", value=f"value{i}")

        # Should have only 3 items (oldest evicted)
        stats = cache.get_stats()
        self.assertLessEqual(stats["size"], 3)

    def test_interface_rag_imports(self):
        """Test that interface.py RAG functions are importable."""
        from tradingagents.dataflows.interface import (
            route_to_vendor_with_rag,
            _is_rag_enabled,
            _is_rag_supported_method,
        )

        # Test _is_rag_enabled
        enabled = _is_rag_enabled()
        self.assertIsInstance(enabled, bool)

        # Test _is_rag_supported_method
        self.assertTrue(_is_rag_supported_method("get_news"))
        self.assertTrue(_is_rag_supported_method("get_cn_tech_sector_news"))
        self.assertFalse(_is_rag_supported_method("get_stock_data"))

    def test_rag_manager_singleton(self):
        """Test that RAGManager is a proper singleton."""
        from tradingagents.agents.utils.rag import RAGManager

        # Get two instances
        manager1 = RAGManager.get_instance()
        manager2 = RAGManager.get_instance()

        # Should be the same object
        self.assertIs(manager1, manager2)

        # Test reset
        manager1.reset()
        self.assertFalse(manager1.is_initialized())

    def test_merge_rag_and_raw(self):
        """Test _merge_rag_and_raw function."""
        from tradingagents.dataflows.interface import _merge_rag_and_raw

        rag_result = "RAG: Apple stock news"
        raw_result = "Raw: Historical prices"

        merged = _merge_rag_and_raw(rag_result, raw_result)

        self.assertIn("RAG增强信息", merged)
        self.assertIn("原始数据", merged)
        self.assertIn("RAG: Apple stock news", merged)
        self.assertIn("Raw: Historical prices", merged)

    def test_build_rag_query(self):
        """Test _build_rag_query function."""
        from tradingagents.dataflows.interface import _build_rag_query

        # Test with ticker
        query = _build_rag_query("get_news", "AAPL", {})
        self.assertIn("AAPL", query)

        # Test with topic
        kwargs = {"topic": "market"}
        query = _build_rag_query("get_global_news", "MSFT", kwargs)
        self.assertIn("market", query)

    def test_extract_sector(self):
        """Test _extract_sector_from_method function."""
        from tradingagents.dataflows.interface import _extract_sector_from_method

        self.assertEqual(_extract_sector_from_method("get_cn_tech_sector_news"), "tech")
        self.assertEqual(_extract_sector_from_method("get_cn_pharma_news"), "pharma")
        self.assertEqual(_extract_sector_from_method("get_news"), "")


class TestRAGConfigPersistence(unittest.TestCase):
    """Test RAG configuration persistence."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="rag_config_test_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_rag_config_save_load(self):
        """Test RAGConfig save and load."""
        from tradingagents.agents.utils.rag import RAGConfig

        config = RAGConfig(
            enabled=True,
            fallback_to_raw=True,
            cache_results=True,
        )

        config_path = os.path.join(self.test_dir, "rag_config.json")
        config.save(config_path)

        # Verify file exists
        self.assertTrue(os.path.exists(config_path))

        # Load config
        loaded_config = RAGConfig.load(config_path)

        # Verify values
        self.assertEqual(loaded_config.enabled, True)
        self.assertEqual(loaded_config.fallback_to_raw, True)
        self.assertEqual(loaded_config.cache_results, True)

    def test_rag_config_to_dict(self):
        """Test RAGConfig to_dict method."""
        from tradingagents.agents.utils.rag import RAGConfig

        config = RAGConfig(
            enabled=True,
            fallback_to_raw=False,
        )

        data = config.to_dict()

        self.assertIn("enabled", data)
        self.assertIn("fallback_to_raw", data)
        self.assertEqual(data["enabled"], True)
        self.assertEqual(data["fallback_to_raw"], False)


class TestRAGNewsTools(unittest.TestCase):
    """Test RAG news tools integration."""

    def test_get_rag_status(self):
        """Test get_rag_status function."""
        from tradingagents.agents.utils.rag_news_tools import get_rag_status

        status = get_rag_status()
        self.assertIsInstance(status, dict)
        self.assertIn("enabled", status)
        self.assertIn("initialized", status)

    def test_is_rag_enabled_env(self):
        """Test _is_rag_enabled function with env var."""
        from tradingagents.agents.utils.rag_news_tools import _is_rag_enabled

        # Default should be False
        result = _is_rag_enabled()
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
