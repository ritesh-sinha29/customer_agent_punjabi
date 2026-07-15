import os
import uuid
import logging
from typing import Any, Dict, List
from src.app.services.document_loader import document_loader
from src.app.services.chunking_service import chunking_service
from src.app.services.embedding_service import embedding_service
from src.app.services.pinecone_service import pinecone_service

# Set up logging for console prints
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IngestPipeline")

class IngestPipeline:
    def __init__(self):
        pass

    async def run(
        self, 
        file_url: str, 
        file_key: str, 
        user_id: str, 
        chunking_strategy: str = "structure_aware",
        tenant: str = "default",
        permissions: List[str] = None,
        version: str = "1.0.0"
    ) -> Dict[str, Any]:
        """
        Executes the Document Ingestion Pipeline from Step 1 to Step 6.
        
        Steps:
        1. Size and Format Validation & Download from Wasabi (Max 25MB).
        2. Document Loading & Parsing (Layout-Aware LlamaParse with PyMuPDF fallback).
        3. Semantic + Structure-Aware + Hierarchical Chunking.
        4. Embedding generation (dense + sparse vectors).
        5. Metadata schema preparation.
        6. Dynamic Pinecone index creation, namespace isolation, version cleanup, and batch upsert.
        """
        doc_id = str(uuid.uuid4())
        user_permissions = permissions or ["read:all"]
        
        print("\n" + "="*80)
        print(f"STARTING FULL DOCUMENT INGESTION PIPELINE")
        print(f"Document ID: {doc_id}")
        print(f"User ID:     {user_id}")
        print(f"Tenant:      {tenant}")
        print(f"Version:     {version}")
        print(f"File Key:    {file_key}")
        print(f"Strategy:    {chunking_strategy}")
        print("="*80)

        # -------------------------------------------------------------
        # STEP 1 & 2: Download, Validate, and Parse
        # -------------------------------------------------------------
        print("\n>>> STEP 1 & 2: Downloading and Parsing layout...")
        try:
            parsed_doc = await document_loader.load_and_parse(file_url, file_key)
        except Exception as e:
            logger.error(f"Pipeline error during Download/Parsing stage: {e}")
            print(f"[-] PIPELINE FAILED: {e}")
            return {"success": False, "error": f"Download or parsing failed: {str(e)}"}

        parser_used = parsed_doc.get("parser_used", "unknown")
        pages = parsed_doc.get("pages", [])
        combined_markdown = parsed_doc.get("markdown", "")
        combined_text = parsed_doc.get("text", "")
        
        print(f"[+] STEP 1 & 2 Success: Document parsed successfully!")
        print(f"    - Parser used: {parser_used.upper()}")
        print(f"    - Total Pages: {len(pages)}")

        # -------------------------------------------------------------
        # STEP 3: Chunking
        # -------------------------------------------------------------
        print(f"\n>>> STEP 3: Chunking using strategy: {chunking_strategy}...")
        
        chunks_output = []
        parent_chunks = []
        child_chunks = []

        try:
            if chunking_strategy == "semantic":
                chunks_output = chunking_service.chunk_semantically(
                    text=combined_text,
                    doc_id=doc_id,
                    similarity_threshold=0.8,
                    max_chunk_size_chars=1500
                )
            elif chunking_strategy == "hierarchical":
                hierarchical_result = chunking_service.chunk_hierarchical(
                    markdown_text=combined_markdown,
                    doc_id=doc_id,
                    parent_max_chars=3000,
                    child_max_chars=600
                )
                parent_chunks = hierarchical_result["parent_chunks"]
                child_chunks = hierarchical_result["child_chunks"]
                # We embed and index the child sub-chunks
                chunks_output = child_chunks
            else:
                chunks_output = chunking_service.chunk_by_structure(
                    markdown_text=combined_markdown,
                    doc_id=doc_id,
                    max_chars=1500,
                    overlap_chars=200
                )
        except Exception as e:
            logger.error(f"Pipeline error during Chunking stage: {e}")
            print(f"[-] PIPELINE FAILED: {e}")
            return {"success": False, "error": f"Chunking stage failed: {str(e)}"}

        print(f"[+] STEP 3 Success: Chunking complete!")
        if chunking_strategy == "hierarchical":
            print(f"    - Parent chunks: {len(parent_chunks)}")
            print(f"    - Child chunks:  {len(child_chunks)}")
        else:
            print(f"    - Total chunks:  {len(chunks_output)}")

        if not chunks_output:
            print("[-] PIPELINE ABORTED: No chunks generated.")
            return {"success": False, "error": "No text chunks were generated from the document."}

        # -------------------------------------------------------------
        # STEP 4: Embedding (Dense & Sparse)
        # -------------------------------------------------------------
        print("\n>>> STEP 4: Generating vector embeddings...")
        
        chunk_texts = [c["text"] for c in chunks_output]
        
        try:
            # 1. Generate dense vectors (using TEI/vLLM or local fallback)
            dense_vectors = await embedding_service.get_dense_embeddings(chunk_texts)
            
            # 2. Generate sparse vectors locally (for Hybrid search)
            sparse_vectors = embedding_service.get_sparse_embeddings(chunk_texts)
            
        except Exception as e:
            logger.error(f"Pipeline error during Embedding stage: {e}")
            print(f"[-] PIPELINE FAILED: {e}")
            return {"success": False, "error": f"Embedding generation failed: {str(e)}"}

        vector_dim = len(dense_vectors[0])
        print(f"[+] STEP 4 Success: Embeddings generated!")
        print(f"    - Dense Vector Dimension: {vector_dim}")
        print(f"    - Sparse Vectors Count:  {len(sparse_vectors)}")

        # -------------------------------------------------------------
        # STEP 5 & 6: Pinecone Storage & Tenancy Metadata Packaging
        # -------------------------------------------------------------
        print("\n>>> STEP 5 & 6: Preparing metadata and upserting to Pinecone...")
        
        try:
            # 1. Ensure Index exists in Pinecone matching vector dimensions
            pinecone_service.ensure_index(dimension=vector_dim)
            
            # 2. De-duplicate: Purge old versions of this document from the tenant namespace
            # Pinecone lets us run a metadata filter delete inside a namespace
            pinecone_service.delete_by_doc_id(doc_id=doc_id, namespace=tenant)
            
            # 3. Assemble complete vector payloads with metadata
            pinecone_vectors = []
            for idx, chunk in enumerate(chunks_output):
                chunk_id = chunk["chunk_id"]
                
                # Metadata Schema definition (Step 5)
                metadata = {
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "file_key": file_key,
                    "user_id": user_id,
                    "tenant": tenant,
                    "version": version,
                    "permissions": user_permissions,
                    "headings_path": chunk["headings_path"],
                    "headings_path_str": chunk.get("headings_path_str", "Root"),
                    "text": chunk["text"],
                    "chunking_strategy": chunking_strategy
                }
                
                # Add extra relational info for hierarchical child chunks
                if "parent_id" in chunk:
                    metadata["parent_id"] = chunk["parent_id"]
                    # Optionally store parent context summary/headings path
                    parent_ref = [p for p in parent_chunks if p["chunk_id"] == chunk["parent_id"]]
                    if parent_ref:
                        metadata["parent_preview"] = parent_ref[0]["text"][:200]

                vector_payload = {
                    "id": chunk_id,
                    "values": dense_vectors[idx],
                    "metadata": metadata
                }
                
                if sparse_vectors and idx < len(sparse_vectors):
                    vector_payload["sparse_values"] = sparse_vectors[idx]

                pinecone_vectors.append(vector_payload)

            # 4. Batch upsert vectors inside tenant namespace
            upserted_count = pinecone_service.upsert_vectors(
                vectors=pinecone_vectors,
                namespace=tenant
            )
            
        except Exception as e:
            logger.error(f"Pipeline error during Pinecone upsert stage: {e}")
            print(f"[-] PIPELINE FAILED: {e}")
            return {"success": False, "error": f"Pinecone upsert failed: {str(e)}"}

        print(f"[+] STEP 5 & 6 Success: Vectors upserted to Pinecone!")
        print(f"    - Upserted chunks count: {upserted_count}")
        print(f"    - Tenancy Namespace:     {tenant}")
        print(f"    - Version tag:           {version}")

        print("\n" + "="*80)
        print("PIPELINE WORKFLOW COMPLETED SUCCESSFULLY (STEPS 1-6)")
        print("="*80 + "\n")

        return {
            "success": True,
            "doc_id": doc_id,
            "parser_used": parser_used,
            "chunking_strategy": chunking_strategy,
            "vector_dimension": vector_dim,
            "tenant": tenant,
            "version": version,
            "upserted_count": upserted_count
        }

ingest_pipeline = IngestPipeline()
