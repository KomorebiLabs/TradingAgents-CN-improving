---
name: rag
description: "Skill for the Rag area of TradingAgents-CN-improving. 122 symbols across 12 files."
---

# Rag

122 symbols | 12 files | Cohesion: 93%

## When to Use

- Working with code in `tradingagents/`
- Understanding how preload_rag_models, ensure_rag_ready, get_security_config work
- Modifying rag-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `tradingagents/agents/utils/rag/vector_store.py` | create, _create_chromadb, _create_qdrant, _compute_similarity, add_documents (+16) |
| `tradingagents/agents/utils/rag/cn_news_retriever.py` | _initialize, index_documents, add_news, get_instance, get_cn_news_retriever (+13) |
| `tradingagents/agents/utils/rag/retriever.py` | __init__, _make_key, get, put, invalidate (+13) |
| `tradingagents/agents/utils/rag/rag_middleware.py` | _get_validator, _get_rate_limiter, _validate_input, _init_rag, _get_rag_results (+11) |
| `tradingagents/agents/utils/rag/embedding_model.py` | create, create_default, EmbeddingModelBase, OpenAIEmbedding, HuggingFaceEmbedding (+9) |
| `tradingagents/agents/utils/rag/performance.py` | get_instance, _notify_ready, preload, _preload_background, _load (+5) |
| `tests/test_rag.py` | test_simple_reranker_initialization, test_bm25_basic, test_bm25_chinese, test_memory_vector_store_basic, test_vector_store_filter (+1) |
| `tests/test_rag_integration.py` | test_lru_cache_basic, test_lru_cache_eviction, test_rag_manager_singleton, test_rag_config_save_load, test_rag_config_to_dict (+1) |
| `tradingagents/agents/utils/rag/security.py` | check_required_keys, get_security_config, get_validator, get_rate_limiter, check_api_keys |
| `tradingagents/agents/utils/rag/config.py` | to_dict, from_dict, save, load |

## Entry Points

Start here when exploring this area:

- **`preload_rag_models`** (Function) — `tradingagents/agents/utils/rag/performance.py:222`
- **`ensure_rag_ready`** (Function) — `tradingagents/agents/utils/rag/performance.py:246`
- **`get_security_config`** (Function) — `tradingagents/agents/utils/rag/security.py:467`
- **`get_validator`** (Function) — `tradingagents/agents/utils/rag/security.py:480`
- **`get_rate_limiter`** (Function) — `tradingagents/agents/utils/rag/security.py:488`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `EmbeddingModelBase` | Class | `tradingagents/agents/utils/rag/embedding_model.py` | 18 |
| `OpenAIEmbedding` | Class | `tradingagents/agents/utils/rag/embedding_model.py` | 32 |
| `HuggingFaceEmbedding` | Class | `tradingagents/agents/utils/rag/embedding_model.py` | 68 |
| `MiniLMEmbedding` | Class | `tradingagents/agents/utils/rag/embedding_model.py` | 137 |
| `BGEEmbedding` | Class | `tradingagents/agents/utils/rag/embedding_model.py` | 150 |
| `VectorStoreBase` | Class | `tradingagents/agents/utils/rag/vector_store.py` | 29 |
| `MemoryVectorStore` | Class | `tradingagents/agents/utils/rag/vector_store.py` | 67 |
| `FAISSVectorStore` | Class | `tradingagents/agents/utils/rag/vector_store.py` | 247 |
| `ChromaDBVectorStore` | Class | `tradingagents/agents/utils/rag/vector_store.py` | 470 |
| `NewsDocument` | Class | `tradingagents/agents/utils/rag/cn_news_retriever.py` | 26 |
| `Document` | Class | `tradingagents/agents/utils/rag/vector_store.py` | 21 |
| `preload_rag_models` | Function | `tradingagents/agents/utils/rag/performance.py` | 222 |
| `ensure_rag_ready` | Function | `tradingagents/agents/utils/rag/performance.py` | 246 |
| `get_security_config` | Function | `tradingagents/agents/utils/rag/security.py` | 467 |
| `get_validator` | Function | `tradingagents/agents/utils/rag/security.py` | 480 |
| `get_rate_limiter` | Function | `tradingagents/agents/utils/rag/security.py` | 488 |
| `check_api_keys` | Function | `tradingagents/agents/utils/rag/security.py` | 496 |
| `get_rag_manager` | Function | `tradingagents/agents/utils/rag/cn_news_retriever.py` | 599 |
| `get_cn_news_retriever` | Function | `tradingagents/agents/utils/rag/cn_news_retriever.py` | 604 |
| `get_middleware` | Function | `tradingagents/agents/utils/rag/rag_middleware.py` | 411 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Execute → Get_security_config` | cross_community | 5 |
| `Execute_with_rag → Get_security_config` | cross_community | 5 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Dataflows | 2 calls |

## How to Explore

1. `gitnexus_context({name: "preload_rag_models"})` — see callers and callees
2. `gitnexus_query({query: "rag"})` — find related execution flows
3. Read key files listed above for implementation details
