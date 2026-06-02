"""
Fake Implementations for Testing.

Fake是有真实实现的测试替身，与Mock的区别：
- Mock: 每次测试重新生成，不知道内部逻辑
- Fake: 有实现逻辑，可以复用，一致性好

使用原则：
1. 接口与真实实现一致
2. 行为与真实实现相似（可配置偏差）
3. 可配置返回结果
4. 跨测试复用
"""

from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
import numpy as np
from datetime import datetime, timedelta


# ============================================================================
# Fake Embedding Model
# ============================================================================

class FakeEmbeddingModel:
    """
    假嵌入模型实现。

    特性:
    - 确定性：相同文本产生相同向量
    - 可配置维度
    - 可配置延迟（模拟真实模型）
    - 支持批量
    """

    def __init__(
        self,
        dimension: int = 384,
        delay_ms: float = 0,
        seed: int = 42,
    ):
        self.dimension = dimension
        self.delay_ms = delay_ms
        self.seed = seed
        self.rng = np.random.RandomState(seed)
        self._call_count = 0

        # 缓存已计算的嵌入
        self._cache: Dict[str, np.ndarray] = {}

    def embed(self, texts: str | List[str]) -> np.ndarray:
        """生成嵌入向量."""
        import time

        self._call_count += 1

        # 模拟延迟
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000)

        if isinstance(texts, str):
            texts = [texts]

        embeddings = []
        for text in texts:
            if text in self._cache:
                embeddings.append(self._cache[text])
            else:
                # 生成确定性向量
                vec = self._generate_deterministic(text)
                self._cache[text] = vec
                embeddings.append(vec)

        return np.array(embeddings, dtype=np.float32)

    def _generate_deterministic(self, text: str) -> np.ndarray:
        """生成确定性向量（相同文本→相同向量）."""
        # 使用文本的hash作为种子的一部分
        text_hash = hash(text) + self.seed
        rng = np.random.RandomState(text_hash % (2**31))

        vec = rng.randn(self.dimension).astype(np.float32)
        # L2 归一化
        vec = vec / (np.linalg.norm(vec) + 1e-8)
        return vec

    def get_dimension(self) -> int:
        return self.dimension

    def get_call_count(self) -> int:
        return self._call_count

    def reset_cache(self):
        """重置缓存."""
        self._cache.clear()
        self._call_count = 0


# ============================================================================
# Fake Vector Store
# ============================================================================

