import asyncio
import os
import sys
import time
from pathlib import Path

# Add project root to python path to resolve imports correctly
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# Fix Windows console print for Unicode
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from src.app.services.query_optimizer import query_optimizer
from src.app.services.retrieval_service import retrieval_service
from src.app.services.pinecone_service import pinecone_service

async def run_test_case(title: str, query: str):
    print(f"\n--- {title} ---")
    print(f"User Query: '{query}'")
    
    start_total = time.perf_counter()
    
    # 1. Query rewrite / expansion
    start_opt = time.perf_counter()
    optimized_queries = query_optimizer.optimize_query([], query, user_id="user_specific_test")
    opt_duration_ms = (time.perf_counter() - start_opt) * 1000
    
    # 2. Parallel hybrid search in Pinecone (searching actual company docs in 'default' namespace)
    start_ret = time.perf_counter()
    results = await retrieval_service.retrieve_parallel(
        queries=optimized_queries,
        top_k=3,
        namespace="default",
        user_id="user_specific_test"
    )
    ret_duration_ms = (time.perf_counter() - start_ret) * 1000
    
    elapsed_ms = (time.perf_counter() - start_total) * 1000
    
    print(f"Total Execution Time: {elapsed_ms:.2f} ms")
    print(f"  └─ Query Optimizer: {opt_duration_ms:.2f} ms")
    print(f"  └─ Parallel Search: {ret_duration_ms:.2f} ms")
    print("Generated Query Variations:")
    for idx, q in enumerate(optimized_queries, 1):
        print(f"  {idx}. {q}")
        
    print(f"Retrieved Chunks (Top 3):")
    if not results:
        print("  [No chunks found]")
    for idx, match in enumerate(results, 1):
        metadata = match.get("metadata", {})
        chunk_id = metadata.get("chunk_id", "N/A")
        doc_id = metadata.get("doc_id", "N/A")
        headings_path = metadata.get("headings_path_str", "N/A")
        text = metadata.get("text", "")
        # Remove multiple newlines for prettier display
        text_snippet = " ".join(text.split())[:200]
        print(f"  {idx}. [Score: {match.get('score', 0):.4f}] [Doc: {doc_id}] [Heading: {headings_path}]")
        print(f"     Content: {text_snippet}...")
        
    return elapsed_ms

async def main():
    # 1. Connect
    conn_ok = pinecone_service.check_connection()
    if not conn_ok:
        print("[-] Cannot connect to Pinecone. Ingestion and search tests aborted.")
        return

    # 3. Run Test Queries
    queries = [
        "What is the main purpose of Buffalo-Power 2X",
        "Oye ji, Horsa-550X-Turbo kida help karda race horses nu?",
        "ਮੈਕਸਾਪ੍ਰੋ ਲਿਕਵਿਡ ਕਿਉਂ ਵਰਤਿਆ ਜਾਂਦਾ ਹੈ ਮੁਰਗੀਆਂ ਲਈ?"
    ]
    
    for idx, q in enumerate(queries, 1):
        await run_test_case(f"QUERY {idx}", q)

if __name__ == "__main__":
    asyncio.run(main())
