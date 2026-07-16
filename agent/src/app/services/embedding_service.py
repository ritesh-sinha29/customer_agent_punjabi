import asyncio
import hashlib
import logging
import re
from typing import Any, Dict, List

import httpx

from src.app.core.config import settings

logger = logging.getLogger("EmbeddingService")


class EmbeddingService:
    """
    Handles Step 4: Dense and Sparse vector generation.
    Supports external TEI / vLLM HTTP endpoints, falling back to local SentenceTransformers.
    """

    def __init__(self):
        self.api_url = settings.EMBEDDING_API_URL
        self._local_model = None
        self.model_name = "mixedbread-ai/mxbai-embed-large-v1"  # 1024 dimensions model to match Pinecone index

    def _get_local_model(self):
        """
        Lazy-loads local SentenceTransformer model.
        """
        if self._local_model is None:
            logger.info(
                f"Initializing local SentenceTransformer ({self.model_name}) for dense embeddings..."
            )
            try:
                from sentence_transformers import SentenceTransformer

                self._local_model = SentenceTransformer(self.model_name)
                logger.info("Local SentenceTransformer loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load local SentenceTransformer: {e}")
                raise e
        return self._local_model

    async def get_dense_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates dense vector embeddings.
        If OPENAI_API_KEY is configured, uses OpenAI's text-embedding-3-small (1024 dimensions).
        If EMBEDDING_API_URL is configured, queries the TEI/vLLM endpoint.
        Otherwise, runs embedding generation locally using SentenceTransformer.
        """
        if not texts:
            return []

        # 1. (Commented out for Jina testing) Try OpenAI embedding small (1024 dim) if configured
        # if settings.OPENAI_API_KEY:
        #     logger.info("[Step 4 - Embedding] Generating dense embeddings using OpenAI text-embedding-3-small (1024d)...")
        #     try:
        #         batch_size = 32
        #         all_embeddings = []
        #         headers = {
        #             "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        #             "Content-Type": "application/json"
        #         }
        #         async with httpx.AsyncClient(timeout=30.0) as client:
        #             for i in range(0, len(texts), batch_size):
        #                 batch = texts[i:i + batch_size]
        #                 response = await client.post(
        #                     "https://api.openai.com/v1/embeddings",
        #                     headers=headers,
        #                     json={
        #                         "input": batch,
        #                         "model": "text-embedding-3-small",
        #                         "dimensions": 1024
        #                     }
        #                 )
        #                 if response.status_code == 200:
        #                     res_json = response.json()
        #                     embeddings = [item["embedding"] for item in res_json.get("data", [])]
        #                     all_embeddings.extend(embeddings)
        #                 else:
        #                     raise RuntimeError(f"OpenAI API request failed: {response.text}")
        #         return all_embeddings
        #     except Exception as e:
        #         logger.error(f"OpenAI embedding generation failed: {e}. Falling back...")

        # 1.5. Try Jina embedding (1024 dim) if configured
        if settings.JINA_API_KEY:
            logger.info(
                "[Step 4 - Embedding] Generating dense embeddings using Jina (1024d)..."
            )
            try:
                batch_size = 32
                all_embeddings = []
                headers = {
                    "Authorization": f"Bearer {settings.JINA_API_KEY}",
                    "Content-Type": "application/json",
                }
                async with httpx.AsyncClient(timeout=60.0) as client:
                    for i in range(0, len(texts), batch_size):
                        batch = texts[i : i + batch_size]
                        response = await client.post(
                            "https://api.jina.ai/v1/embeddings",
                            headers=headers,
                            json={
                                "input": batch,
                                "model": "jina-embeddings-v3",
                                "dimensions": 1024,
                            },
                        )
                        if response.status_code == 200:
                            res_json = response.json()
                            embeddings = [
                                item["embedding"] for item in res_json.get("data", [])
                            ]
                            all_embeddings.extend(embeddings)
                        else:
                            raise RuntimeError(
                                f"Jina API request failed: {response.text}"
                            )
                return all_embeddings
            except Exception as e:
                logger.error(f"Jina embedding generation failed: {e}. Falling back...")

        # 2. If TEI / vLLM server is configured
        if self.api_url:
            logger.info(
                f"[Step 4 - Embedding] Fetching embeddings from remote TEI/vLLM: {self.api_url}"
            )
            try:
                # Batch requests of size 32
                batch_size = 32
                all_embeddings = []

                async with httpx.AsyncClient(timeout=30.0) as client:
                    for i in range(0, len(texts), batch_size):
                        batch = texts[i : i + batch_size]

                        # TEI expects {"inputs": [...]} or {"inputs": "..."}
                        # vLLM/OpenAI expects {"input": [...], "model": "..."}
                        # We will try TEI format first, then fall back to OpenAI style if needed
                        response = await client.post(
                            self.api_url, json={"inputs": batch}
                        )

                        if response.status_code == 200:
                            embeddings = response.json()
                            # TEI returns a list of float arrays directly or list of dicts
                            if isinstance(embeddings, list):
                                if len(embeddings) > 0 and isinstance(
                                    embeddings[0], dict
                                ):
                                    # Handle standard huggingface text-generation-inference style wrapper
                                    embeddings = [
                                        emb.get("embedding", emb) for emb in embeddings
                                    ]
                                all_embeddings.extend(embeddings)
                            else:
                                raise ValueError(
                                    f"Unexpected response format from TEI: {embeddings}"
                                )
                        else:
                            # Try OpenAI style wrapper (vLLM / Ollama compatible)
                            logger.warning(
                                f"TEI style request failed with status {response.status_code}. Retrying OpenAI-embeddings format..."
                            )
                            response_oa = await client.post(
                                self.api_url,
                                json={"input": batch, "model": "qwen3-embed-0.6"},
                            )
                            if response_oa.status_code == 200:
                                res_json = response_oa.json()
                                # Expecting OpenAI format: {"data": [{"embedding": [...]}, ...]}
                                embeddings = [
                                    item["embedding"]
                                    for item in res_json.get("data", [])
                                ]
                                all_embeddings.extend(embeddings)
                            else:
                                raise RuntimeError(
                                    f"Embedding API request failed: {response_oa.text}"
                                )

                return all_embeddings
            except Exception as e:
                logger.error(
                    f"Remote embedding extraction failed: {e}. Falling back to local model."
                )

        # Local SentenceTransformer Fallback
        logger.info(
            "[Step 4 - Embedding] Generating dense embeddings locally using SentenceTransformer..."
        )
        model = self._get_local_model()

        # Run local encode in a threadpool to prevent blocking the event loop
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(
            None, lambda: model.encode(texts, convert_to_numpy=True)
        )
        return [emb.tolist() for emb in embeddings]

    def get_sparse_embeddings(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Generates sparse term-frequency vectors (indices and values) for hybrid search support.
        Uses hash-based vocabulary indexing (Hashing Trick) to remain lightweight and dependency-free.
        """
        logger.info(
            f"[Step 4 - Embedding] Generating sparse TF vectors locally for {len(texts)} chunks..."
        )
        sparse_vectors = []
        VOCAB_SIZE = 2**20  # Map tokens to a 1M dimensional sparse space

        for text in texts:
            # Simple tokenization: lowercase, alpha-numeric tokens
            tokens = [t.lower() for t in re.findall(r"\w+", text) if len(t) > 1]
            if not tokens:
                sparse_vectors.append({"indices": [], "values": []})
                continue

            # Compute term frequencies
            counts = {}
            for t in tokens:
                counts[t] = counts.get(t, 0) + 1

            # TF normalization
            total_tokens = len(tokens)
            term_frequencies = {t: count / total_tokens for t, count in counts.items()}

            indices = []
            values = []
            for token, tf in term_frequencies.items():
                # Hash token to a stable vocabulary index
                h = hashlib.sha256(token.encode("utf-8")).hexdigest()
                idx = int(h, 16) % VOCAB_SIZE
                indices.append(idx)
                values.append(float(tf))

            # Pinecone expects sorted indices
            sorted_pairs = sorted(zip(indices, values))
            sorted_indices = [p[0] for p in sorted_pairs]
            sorted_values = [p[1] for p in sorted_pairs]

            sparse_vectors.append({"indices": sorted_indices, "values": sorted_values})

        return sparse_vectors


embedding_service = EmbeddingService()