class FakeVectorStore:
    """
    假向量存储实现。

    使用简单的内存存储+余弦相似度。
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.documents: Dict[str, Dict] = {}
        self.embeddings: Dict[str, np.ndarray] = {}
        self._doc_id_counter = 0

    def add_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict]] = None,
        embeddings: Optional[np.ndarray] = None,
    ) -> List[str]:
        """添加文档."""
        doc_ids = []

        for i, text in enumerate(texts):
            self._doc_id_counter += 1
            doc_id = f"doc_{self._doc_id_counter}"

            metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
            embedding = embeddings[i] if embeddings is not None else None

            self.documents[doc_id] = {
                "text": text,
                "metadata": metadata,
            }
            self.embeddings[doc_id] = embedding

            doc_ids.append(doc_id)

        return doc_ids

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[Tuple[str, float, Dict]]:
        """
        搜索相似文档.

        Returns:
            List of (doc_id, score, metadata)
        """
        results = []

        for doc_id, embedding in self.embeddings.items():
            if embedding is None:
                continue

            # 计算余弦相似度
            score = self._cosine_similarity(query_embedding, embedding)

            # 应用过滤器
            if filters:
                metadata = self.documents[doc_id]["metadata"]
                if not self._match_filters(metadata, filters):
                    continue

            results.append((
                doc_id,
                float(score),
                self.documents[doc_id]["metadata"],
            ))

        # 按分数排序
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:top_k]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """计算余弦相似度."""
        # 确保是一维向量
        a_flat = a.flatten()
        b_flat = b.flatten()
        
        norm_a = np.linalg.norm(a_flat)
        norm_b = np.linalg.norm(b_flat)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        dot_product = np.dot(a_flat, b_flat)
        return float(dot_product / (norm_a * norm_b))

    def _match_filters(self, metadata: Dict, filters: Dict) -> bool:
        """检查是否匹配过滤器."""
        for key, value in filters.items():
            if key not in metadata:
                return False
            if metadata[key] != value:
                return False
        return True

    def get_document(self, doc_id: str) -> Optional[Dict]:
        return self.documents.get(doc_id)

    def delete(self, doc_ids: List[str]) -> None:
        for doc_id in doc_ids:
            self.documents.pop(doc_id, None)
            self.embeddings.pop(doc_id, None)

    def count(self) -> int:
        return len(self.documents)


# ============================================================================
# Fake Retriever
# ============================================================================

@dataclass
class FakeRetrievalResult:
    """假检索结果."""
    content: str
    score: float
    source: str = "fake"
    date: str = ""
    sector: str = ""


class FakeRetriever:
    """
    假检索器实现。

    使用预定义数据集进行检索。
    """

    def __init__(self, dimension: int = 384):
        self.embedding_model = FakeEmbeddingModel(dimension=dimension)
        self.vector_store = FakeVectorStore(dimension=dimension)
        self._initialized = False
        self._documents: List[FakeRetrievalResult] = []

    def initialize(self, documents: List[FakeRetrievalResult]):
        """初始化假检索器（添加预设文档）."""
        self._documents = documents

        texts = [doc.content for doc in documents]
        metadatas = [
            {"source": doc.source, "date": doc.date, "sector": doc.sector}
            for doc in documents
        ]

        embeddings = self.embedding_model.embed(texts)
        self.vector_store.add_documents(texts, metadatas, embeddings)
        self._initialized = True

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[FakeRetrievalResult]:
        """检索相关文档."""
        if not self._initialized:
            return []

        query_embedding = self.embedding_model.embed(query)
        results = self.vector_store.search(query_embedding, top_k, filters)

        retrieval_results = []
        for doc_id, score, metadata in results:
            doc_text = self.vector_store.get_document(doc_id)["text"]
            # 找到对应的原始文档
            for doc in self._documents:
                if doc.content == doc_text:
                    retrieval_results.append(FakeRetrievalResult(
                        content=doc.content,
                        score=score,
                        source=doc.source,
                        date=doc.date,
                        sector=doc.sector,
                    ))
                    break

        return retrieval_results

    def format_for_llm_context(
        self,
        results: List[FakeRetrievalResult],
        max_results: int = 10,
    ) -> str:
        """格式化检索结果为LLM上下文."""
        if not results:
            return "No relevant documents found."

        lines = []
        for i, result in enumerate(results[:max_results], 1):
            lines.append(f"## Document {i} [Score: {result.score:.3f}]")
            lines.append(f"Source: {result.source}")
            if result.date:
                lines.append(f"Date: {result.date}")
            if result.sector:
                lines.append(f"Sector: {result.sector}")
            lines.append("")
            lines.append(result.content)
            lines.append("")

        return "\n".join(lines)


# ============================================================================
# Fake News Data
# ============================================================================

class FakeNewsData:
    """
    假新闻数据生成器。

    生成逼真的测试数据。
    """

    @staticmethod
    def generate_news(
        ticker: str = "AAPL",
        start_date: str = "2025-01-01",
        end_date: str = "2025-01-07",
        num_articles: int = 5,
    ) -> str:
        """生成假新闻数据."""
        lines = [f"News for {ticker} ({start_date} to {end_date})", "=" * 50, ""]

        base_date = datetime.strptime(start_date, "%Y-%m-%d")

        for i in range(num_articles):
            date = base_date + timedelta(days=i)
            lines.append(f"Date: {date.strftime('%Y-%m-%d')}")
            lines.append(f"Headline: {ticker} Reports Q{i+1} Earnings, Revenue {['Up', 'Down'][i % 2]} {5 + i}%")
            lines.append(f"Summary: {ticker} announced quarterly results. Key metrics show growth in key markets.")
            lines.append("-" * 50)
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def generate_cn_news(
        sector: str = "tech",
        curr_date: str = "2025-01-07",
        num_articles: int = 5,
    ) -> str:
        """生成假中国A股新闻."""
        sector_templates = {
            "tech": [
                "半导体行业迎来政策利好",
                "芯片国产替代进程加速",
                "科创板上市公司业绩预增",
            ],
            "new_energy": [
                "新能源汽车销量持续增长",
                "光伏产业链价格企稳回升",
                "储能市场规模扩大",
            ],
            "pharma": [
                "创新药研发取得突破进展",
                "医疗器械板块受政策支持",
                "中药现代化进程加快",
            ],
            "real_estate": [
                "房地产市场政策暖风频吹",
                "保障房建设加速推进",
                "房地产融资环境改善",
            ],
            "fintech": [
                "数字人民币试点范围扩大",
                "金融科技监管框架完善",
                "支付行业创新发展",
            ],
        }

        templates = sector_templates.get(sector, sector_templates["tech"])

        lines = [f"{sector.upper()} Sector News - {curr_date}", "=" * 50, ""]

        for i, template in enumerate(templates[:num_articles]):
            lines.append(f"## News {i+1}")
            lines.append(f"Title: {template}")
            lines.append(f"Content: 近日，{template}。市场分析师表示，相关产业链将持续受益。")
            lines.append("-" * 50)
            lines.append("")

        return "\n".join(lines)


# ============================================================================
# Fake Reranker
# ============================================================================

class FakeReranker:
    """
    假重排器。

    基于简单的相关性分数进行重排。
    """

    def __init__(self, top_k: int = 10):
        self.top_k = top_k

    def rerank(
        self,
        query: str,
        results: List[Tuple[str, float, Dict]],
    ) -> List[Tuple[str, float, Dict]]:
        """重排结果."""
        # 简单的基于长度和关键词的调整
        query_words = set(query.lower().split())

        reranked = []
        for doc_id, score, metadata in results:
            # 简单的相关性调整
            content = metadata.get("text", "")
            if content:
                content_words = set(content.lower().split())
                overlap = len(query_words & content_words)
                boost = 1.0 + (overlap * 0.01)
                score *= boost

            reranked.append((doc_id, score, metadata))

        # 重新排序
        reranked.sort(key=lambda x: x[1], reverse=True)

        return reranked[:self.top_k]
