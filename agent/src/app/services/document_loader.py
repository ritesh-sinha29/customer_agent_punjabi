import os
import urllib.request
import tempfile
import logging
from typing import Any, Dict
from src.app.services.llama_service import llama_service

logger = logging.getLogger("DocumentLoader")

class DocumentLoader:
    """
    Step 1: Download & Size Validation (Max 25MB).
    Step 2: Document Parsing (LlamaParse layout extraction, with local fallback).
    """

    MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB limit

    def __init__(self):
        self.llama_service = llama_service

    def download_file(self, file_url: str, file_key: str) -> str:
        """
        Downloads a file from the provided URL, monitors download size, and returns the path to a temporary file.
        Enforces a 25MB limit.
        """
        _, ext = os.path.splitext(file_key.lower())
        if not ext:
            _, ext = os.path.splitext(file_url.split("?")[0].lower())

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        temp_path = temp_file.name
        temp_file.close()

        logger.info(f"[Step 1] Downloading file from: {file_url}")
        
        try:
            # Check size via HEAD request if possible
            try:
                head_req = urllib.request.Request(file_url, method="HEAD")
                with urllib.request.urlopen(head_req, timeout=10) as head_resp:
                    content_length = head_resp.getheader("Content-Length")
                    if content_length and int(content_length) > self.MAX_FILE_SIZE_BYTES:
                        raise ValueError("File exceeds maximum allowed size of 25MB.")
            except Exception as head_err:
                if isinstance(head_err, ValueError):
                    raise head_err

            # Download with progressive size checking
            req = urllib.request.Request(file_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as response, open(temp_path, "wb") as out_file:
                total_bytes = 0
                while True:
                    chunk = response.read(1024 * 512)  # 512 KB chunks
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > self.MAX_FILE_SIZE_BYTES:
                        raise ValueError("File exceeds maximum allowed size of 25MB.")
                    out_file.write(chunk)
            
            logger.info(f"[Step 1] Download completed successfully. Size: {total_bytes / (1024*1024):.2f} MB")
            return temp_path

        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e

    async def parse_with_llamaparse(self, file_path: str) -> Dict[str, Any]:
        """
        Parses document using LlamaParse.
        """
        parser = llama_service.get_parser()
        if not parser:
            raise RuntimeError("LlamaParse client is not initialized.")

        logger.info("[Step 2] Sending document to LlamaParse...")
        
        # Load documents via LlamaParse
        documents = await parser.aload_data(file_path)
        combined_text = "\n\n".join([doc.text for doc in documents])
        
        pages_data = []
        for idx, doc in enumerate(documents):
            pages_data.append({
                "page_number": idx + 1,
                "text": doc.text,
                "markdown": doc.text,
                "tables": []
            })
            
        logger.info(f"[Step 2] LlamaParse complete: {len(pages_data)} pages processed.")
        return {
            "text": combined_text,
            "markdown": combined_text,
            "pages": pages_data,
            "parser_used": "llamaparse"
        }

    def parse_fallback(self, file_path: str) -> Dict[str, Any]:
        """
        Fallback parser (PyMuPDF for PDFs, direct file reading for text files).
        """
        logger.info("[Step 2] Using fallback parser...")
        _, ext = os.path.splitext(file_path.lower())
        
        # If PDF, try PyMuPDF
        if ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(file_path)
                pages_data = []
                combined_text = []
                for i, page in enumerate(doc):
                    page_num = i + 1
                    text = page.get_text()
                    combined_text.append(text)
                    pages_data.append({
                        "page_number": page_num,
                        "text": text,
                        "markdown": text,
                        "tables": []
                    })
                return {
                    "text": "\n\n".join(combined_text),
                    "markdown": "\n\n".join(combined_text),
                    "pages": pages_data,
                    "parser_used": "pymupdf_fallback"
                }
            except ImportError:
                raise ImportError("PyMuPDF is not installed. Run 'pip install pymupdf' to enable fallback.")
        
        # Otherwise, try reading as raw text
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text_content = f.read()
            return {
                "text": text_content,
                "markdown": text_content,
                "pages": [{"page_number": 1, "text": text_content, "markdown": text_content, "tables": []}],
                "parser_used": "text_fallback"
            }
        except Exception as e:
            raise RuntimeError(f"Fallback text parsing failed: {e}")

    async def load_and_parse(self, file_url: str, file_key: str) -> Dict[str, Any]:
        """
        Orchestration: Download, validate size, parse with LlamaParse, or use local fallback.
        """
        # Step 1: Download & size validation
        local_path = self.download_file(file_url, file_key)
        
        # Step 2: Document Loading & Parsing
        try:
            if llama_service.check_connection():
                try:
                    return await self.parse_with_llamaparse(local_path)
                except Exception as parse_err:
                    logger.error(f"LlamaParse failed: {parse_err}. Falling back...")
            
            return self.parse_fallback(local_path)

        finally:
            if os.path.exists(local_path):
                try:
                    os.unlink(local_path)
                except Exception as cleanup_err:
                    logger.warning(f"Could not clean up temp file {local_path}: {cleanup_err}")

document_loader = DocumentLoader()
