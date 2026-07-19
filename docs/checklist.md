# Customer Agent Project Checklist

This document tracks the implemented features, their core files, and algorithms, as well as upcoming features for the multi-state agent system.

---

## Completed Core Features

### 1. Document Ingestion (Semantic & Hierarchical Chunking)
* **Files**: [ingest_pipeline.py](file:///r:/python/customer_agent/agent/src/app/pipelines/ingest_pipeline.py) & [chunking_service.py](file:///r:/python/customer_agent/agent/src/app/services/chunking_service.py)
* **Core Algo**: Uses LlamaParse to extract structured layout JSON, splits documents into structural blocks matching heading levels, and applies embedding semantic similarity thresholding to merge or divide chunks.

### 2. Query Rewrite & Multi-Query Expansion
* **File**: [query_optimizer.py](file:///r:/python/customer_agent/agent/src/app/services/query_optimizer.py)
* **Core Algo**: Rewrites conversational queries by resolving history pronouns and uses Qwen/OpenAI to translate Punjabi/Hinglish agricultural terms into exactly 3 English search variations.

### 3. Parallel Hybrid Search (Dense + Sparse)
* **Files**: [retrieval_service.py](file:///r:/python/customer_agent/agent/src/app/services/retrieval_service.py) & [embedding_service.py](file:///r:/python/customer_agent/agent/src/app/services/embedding_service.py)
* **Core Algo**: Batch generates dense vector embeddings (via Jina API) and sparse term-frequency vectors (via a custom SHA-256 Hashing Trick tokenizer), concurrently querying Pinecone namespaces in parallel threads via `asyncio.gather`.

### 4. Reranking (Jina Rerank v2 + Local RRF Fallback)
* **Files**: [reranking_service.py](file:///r:/python/customer_agent/agent/src/app/services/reranking_service.py) & integrated in [retrieval_service.py](file:///r:/python/customer_agent/agent/src/app/services/retrieval_service.py)
* **Core Algo**: Sends search candidates to Jina Rerank v2 API for deep cross-encoder semantic scoring. If the API fails or is inactive, falls back to local Reciprocal Rank Fusion (RRF) to merge query rank positions mathematically.


---

