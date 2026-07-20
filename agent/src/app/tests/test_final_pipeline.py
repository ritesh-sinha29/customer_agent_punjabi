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
from src.app.services.embedding_service import embedding_service
from src.app.services.bm25_service import bm25_service


def get_demo_chunks() -> list[str]:
    """
    Reads demo.md and splits it into logical chunks.
    """
    demo_path = Path(__file__).resolve().parent / "demo.md"
    if not demo_path.exists():
        raise FileNotFoundError(f"demo.md not found at {demo_path}")
        
    content = demo_path.read_text(encoding="utf-8")
    sections = content.split("## ")
    
    chunks = []
    # Add intro
    intro = sections[0].strip()
    if intro:
        chunks.append(intro)
        
    for sec in sections[1:]:
        chunks.append("## " + sec.strip())
        
    return chunks


async def ingest_demo_doc():
    """
    Splits demo.md, generates embeddings, and loads it into the Pinecone index.
    """
    print("\n>>> INGESTING DEMO DOCUMENT TO PINECONE...")
    chunks = get_demo_chunks()
    print(f"Generated {len(chunks)} text chunks from demo.md.")

    # 1. Generate dense and sparse vectors in batch
    bm25_service.fit_new_documents(chunks)
    dense_vectors = await embedding_service.get_dense_embeddings(chunks)
    sparse_vectors = bm25_service.get_document_sparse_vectors(chunks)

    # 2. Package payloads
    pinecone_vectors = []
    doc_id = "demo_doc"
    for idx, text in enumerate(chunks):
        chunk_id = f"demo-chunk-{idx}"
        metadata = {
            "doc_id": doc_id,
            "chunk_id": chunk_id,
            "text": text,
            "version": "1.0.0",
            "permissions": ["read:all"]
        }
        vector_payload = {
            "id": chunk_id,
            "values": dense_vectors[idx],
            "metadata": metadata
        }
        if sparse_vectors and idx < len(sparse_vectors):
            vector_payload["sparse_values"] = sparse_vectors[idx]

        pinecone_vectors.append(vector_payload)

    # 3. Ensure index exists and upsert
    pinecone_service.ensure_index(dimension=len(dense_vectors[0]))
    
    # Clean old ones first
    pinecone_service.delete_by_doc_id(doc_id=doc_id, namespace="default")
    
    # Upsert
    upserted = pinecone_service.upsert_vectors(pinecone_vectors, namespace="default")
    print(f"[+] Successfully loaded {upserted} chunks into Pinecone namespace 'default'.\n")


async def run_test_case(title: str, query: str):
    """
    Runs a single query case: expands the query, runs parallel search, and measures time.
    """
    print(f"\n--- {title} ---")
    print(f"User Query: '{query}'")
    
    start_total = time.perf_counter()
    
    # 1. Query rewrite / expansion
    start_opt = time.perf_counter()
    optimized_queries = query_optimizer.optimize_query([], query, user_id="final_test_user")
    opt_duration_ms = (time.perf_counter() - start_opt) * 1000
    
    # 2. Parallel hybrid search in Pinecone
    start_ret = time.perf_counter()
    results = await retrieval_service.retrieve_parallel(
        queries=optimized_queries,
        top_k=2,
        namespace="default",
        user_id="final_test_user"
    )
    ret_duration_ms = (time.perf_counter() - start_ret) * 1000
    
    elapsed_ms = (time.perf_counter() - start_total) * 1000
    
    print(f"Total Execution Time: {elapsed_ms:.2f} ms")
    print(f"  └─ Query Optimizer: {opt_duration_ms:.2f} ms")
    print(f"  └─ Parallel Search: {ret_duration_ms:.2f} ms")
    print("Generated Query Variations:")
    for idx, q in enumerate(optimized_queries, 1):
        print(f"  {idx}. {q}")
        
    print(f"Retrieved Chunks (Top 2):")
    if not results:
        print("  [No chunks found]")
    for idx, match in enumerate(results, 1):
        metadata = match.get("metadata", {})
        print(f"  {idx}. [Score: {match.get('score', 0):.4f}] {metadata.get('text', '')[:150]}...")
        
    # Return time to check limits
    return elapsed_ms


async def main():
    # 1. Connect
    conn_ok = pinecone_service.check_connection()
    if not conn_ok:
        print("[-] Cannot connect to Pinecone. Ingestion and search tests aborted.")
        return

    # 2. Ingest demo.md
    await ingest_demo_doc()

    # 2.5. Warm up API connections and TLS keep-alives
    print(">>> WARMING UP API CONNECTIONS AND TLS KEEP-ALIVES...")
    try:
        # Dry-run optimizer (caches heuristics / optimizer loading)
        query_optimizer.optimize_query([], "warmup", user_id="warmup")
        # Dry-run embedding generation (initiates Jina TLS handshake)
        dummy_dense = await embedding_service.get_dense_embeddings(["warmup"])
        # Dry-run Pinecone query (initiates Pinecone TCP/TLS keep-alive)
        pinecone_service.query_hybrid(dense_vector=dummy_dense[0], top_k=1, namespace="default")
        print("[+] System warmed up. Pre-established network keep-alives.\n")
    except Exception as we:
        print(f"[-] Warmup warning: {we}\n")

    # 3. Run Test Queries
    times = []
    
    # Query A: Pure Punjabi
    t_a = await run_test_case(
        title="TEST CASE A: Pure Punjabi",
        query="ਪਾਈਪਲਾਈਨ ਵਿੱਚ ਚੰਕਿੰਗ ਕਿਵੇਂ ਹੁੰਦੀ ਹੈ?" # "How does chunking happen in the pipeline?"
    )
    times.append(t_a)

    # Query B: Punjabi Hinglish
    t_b = await run_test_case(
        title="TEST CASE B: Punjabi Hinglish/Transliteration",
        query="Agar LlamaParse offline ho jaye to kya fallback options hain?"
    )
    times.append(t_b)

    # Query C: English
    t_c = await run_test_case(
        title="TEST CASE C: Standard English",
        query="What is the size limit for document uploads?"
    )
    times.append(t_c)

    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    print(f"Pure Punjabi Query:       {t_a:.2f} ms")
    print(f"Punjabi Hinglish Query:   {t_b:.2f} ms")
    print(f"Standard English Query:   {t_c:.2f} ms")
    print(f"Average Response Time:     {sum(times)/len(times):.2f} ms")
    
    # Final check: are execution times less than 1 second?
    if all(t < 1000 for t in times):
        print("\n🎉 SUCCESS: All query pipelines completed in under 1 second (1000 ms)!")
    else:
        print("\n⚠️ WARNING: Some query pipelines took longer than 1 second. (Likely first run network spikes).")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
