import asyncio
import logging
from typing import Dict, Any, List
import logfire

from src.app.services.query_optimizer import QueryOptimizer
from src.app.services.retrieval_service import RetrievalService, retrieval_service
from src.app.graphs.state import SupervisorState

logger = logging.getLogger("RAGSubAgent")
query_optimizer = QueryOptimizer()


async def run_rag_agent(state: SupervisorState) -> Dict[str, Any]:
    """
    RAG Sub-Agent for Vrsa Agrotech.
    
    6-STEP RAG PIPELINE:
    ====================
    Step 1: Extract latest user query & prepare conversation history.
    Step 2: Multi-Query Expansion via QueryOptimizer (3 query variations & Punjabi/Hinglish term resolution).
    Step 3: Generate BM25 Sparse Vectors (bm25_service) + Dense Vectors (embedding_service).
    Step 4: Parallel Hybrid Search on Pinecone (pinecone_service).
    Step 5: Candidate Reranking via Jina Reranker v2 / RRF fusion (filters candidate pool to top 5 or fewer chunks).
    Step 6: Return clean internal facts payload back to Supervisor State.

    RETURN RESPONSE EXAMPLE BACK TO SUPERVISOR STATE:
    =================================================
    {
        "internal_facts": [
            {
                "subagent": "rag_agent",
                "original_query": "my buffalo gives low milk fat, which supplement to use?",
                "reranked_chunks": [
                    "MaxaPro-DS Dairy is a double-strength supplement formulated to increase daily milk production...",
                    "Buffalo-F 1.5X increases fat content by up to 1.5% in high-yielding buffaloes...",
                    "Dosage: Mix 50g daily in cattle feed for optimal results..."
                ]
            }
        ],
        "next": "supervisor_sales_agent"
    }
    """
    messages = state.get("messages", [])
    user_id = state.get("user_id", "guest_user")
    
    # -------------------------------------------------------------------------
    # STEP 1: Extract latest user query & prepare conversation history
    # -------------------------------------------------------------------------
    chat_history = []
    last_user_query = ""
    for msg in messages:
        if hasattr(msg, "type"):
            role = "user" if msg.type == "human" else "assistant"
            content = msg.content
        elif isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
        else:
            role = "user"
            content = str(msg)
            
        chat_history.append({"role": role, "content": content})
        if role == "user":
            last_user_query = content

    if not last_user_query:
        last_user_query = "Vrsa Agrotech animal nutrition supplements and dairy products"

    print("\n" + "=" * 80)
    print(f"[RAG SUB-AGENT] STEP 1: USER QUERY EXTRACTED -> '{last_user_query}'")

    # -------------------------------------------------------------------------
    # STEP 2: Multi-Query Expansion via QueryOptimizer (3 variations)
    # -------------------------------------------------------------------------
    try:
        expanded_queries = await asyncio.to_thread(
            query_optimizer.optimize_query,
            chat_history=chat_history,
            current_query=last_user_query,
            user_id=user_id
        )
        if not expanded_queries:
            expanded_queries = [last_user_query]
    except Exception as e:
        logger.error(f"[RAG Sub-Agent] Step 2 error: {e}. Using original query.")
        expanded_queries = [last_user_query]

    print("\n[RAG SUB-AGENT] STEP 2: 3 QUERY EXPANSIONS (QueryOptimizer):")
    for idx, q in enumerate(expanded_queries[:3], 1):
        print(f"   {idx}. {q}")
    
    logfire.info("Multi-query expansions generated", original=last_user_query, expansions=expanded_queries[:3])

    # -------------------------------------------------------------------------
    # STEP 3 & 4: BM25 Sparse + Dense Hybrid Search on Pinecone
    # (Step 3: bm25_service generates sparse vectors + embedding_service generates dense vectors)
    # (Step 4: pinecone_service executes parallel hybrid search)
    # STEP 5: Candidate Reranking via Jina Reranker v2 / RRF fusion (top 5 or fewer)
    # -------------------------------------------------------------------------
    reranked_chunks = []
    try:
        retrieved_matches = await retrieval_service.retrieve_parallel(
            queries=expanded_queries,
            top_k=5,
            user_id=user_id,
            original_query=last_user_query,
            namespace="default"
        )
        
        print(f"\n[RAG SUB-AGENT] STEP 5: TOP RERANKED CHUNKS RETURNED ({len(retrieved_matches)}):")
        for idx, match in enumerate(retrieved_matches, 1):
            text = match.get("metadata", {}).get("text", "") or match.get("metadata", {}).get("content", "")
            score = match.get("score", 0.0)
            if text:
                reranked_chunks.append(text)
                snippet = text[:140].replace("\n", " ") + "..." if len(text) > 140 else text
                print(f"   Chunk #{idx} [Rerank Score: {score:.4f}]: {snippet}")

    except Exception as e:
        logger.error(f"[RAG Sub-Agent] Step 3-5 error: {e}")

    # Capture dense vector embedding of last_user_query for zero-cost semantic cache reuse
    rag_dense_vec = None
    try:
        from src.app.services.embedding_service import embedding_service
        vecs = await embedding_service.get_dense_embeddings([last_user_query])
        if vecs and vecs[0]:
            rag_dense_vec = vecs[0]
    except Exception as ee:
        logger.error(f"Error capturing RAG dense vector for cache: {ee}")

    # -------------------------------------------------------------------------
    # STEP 6: Store clean payload in Supervisor State & route to supervisor_sales_agent
    # -------------------------------------------------------------------------
    existing_facts = list(state.get("internal_facts") or [])
    payload = {
        "subagent": "rag_agent",
        "original_query": last_user_query,
        "reranked_chunks": reranked_chunks,  # Top 5 (or fewer) reranked chunks
        "rag_dense_vec": rag_dense_vec
    }
    existing_facts.append(payload)

    print(f"\n[RAG SUB-AGENT] STEP 6: Sent {len(reranked_chunks)} reranked chunks to Supervisor State -> Next: 'supervisor_sales_agent'")
    print("=" * 80 + "\n")

    return {
        "internal_facts": existing_facts,
        "next": "supervisor_sales_agent"
    }
