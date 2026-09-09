import logging
from typing import Any, Dict, List
import httpx
from src.app.core.config import settings

logger = logging.getLogger("RerankingService")


class RerankingService:
    """
    Reranking service that integrates Jina Rerank v2 API with a local
    Reciprocal Rank Fusion (RRF) fallback algorithm.
    """

    def __init__(self):
        self.jina_api_key = settings.JINA_API_KEY
        self.api_url = "https://api.jina.ai/v1/rerank"

    async def rerank_jina(
        self, query: str, documents: List[Dict[str, Any]], top_n: int = 5
    ) -> List[Dict[str, Any]] | None:
        """
        Sends query and documents to the Jina Reranker v2 API.
        """
        if not self.jina_api_key:
            logger.warning("JINA_API_KEY is not configured. Skipping Jina Rerank.")
            return None

        if not documents:
            return []

        # Extract text snippets from documents
        doc_texts = []
        for doc in documents:
            text = doc.get("metadata", {}).get("text", "")
            doc_texts.append(text)

        headers = {
            "Authorization": f"Bearer {self.jina_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "jina-reranker-v2-base-multilingual",
            "query": query,
            "documents": doc_texts,
            "top_n": top_n,
        }

        try:
            logger.info(f"Sending {len(documents)} candidates to Jina Reranker...")
            async with httpx.AsyncClient(timeout=6.0) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)
                if response.status_code == 200:
                    results = response.json().get("results", [])
                    reranked_docs = []
                    for item in results:
                        idx = item["index"]
                        score = item["relevance_score"]
                        doc = documents[idx].copy()
                        doc["rerank_score"] = score
                        # Also override Pinecone score with Jina relevance score
                        doc["score"] = score
                        reranked_docs.append(doc)
                    logger.info("Jina Reranking succeeded.")
                    return reranked_docs
                else:
                    logger.error(
                        f"Jina Reranker API error status {response.status_code}: {response.text}"
                    )
                    return None
        except Exception as e:
            logger.error(f"Failed to call Jina Reranker API: {e}")
            return None

    def rerank_rrf(
        self, results_lists: List[List[Dict[str, Any]]], top_n: int = 5, k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Computes Reciprocal Rank Fusion (RRF) across multiple ranked lists.
        Used as local fallback when Jina API key is missing or fails.
        """
        logger.info(
            f"Fusing {len(results_lists)} parallel query result lists using local RRF (k={k})..."
        )
        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, Dict[str, Any]] = {}

        for rank_list in results_lists:
            for rank_idx, doc in enumerate(rank_list):
                doc_id = doc.get("id")
                if not doc_id:
                    continue

                # Store document structure
                if doc_id not in doc_map:
                    doc_map[doc_id] = doc.copy()

                # Add to reciprocal rank score (1-based rank index)
                rank = rank_idx + 1
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (k + rank))

        # Sort documents by RRF score descending
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        reranked_docs = []
        for doc_id in sorted_ids[:top_n]:
            doc = doc_map[doc_id].copy()
            doc["rrf_score"] = rrf_scores[doc_id]
            # Maintain a score field for standard compatibility
            doc["score"] = rrf_scores[doc_id]
            reranked_docs.append(doc)

        logger.info(f"Local RRF completed. Fused to top {len(reranked_docs)} results.")
        return reranked_docs

    async def rerank(
        self,
        query: str,
        results_lists: List[List[Dict[str, Any]]],
        top_n: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Orchestrator: Attempt Jina Rerank v2 first. If Jina is unavailable
        or fails, fallback to local Reciprocal Rank Fusion (RRF).
        """
        # 1. De-duplicate unique candidates for Jina Reranker input
        unique_matches = {}
        for rank_list in results_lists:
            for doc in rank_list:
                doc_id = doc.get("id")
                if doc_id not in unique_matches or doc.get("score", 0.0) > unique_matches[doc_id].get("score", 0.0):
                    unique_matches[doc_id] = doc

        candidates = list(unique_matches.values())

        if not candidates:
            return []

        # 2. (Commented out - Jina reranking removed in favor of pure RRF fusion)
        # if self.jina_api_key:
        #     reranked = await self.rerank_jina(query, candidates, top_n=top_n)
        #     if reranked is not None:
        #         return reranked

        # 3. Perform Reciprocal Rank Fusion (RRF)
        return self.rerank_rrf(results_lists, top_n=top_n)


reranking_service = RerankingService()
