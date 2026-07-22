import asyncio
import logging
from typing import Any, Dict, List
import logfire
from src.app.services.embedding_service import embedding_service
from src.app.services.pinecone_service import pinecone_service
from src.app.services.bm25_service import bm25_service
from src.app.services.query_optimizer import langfuse

logger = logging.getLogger("RetrievalService")

class RetrievalService:
    """
    Retrieval service that coordinates hybrid search (dense + sparse)
    over multiple queries in parallel against the Pinecone vector database.
    """

    def __init__(self):
        pass

    async def _query_single(
        self, 
        query: str, 
        dense_vec: List[float], 
        sparse_vec: Dict[str, Any], 
        top_k: int, 
        namespace: str,
        filter: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes a single hybrid query against Pinecone in a worker thread.
        """
        try:
            # Execute in a thread pool to avoid blocking the event loop
            results = await asyncio.to_thread(
                pinecone_service.query_hybrid,
                dense_vector=dense_vec,
                sparse_vector=sparse_vec,
                top_k=top_k,
                namespace=namespace,
                filter=filter
            )
            return results
        except Exception as e:
            logger.error(f"Failed single Pinecone query for '{query}': {e}")
            return []

    @logfire.instrument("hybrid_retrieval_parallel")
    async def retrieve_parallel(
        self, 
        queries: List[str], 
        top_k: int = 5, 
        namespace: str = "default",
        user_id: str = "guest_user",
        original_query: str = None
    ) -> List[Dict[str, Any]]:
        """
        Takes multiple search queries, generates dense + sparse embeddings in batch,
        queries Pinecone in parallel, de-duplicates and rerank chunks (using Jina v2
        Reranker or local RRF), and returns the top_k sorted results.
        """
        if not queries:
            return []

        logger.info(f"Initiating parallel hybrid search for {len(queries)} queries...")
        logfire.info("Parallel hybrid search starting", queries=queries, namespace=namespace)

        # 1. Batched generation of embeddings (dense and sparse)
        try:
            dense_vectors = await embedding_service.get_dense_embeddings(queries)
            sparse_vectors = bm25_service.get_query_sparse_vectors(queries)
        except Exception as e:
            logger.error(f"Failed embedding generation during retrieval: {e}")
            logfire.exception("Embedding generation error in retrieval", error=str(e))
            return []

        # 2. Setup Langfuse span/observation
        span = None
        if langfuse:
            try:
                span = langfuse.start_observation(
                    as_type="span",
                    name="hybrid-search-parallel",
                    input={"queries": queries, "top_k": top_k, "namespace": namespace},
                    metadata={"user_id": user_id}
                )
            except Exception as le:
                logger.error(f"Langfuse span creation failed in retrieval: {le}")

        # 3. Query Pinecone in parallel with an expanded candidate pool size
        candidate_top_k = max(top_k * 3, 15)
        filter_dict = None
        if namespace == "user_memory" and user_id:
            filter_dict = {"user_id": {"$eq": user_id}}

        tasks = []
        for i, query in enumerate(queries):
            dense_vec = dense_vectors[i] if i < len(dense_vectors) else None
            sparse_vec = sparse_vectors[i] if i < len(sparse_vectors) else None
            
            tasks.append(
                self._query_single(
                    query=query,
                    dense_vec=dense_vec,
                    sparse_vec=sparse_vec,
                    top_k=candidate_top_k,
                    namespace=namespace,
                    filter=filter_dict
                )
            )

        # Run all queries concurrently
        results_lists = await asyncio.gather(*tasks)

        # 4. Rerank and filter using RerankingService
        from src.app.services.reranking_service import reranking_service
        primary_query = original_query if original_query else queries[0]
        
        final_results = await reranking_service.rerank(
            query=primary_query,
            results_lists=results_lists,
            top_n=top_k
        )

        # Print retrieved chunks to console for user verification
        print("\n" + "=" * 80)
        print(f"BM25 HYBRID RETRIEVAL RESULTS (Original Query: '{primary_query}')")
        print("=" * 80)
        for idx, match in enumerate(final_results, 1):
            score = match.get("score", 0.0)
            text = match.get("metadata", {}).get("text", "")
            snippet = text[:150].replace("\n", " ") + "..." if len(text) > 150 else text
            print(f"[{idx}] [Score: {score:.4f}] {snippet}")
        print("=" * 80 + "\n")

        logger.info(f"Retrieved and reranked {len(final_results)} chunks from Pinecone.")
        logfire.info("Parallel retrieval complete", final_count=len(final_results))

        if span:
            try:
                span.update(output=final_results)
                span.end()
            except Exception as le:
                logger.error(f"Failed to end Langfuse span in retrieval: {le}")

        return final_results

retrieval_service = RetrievalService()
