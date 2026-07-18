import asyncio
import logging
from typing import Any, Dict, List
import logfire
from src.app.services.embedding_service import embedding_service
from src.app.services.pinecone_service import pinecone_service
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
        namespace: str
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
                namespace=namespace
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
        namespace: str = None,
        user_id: str = "guest_user"
    ) -> List[Dict[str, Any]]:
        """
        Takes multiple search queries, generates dense + sparse embeddings in batch,
        queries Pinecone in parallel, de-duplicates chunks, and returns sorted results.
        """
        if not queries:
            return []

        logger.info(f"Initiating parallel hybrid search for {len(queries)} queries...")
        logfire.info("Parallel hybrid search starting", queries=queries, namespace=namespace)

        # 1. Batched generation of embeddings (dense and sparse)
        try:
            dense_vectors = await embedding_service.get_dense_embeddings(queries)
            sparse_vectors = embedding_service.get_sparse_embeddings(queries)
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

        # 3. Query Pinecone in parallel
        tasks = []
        for i, query in enumerate(queries):
            dense_vec = dense_vectors[i] if i < len(dense_vectors) else None
            sparse_vec = sparse_vectors[i] if i < len(sparse_vectors) else None
            
            tasks.append(
                self._query_single(
                    query=query,
                    dense_vec=dense_vec,
                    sparse_vec=sparse_vec,
                    top_k=top_k,
                    namespace=namespace
                )
            )

        # Run all queries concurrently
        results_lists = await asyncio.gather(*tasks)

        # 4. De-duplicate and combine results
        unique_matches = {}
        for matches in results_lists:
            for match in matches:
                match_id = match.get("id")
                # We keep the match with the highest score if duplicates appear
                if match_id not in unique_matches or match.get("score", 0) > unique_matches[match_id].get("score", 0):
                    unique_matches[match_id] = match

        # Sort combined unique matches by score descending
        sorted_results = sorted(
            unique_matches.values(),
            key=lambda x: x.get("score", 0),
            reverse=True
        )

        # Limit to top K
        final_results = sorted_results[:top_k]

        logger.info(f"Retrieved and de-duplicated {len(final_results)} chunks from Pinecone.")
        logfire.info("Parallel retrieval complete", final_count=len(final_results))

        if span:
            try:
                span.update(output=final_results)
                span.end()
            except Exception as le:
                logger.error(f"Failed to end Langfuse span in retrieval: {le}")

        return final_results

retrieval_service = RetrievalService()
