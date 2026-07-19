import asyncio
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


async def run_rerank_test(query_text: str):
    print("\n" + "=" * 80)
    print(f"RUNNING RERANKING TEST FOR: '{query_text}'")
    print("=" * 80)

    start_total = time.perf_counter()

    # 1. Expand query to multiple variations
    print("[+] Step 1: Generating query variations via QueryOptimizer...")
    try:
        optimized_queries = query_optimizer.optimize_query([], query_text, user_id="rerank_test")
    except Exception as e:
        print(f"  [-] Query optimization failed: {e}")
        optimized_queries = [query_text]

    print("  Generated Query Variations:")
    for idx, q in enumerate(optimized_queries, 1):
        print(f"    {idx}. {q}")

    # 2. Retrieve and Rerank top 5 chunks
    print("\n[+] Step 2: Retrieving candidates and applying Reranking (top_k=5)...")
    try:
        results = await retrieval_service.retrieve_parallel(
            queries=optimized_queries,
            top_k=5,
            namespace="default",
            user_id="rerank_test",
            original_query=query_text
        )
    except Exception as e:
        print(f"  [-] Parallel retrieval + reranking failed: {e}")
        results = []

    duration_ms = (time.perf_counter() - start_total) * 1000

    print(f"\n[+] Step 3: Top Reranked Chunks (Count: {len(results)}):")
    if not results:
        print("  [No chunks returned]")
    for idx, match in enumerate(results, 1):
        metadata = match.get("metadata", {})
        score = match.get("score", 0.0)
        chunk_id = metadata.get("chunk_id", "N/A")
        headings = metadata.get("headings_path_str", "N/A")
        text = metadata.get("text", "")
        # Get score types
        rerank_score = match.get("rerank_score")
        rrf_score = match.get("rrf_score")
        
        score_type = "Jina Relevance Score" if rerank_score is not None else "Local RRF Score"
        score_val = rerank_score if rerank_score is not None else rrf_score

        print(f"\n  Chunk {idx} [ID: {chunk_id}] [Headings: {headings}]:")
        print(f"  Score: {score_val:.4f} ({score_type})")
        print("-" * 50)
        # Snippet of content
        print(" ".join(text.split())[:250] + "...")
        print("-" * 50)

    print(f"\nExecution latency: {duration_ms:.2f} ms")


async def main():
    # Verify connection to Pinecone
    if not pinecone_service.check_connection():
        print("[-] Cannot connect to Pinecone. Aborting test.")
        return

    # Test cases
    test_queries = [
        "What is the main purpose of Buffalo-Power 2X",
        "ਮੈਕਸਾਪ੍ਰੋ ਲਿਕਵਿਡ ਕਿਉਂ ਵਰਤਿਆ ਜਾਂਦਾ ਹੈ ਮੁਰਗੀਆਂ ਲਈ?"
    ]

    for q in test_queries:
        await run_rerank_test(q)
        print("\n" + "#" * 80)


if __name__ == "__main__":
    asyncio.run(main())
