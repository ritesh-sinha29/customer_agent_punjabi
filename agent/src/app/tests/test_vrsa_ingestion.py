import asyncio
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

# Add project root to python path to resolve imports correctly
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# Fix Windows console print for Unicode
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from src.app.pipelines.ingest_pipeline import ingest_pipeline
from src.app.services.pinecone_service import pinecone_service

# Path to the target PDF
PDF_PATH = r"C:\Users\rox\Downloads\VRSA-AGROTECH.pdf"

def mock_download_file(file_url: str, file_key: str) -> str:
    """
    Safely copies the local PDF to a temporary directory so that the pipeline's
    cleanup logic will only delete the copy and leave the original file intact.
    """
    if not os.path.exists(PDF_PATH):
        raise FileNotFoundError(f"Target PDF file not found at: {PDF_PATH}")
    
    # Create temp file with PDF extension
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, "temp_VRSA-AGROTECH.pdf")
    
    print(f"[Mock Download] Copying {PDF_PATH} to temporary path: {temp_path}")
    shutil.copy2(PDF_PATH, temp_path)
    return temp_path

async def main():
    print("=" * 80)
    print("RUNNING PIPELINE INGESTION TEST FOR VRSA-AGROTECH.pdf")
    print("=" * 80)

    # 1. Connect check
    print("[+] Initializing connection...")

    # 2. Run Ingestion with mock download
    start_time = time.perf_counter()
    
    # Patch the download_file method to use our safe copy function
    with patch("src.app.services.document_loader.document_loader.download_file", side_effect=mock_download_file):
        try:
            result = await ingest_pipeline.run(
                file_url="http://dummy-url/VRSA-AGROTECH.pdf",
                file_key="VRSA-AGROTECH.pdf",
                user_id="test_user",
                tenant="default",
                job_id="vrsa_agrotech_test"
            )
        except Exception as e:
            print(f"[-] Ingestion crashed: {e}")
            result = {"success": False, "error": str(e)}

    duration = time.perf_counter() - start_time

    print("\n" + "=" * 80)
    print("INGESTION METRICS & RESULTS")
    print("=" * 80)
    print(f"Success:             {result.get('success')}")
    if result.get('success'):
        print(f"Total Time Taken:    {duration:.2f} seconds ({duration * 1000:.2f} ms)")
        print(f"Upserted Chunks:     {result.get('upserted_count')}")
        print(f"Vector Dimension:    {result.get('vector_dimension')}")
        print(f"Parser Used:         {result.get('parser_used')}")
        print(f"Chunking Strategy:   {result.get('chunking_strategy')}")
    else:
        print(f"Error Message:       {result.get('error')}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
