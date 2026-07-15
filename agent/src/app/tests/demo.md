# demo for test scripts for Ingestion pipelines.

This is a demonstration document for validating the layout-aware ingestion pipeline.
It covers the integration of LlamaParse layout extraction, semantic chunking, Qwen3 embedding representations, and Pinecone vector store upserts.

## Step 1: Document Upload & Download
- The document is uploaded to the Wasabi S3 storage bucket.
- The pipeline downloads the document and validates that the file size is under the 25MB threshold.

## Step 2: Layout-Aware Parsing
- We use LlamaParse to extract structured layout from complex documents.
- If LlamaParse is offline, the pipeline gracefully falls back to local PyMuPDF extraction.

## Step 3: Chunking Strategies
- **Structure-Aware Chunking:** Recursively splits markdown by heading levels to retain hierarchical context paths.
- **Semantic Chunking:** Groups sentences dynamically by vector similarity drops.
- **Hierarchical Chunking:** Establishes parent-child relationships between large passages and smaller searchable chunks.

## Step 4: Embedding & Vector Upsert
- Dense vectors are generated using 1024-dimension models.
- Sparse vectors are generated locally to enable hybrid search.
- The payload is upserted to Pinecone within isolated tenant namespaces.
