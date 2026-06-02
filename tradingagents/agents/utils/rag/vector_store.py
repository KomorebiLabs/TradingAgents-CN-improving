"""
Vector Store Abstraction Layer.

Provides a unified interface for different vector databases:
- ChromaDB (persistent, serverless)
- FAISS (in-memory, fast)
- Qdrant (production-ready, cloud-native)
- Memory (fallback, no persistence)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import json
from pathlib import Path

from .config import VectorStoreConfig, VectorStoreType


@dataclass
class Document:
    """Represents a document in the vector store."""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[np.ndarray] = None


class VectorStoreBase(ABC):
    """Abstract base class for vector stores."""

    @abstractmethod
    def add_documents(
        self,
        documents: List[Document],
        embeddings: np.ndarray,
    ) -> List[str]:
        """Add documents to the store."""
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Document, float]]:
        """Search for similar documents."""
        pass

    @abstractmethod
    def delete(self, document_ids: List[str]) -> None:
        """Delete documents by ID."""
        pass

    @abstractmethod
    def persist(self) -> None:
        """Persist the vector store to disk."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the store."""
        pass


class MemoryVectorStore(VectorStoreBase):
    """In-memory vector store (fallback implementation)."""

    def __init__(self, config: VectorStoreConfig = None):
        self.config = config or VectorStoreConfig()
        self.documents: Dict[str, Document] = {}
        self.embeddings: Dict[str, np.ndarray] = {}
        self._embedding_matrix: Optional[np.ndarray] = None
        self._id_list: List[str] = []

    def _rebuild_matrix(self):
        """Rebuild the embedding matrix for similarity search."""
        if not self.documents:
            self._embedding_matrix = None
            self._id_list = []
            return

        self._id_list = list(self.documents.keys())
        self._embedding_matrix = np.array([
            self.embeddings[doc_id] for doc_id in self._id_list
        ], dtype=np.float32)

    def _compute_similarity(
        self,
        query: np.ndarray,
        top_k: int,
    ) -> List[Tuple[int, float]]:
        """Compute cosine similarity between query and all embeddings."""
        if self._embedding_matrix is None:
            return []

        # Normalize for cosine similarity
        query_norm = query / (np.linalg.norm(query) + 1e-8)
        matrix_norm = self._embedding_matrix / (
            np.linalg.norm(self._embedding_matrix, axis=1, keepdims=True) + 1e-8
        )

        similarities = np.dot(matrix_norm, query_norm)
        top_indices = np.argsort(similarities)[::-1][:top_k]

        return [(idx, float(similarities[idx])) for idx in top_indices]

    def add_documents(
        self,
        documents: List[Document],
        embeddings: np.ndarray,
    ) -> List[str]:
        doc_ids = []
        for i, doc in enumerate(documents):
            self.documents[doc.id] = doc
            self.embeddings[doc.id] = embeddings[i]
            doc_ids.append(doc.id)

        self._rebuild_matrix()
        return doc_ids

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Document, float]]:
        results = self._compute_similarity(query_embedding, top_k * 2)  # Over-fetch for filtering

        output = []
        for idx, score in results:
            if idx >= len(self._id_list):
                continue
            doc_id = self._id_list[idx]
            doc = self.documents.get(doc_id)

            if doc is None:
                continue

            # Apply filters
            if filters:
                matches = True
                for key, value in filters.items():
                    doc_value = doc.metadata.get(key)
                    if isinstance(value, list):
                        if doc_value not in value:
                            matches = False
                            break
                    else:
                        if doc_value != value:
                            matches = False
                            break
                if not matches:
                    continue

            output.append((doc, score))
            if len(output) >= top_k:
                break

        return output

    def delete(self, document_ids: List[str]) -> None:
        for doc_id in document_ids:
            self.documents.pop(doc_id, None)
            self.embeddings.pop(doc_id, None)
        self._rebuild_matrix()

    def persist(self) -> None:
        """Persist memory store to disk.

        Saves documents, embeddings, and metadata to a JSON file.
        """
        import os

        persist_dir = self.config.persist_directory or "./rag_data"
        persist_path = Path(persist_dir) / f"{self.config.collection_name}_memory.json"

        # Ensure directory exists
        os.makedirs(persist_dir, exist_ok=True)

        # Prepare data for serialization
        data = {
            "documents": {},
            "dimension": self._embedding_matrix.shape[1] if self._embedding_matrix is not None else 0,
        }

        for doc_id, doc in self.documents.items():
            data["documents"][doc_id] = {
                "id": doc.id,
                "content": doc.content,
                "metadata": doc.metadata,
                "embedding": self.embeddings[doc_id].tolist() if doc_id in self.embeddings else None,
            }

        with open(persist_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def load(self) -> bool:
        """Load memory store from disk.

        Returns:
            True if loaded successfully, False if no saved data found.
        """
        import os

        persist_dir = self.config.persist_directory or "./rag_data"
        persist_path = Path(persist_dir) / f"{self.config.collection_name}_memory.json"

        if not persist_path.exists():
            return False

        with open(persist_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.documents = {}
        self.embeddings = {}

        for doc_id, doc_data in data.get("documents", {}).items():
            doc = Document(
                id=doc_data["id"],
                content=doc_data["content"],
                metadata=doc_data["metadata"],
            )
            self.documents[doc_id] = doc
            if doc_data.get("embedding"):
                self.embeddings[doc_id] = np.array(doc_data["embedding"], dtype=np.float32)

        self._rebuild_matrix()
        return True

    def get_stats(self) -> Dict[str, Any]:
        import os
        persist_dir = self.config.persist_directory or "./rag_data"
        persist_path = Path(persist_dir) / f"{self.config.collection_name}_memory.json"

        stats = {
            "type": "memory",
            "total_documents": len(self.documents),
            "total_embeddings": len(self.embeddings),
            "dimension": self._embedding_matrix.shape[1] if self._embedding_matrix is not None else 0,
            "persisted": os.path.exists(str(persist_path)),
        }
        return stats


class FAISSVectorStore(VectorStoreBase):
    """FAISS-based vector store (requires faiss-cpu or faiss-gpu)."""

    def __init__(self, config: VectorStoreConfig = None):
        self.config = config or VectorStoreConfig()
        self.documents: Dict[str, Document] = {}
        self._index = None
        self._id_to_idx: Dict[str, int] = {}
        self._idx_to_id: Dict[int, str] = {}

        self._init_faiss()

    def _init_faiss(self):
        """Initialize FAISS index."""
        try:
            import faiss
            dimension = self.config.extra_config.get("dimension", 384)
            self._index = faiss.IndexFlatIP(dimension)  # Inner product for normalized vectors
            self._documents: Dict[int, Document] = {}
        except ImportError:
            raise ImportError(
                "FAISS not installed. Install with: pip install faiss-cpu (or faiss-gpu)"
            )

    def add_documents(
        self,
        documents: List[Document],
        embeddings: np.ndarray,
    ) -> List[str]:
        import faiss

        doc_ids = []
        for i, doc in enumerate(documents):
            doc_id = doc.id
            idx = len(self._documents)
            self.documents[doc_id] = doc
            self._id_to_idx[doc_id] = idx
            self._idx_to_id[idx] = doc_id
            self._documents[idx] = doc
            doc_ids.append(doc_id)

        # Normalize embeddings for cosine similarity
        normalized = embeddings.astype(np.float32)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = normalized / (norms + 1e-8)

        self._index.add(normalized)
        return doc_ids

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Document, float]]:
        import faiss

        # Normalize query
        query = query_embedding.astype(np.float32).reshape(1, -1)
        query = query / (np.linalg.norm(query) + 1e-8)

        # Search
        scores, indices = self._index.search(query, min(top_k * 3, self._index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            doc = self._documents.get(int(idx))
            if doc is None:
                continue

            # Apply filters
            if filters:
                matches = True
                for key, value in filters.items():
                    doc_value = doc.metadata.get(key)
                    if isinstance(value, list):
                        if doc_value not in value:
                            matches = False
                            break
                    else:
                        if doc_value != value:
                            matches = False
                            break
                if not matches:
                    continue

            results.append((doc, float(score)))
            if len(results) >= top_k:
                break

        return results

    def delete(self, document_ids: List[str]) -> None:
        # FAISS doesn't support efficient deletion, mark as deleted
        for doc_id in document_ids:
            self.documents.pop(doc_id, None)
            idx = self._id_to_idx.pop(doc_id, None)
            if idx is not None:
                self._idx_to_id.pop(idx, None)
                self._documents.pop(idx, None)

    def persist(self) -> None:
        if not self.config.persist_directory:
            return

        import faiss
        persist_path = Path(self.config.persist_directory) / f"{self.config.collection_name}.index"
        persist_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(persist_path))

        # Save metadata
        metadata_path = persist_path.with_suffix(".json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump({
                "documents": {k: {"id": v.id, "metadata": v.metadata} for k, v in self.documents.items()},
                "id_to_idx": self._id_to_idx,
            }, f, ensure_ascii=False)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "type": "faiss",
            "total_documents": len(self.documents),
            "index_size": self._index.ntotal if self._index else 0,
        }


