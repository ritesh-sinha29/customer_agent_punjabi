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

# Define the user's 3 queries
queries = [
    {
        "id": 1,
        "title": "Question 1 (Hinglish/Punjabi Dairy Cattle vs Buffalo Products)",
        "query": "Mere kol dairy cattle te buffalo dono ne. Dass veere, kehda product kis animal layi best aa te kinna difference aa ohna vich?"
    },
    {
        "id": 2,
        "title": "Question 2 (English Product Range & Animal Species)",
        "query": "How many products does VRSA AGROTECH currently offer, and which animal species do these products serve?"
    },
    {
        "id": 3,
        "title": "Question 3 (Punjabi Milk Buffalo Production & Dosage)",
        "query": "ਜੇ ਮੇਰੇ ਕੋਲ ਦੁੱਧ ਵਾਲੀਆਂ ਭੈਂਸਾਂ ਹਨ ਅਤੇ ਉਨ੍ਹਾਂ ਦੀ ਦੁੱਧ ਉਤਪਾਦਨ ਸਮਰੱਥਾ ਵਧਾਉਣੀ ਹੋਵੇ, ਤਾਂ VRSA AGROTECH ਦਾ ਕਿਹੜਾ ਉਤਪਾਦ ਸਭ ਤੋਂ ਢੁੱਕਵਾਂ ਹੈ? ਇਸ ਦੀ ਖੁਰਾਕ (dosage) ਅਤੇ ਮੁੱਖ ਫਾਇਦੇ ਵੀ ਦੱਸੋ।"
    }
]

async def run_test_case(case):
    print("\n" + "=" * 80)
    print(f"RUNNING TEST CASE {case['id']}: {case['title']}")
    print(f"Original Query: '{case['query']}'")
    print("=" * 80)

    start_total = time.perf_counter()

    # 1. Query rewrite / expansion
    start_opt = time.perf_counter()
    try:
        optimized_queries = query_optimizer.optimize_query([], case['query'], user_id="test_user")
    except Exception as e:
        print(f"[-] Query optimization failed: {e}")
        optimized_queries = [case['query']]
    opt_duration = (time.perf_counter() - start_opt) * 1000

    # 2. Parallel hybrid search in Pinecone
    start_ret = time.perf_counter()
    try:
        results = await retrieval_service.retrieve_parallel(
            queries=optimized_queries,
            top_k=3,
            namespace="default",
            user_id="test_user"
        )
    except Exception as e:
        print(f"[-] Parallel retrieval failed: {e}")
        results = []
    ret_duration = (time.perf_counter() - start_ret) * 1000

    elapsed = (time.perf_counter() - start_total) * 1000

    print("\n[+] 1. Rewritten Multi-Queries:")
    for idx, q in enumerate(optimized_queries, 1):
        print(f"  {idx}. {q}")

    print("\n[+] 2. Retrieved Chunks (Top 3):")
    if not results:
        print("  [No chunks found]")
    for idx, match in enumerate(results, 1):
        metadata = match.get("metadata", {})
        score = match.get("score", 0.0)
        chunk_id = metadata.get("chunk_id", "N/A")
        text = metadata.get("text", "")
        print(f"\n  Chunk {idx} (Score: {score:.4f}, ID: {chunk_id}):")
        # Print first 300 characters of the chunk text
        print("-" * 50)
        print(text.strip())
        print("-" * 50)

    print("\n[+] 3. Timing Performance:")
    print(f"  └─ Query Expansion Time:  {opt_duration:.2f} ms")
    print(f"  └─ Parallel Search Time:  {ret_duration:.2f} ms")
    print(f"  └─ Total Execution Time:  {elapsed:.2f} ms")

async def main():
    # Warm up first
    print("Warming up API connections...")
    try:
        query_optimizer.optimize_query([], "warmup", user_id="warmup")
    except Exception:
        pass
    
    # Run the 3 test cases
    for case in queries:
        await run_test_case(case)
        print("\n" + "#" * 80)

if __name__ == "__main__":
    asyncio.run(main())
