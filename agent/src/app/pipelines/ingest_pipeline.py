import logging
import uuid
from typing import Any, Dict, List

from src.app.core.status_manager import status_manager
from src.app.services.chunking_service import chunking_service
from src.app.services.document_loader import document_loader
from src.app.services.embedding_service import embedding_service
from src.app.services.llama_service import llama_service
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
        tenant: str = "default",
        permissions: List[str] = None,
        version: str = "1.0.0",
        job_id: str = None,
    ) -> Dict[str, Any]:
        """
        Executes the Document Ingestion Pipeline from Step 1 to Step 6.

        Steps:
        1. Size and Format Validation & Download from Wasabi (Max 25MB).
        2. Document Loading & Parsing (Layout-Aware LlamaParse with PyMuPDF fallback).
        3. Combined Semantic-Hierarchical Chunking.
        4. Embedding generation (dense + sparse vectors).
        5. Metadata schema preparation.
        6. Pinecone upserting.
        """
        doc_id = job_id or str(uuid.uuid4())
        user_permissions = permissions or ["read:all"]

        print("\n" + "=" * 80)
        print("STARTING FULL DOCUMENT INGESTION PIPELINE")
        print(f"Job/Doc ID:  {doc_id}")
        print(f"User ID:     {user_id}")
        print(f"Tenant:      {tenant}")
        print(f"Version:     {version}")
        print(f"File Key:    {file_key}")
        print("=" * 80)

        # -------------------------------------------------------------
        # STEP 1 & 2: Download & Parse
        # -------------------------------------------------------------
        print("\n>>> STEP 1 & 2: Downloading and Parsing layout...")
        status_manager.update_status(
            doc_id, 1, "Downloading document from storage S3 bucket..."
        )

        try:
            # Check size & download
            local_path = document_loader.download_file(file_url, file_key)

            # Update step to parsing
            status_manager.update_status(
                doc_id, 2, "Parsing document structure and layout via LlamaParse..."
            )

            if llama_service.check_connection():
                try:
                    parsed_doc = await document_loader.parse_with_llamaparse(local_path)
                except Exception as parse_err:
                    logger.error(f"LlamaParse failed: {parse_err}. Falling back...")
                    parsed_doc = document_loader.parse_fallback(local_path)
            else:
                parsed_doc = document_loader.parse_fallback(local_path)

        except Exception as e:
            logger.error(f"Pipeline error during Download/Parsing stage: {e}")
            print(f"[-] PIPELINE FAILED: {e}")
            status_manager.update_status(
                doc_id, 0, f"Download/Parsing failed: {str(e)}", status="failed"
            )
            return {"success": False, "error": f"Download or parsing failed: {str(e)}"}

        parser_used = parsed_doc.get("parser_used", "unknown")
        pages = parsed_doc.get("pages", [])
        combined_markdown = parsed_doc.get("markdown", "")
        combined_text = parsed_doc.get("text") or combined_markdown

        print("[+] STEP 1 & 2 Success: Document parsed successfully!")
        print(f"    - Parser used: {parser_used.upper()}")
        print(f"    - Total Pages: {len(pages)}")

        # -------------------------------------------------------------
        # STEP 3: Chunking (Combined Semantic & Hierarchical)
        # -------------------------------------------------------------
        print(
            "\n>>> STEP 3: Chunking using combined Semantic-Hierarchical strategy..."
        )
        status_manager.update_status(
            doc_id,
            3,
            "Splitting document into combined semantic-hierarchical chunks...",
        )

        chunks_output = []
        parent_chunks = []
        child_chunks = []
        chunking_strategy = "semantic_hierarchical"

        try:
            hierarchical_result = chunking_service.chunk_hierarchical(
                markdown_text=combined_markdown,
                doc_id=doc_id,
                parent_max_chars=3000,
                child_max_chars=800,
                similarity_threshold=0.8,
            )
            parent_chunks = hierarchical_result["parent_chunks"]
            child_chunks = hierarchical_result["child_chunks"]
            chunks_output = child_chunks
        except Exception as e:
            logger.error(f"Pipeline error during Chunking stage: {e}")
            print(f"[-] PIPELINE FAILED: {e}")
            status_manager.update_status(
                doc_id, 0, f"Chunking failed: {str(e)}", status="failed"
            )
            return {"success": False, "error": f"Chunking stage failed: {str(e)}"}

        print("[+] STEP 3 Success: Chunking complete!")
        print(f"    - Parent chunks (logical sections): {len(parent_chunks)}")
        print(f"    - Child chunks (semantic units):    {len(child_chunks)}")

        if not chunks_output:
            print("[-] PIPELINE ABORTED: No chunks generated.")
            status_manager.update_status(
                doc_id, 0, "No text chunks generated from document.", status="failed"
            )
            return {
                "success": False,
                "error": "No text chunks were generated from the document.",
            }

        # -------------------------------------------------------------
        # STEP 4: Embedding (Dense & Sparse)
        # -------------------------------------------------------------
        print("\n>>> STEP 4: Generating vector embeddings...")
        status_manager.update_status(
            doc_id, 4, "Generating dense (1024d) and sparse TF embeddings..."
        )

        chunk_texts = [c["text"] for c in chunks_output]

        try:
            dense_vectors = await embedding_service.get_dense_embeddings(chunk_texts)
            sparse_vectors = embedding_service.get_sparse_embeddings(chunk_texts)
        except Exception as e:
            logger.error(f"Pipeline error during Embedding stage: {e}")
            print(f"[-] PIPELINE FAILED: {e}")
            status_manager.update_status(
                doc_id, 0, f"Embedding generation failed: {str(e)}", status="failed"
            )
            return {"success": False, "error": f"Embedding generation failed: {str(e)}"}

        vector_dim = len(dense_vectors[0])
        print("[+] STEP 4 Success: Embeddings generated!")
        print(f"    - Dense Vector Dimension: {vector_dim}")

        # -------------------------------------------------------------
        # STEP 5 & 6: Pinecone Storage & Tenancy Metadata Packaging
        # -------------------------------------------------------------
        print("\n>>> STEP 5 & 6: Preparing metadata and upserting to Pinecone...")
        status_manager.update_status(
            doc_id, 5, "Checking Pinecone index and clearing older revisions..."
        )

        try:
            # Ensure Index exists
            pinecone_service.ensure_index(dimension=vector_dim)

            # De-duplicate: Purge old versions
            pinecone_service.delete_by_doc_id(doc_id=doc_id, namespace=tenant)

            status_manager.update_status(
                doc_id, 6, f"Batch upserting {len(chunks_output)} chunks to Pinecone..."
            )

            # Assemble payloads
            pinecone_vectors = []
            for idx, chunk in enumerate(chunks_output):
                chunk_id = chunk["chunk_id"]

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
                    "chunking_strategy": "semantic_hierarchical",
                }

                if "parent_id" in chunk:
                    metadata["parent_id"] = chunk["parent_id"]
                    parent_ref = [
                        p for p in parent_chunks if p["chunk_id"] == chunk["parent_id"]
                    ]
                    if parent_ref:
                        metadata["parent_preview"] = parent_ref[0]["text"][:200]

                vector_payload = {
                    "id": chunk_id,
                    "values": dense_vectors[idx],
                    "metadata": metadata,
                }

                if sparse_vectors and idx < len(sparse_vectors):
                    vector_payload["sparse_values"] = sparse_vectors[idx]

                pinecone_vectors.append(vector_payload)

            # Upsert
            upserted_count = pinecone_service.upsert_vectors(
                vectors=pinecone_vectors, namespace=tenant
            )

        except Exception as e:
            logger.error(f"Pipeline error during Pinecone upsert stage: {e}")
            print(f"[-] PIPELINE FAILED: {e}")
            status_manager.update_status(
                doc_id, 0, f"Pinecone storage failed: {str(e)}", status="failed"
            )
            return {"success": False, "error": f"Pinecone upsert failed: {str(e)}"}

        print("[+] STEP 5 & 6 Success: Vectors upserted to Pinecone!")
        print(f"    - Upserted chunks count: {upserted_count}")

        print("\n" + "=" * 80)
        print("PIPELINE WORKFLOW COMPLETED SUCCESSFULLY (STEPS 1-6)")
        print("=" * 80 + "\n")

        # Update status to completed!
        status_manager.update_status(
            doc_id,
            6,
            f"Successfully processed and stored {upserted_count} chunks in Pinecone namespace '{tenant}'!",
            status="completed",
        )

        return {
            "success": True,
            "doc_id": doc_id,
            "parser_used": parser_used,
            "chunking_strategy": chunking_strategy,
            "vector_dimension": vector_dim,
            "tenant": tenant,
            "version": version,
            "upserted_count": upserted_count,
        }


ingest_pipeline = IngestPipeline()