class VectorStore:
    """Factory class for creating vector stores."""

    _stores: Dict[str, VectorStoreBase] = {}

    @classmethod
    def create(
        cls,
        store_type: VectorStoreType,
        config: VectorStoreConfig = None,
        name: str = "default",
        auto_load: bool = True,
    ) -> VectorStoreBase:
        """Create a vector store instance.

        Args:
            store_type: Type of vector store to create
            config: Configuration for the store
            name: Name for caching (optional)
            auto_load: Whether to automatically load persisted data

        Returns:
            VectorStoreBase instance
        """
        config = config or VectorStoreConfig(store_type=store_type)

        # Check if we have a cached instance
        cache_key = f"{name}_{store_type.value}"
        if cache_key in cls._stores:
            return cls._stores[cache_key]

        if store_type == VectorStoreType.MEMORY:
            store = MemoryVectorStore(config)
            if auto_load:
                store.load()  # Try to load persisted data
            cls._stores[cache_key] = store
            return store
        elif store_type == VectorStoreType.FAISS:
            store = FAISSVectorStore(config)
            cls._stores[cache_key] = store
            return store
        elif store_type == VectorStoreType.CHROMADB:
            store = cls._create_chromadb(config)
            cls._stores[cache_key] = store
            return store
        elif store_type == VectorStoreType.QDRANT:
            store = cls._create_qdrant(config)
            cls._stores[cache_key] = store
            return store
        else:
            store = MemoryVectorStore(config)
            if auto_load:
                store.load()
            return store

    @classmethod
    def get_stores(cls) -> Dict[str, VectorStoreBase]:
        """Get all cached vector store instances."""
        return cls._stores.copy()

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached vector store instances."""
        cls._stores.clear()

    @classmethod
    def _create_chromadb(cls, config: VectorStoreConfig):
        """Create ChromaDB vector store."""
        try:
            import chromadb
            from chromadb.config import Settings

            persist_dir = config.persist_directory or "./chroma_db"
            client = chromadb.Client(Settings(
                persist_directory=persist_dir,
                anonymized_telemetry=False,
            ))

            collection = client.get_or_create_collection(
                name=config.collection_name,
                metadata={"hnsw:space": config.distance_metric}
            )

            return ChromaDBVectorStore(client, collection, config)
        except ImportError:
            raise ImportError(
                "ChromaDB not installed. Install with: pip install chromadb"
            )

    @classmethod
    def _create_qdrant(cls, config: VectorStoreConfig):
        """Create Qdrant vector store."""
        raise NotImplementedError("Qdrant support coming soon")


class ChromaDBVectorStore(VectorStoreBase):
    """ChromaDB vector store implementation."""

    def __init__(self, client, collection, config: VectorStoreConfig):
        self.client = client
        self.collection = collection
        self.config = config

    def add_documents(
        self,
        documents: List[Document],
        embeddings: np.ndarray,
    ) -> List[str]:
        self.collection.add(
            ids=[doc.id for doc in documents],
            embeddings=embeddings.tolist(),
            documents=[doc.content for doc in documents],
            metadatas=[doc.metadata for doc in documents],
        )
        return [doc.id for doc in documents]

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Document, float]]:
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=filters,
        )

        output = []
        for i, doc_id in enumerate(results["ids"][0]):
            doc = Document(
                id=doc_id,
                content=results["documents"][0][i],
                metadata=results["metadatas"][0][i],
            )
            distance = results["distances"][0][i]
            # Convert distance to similarity score
            score = 1.0 / (1.0 + distance)
            output.append((doc, score))

        return output

    def delete(self, document_ids: List[str]) -> None:
        self.collection.delete(ids=document_ids)

    def persist(self) -> None:
        # ChromaDB auto-persists
        pass

    def get_stats(self) -> Dict[str, Any]:
        return {
            "type": "chromadb",
            "total_documents": self.collection.count(),
        }
