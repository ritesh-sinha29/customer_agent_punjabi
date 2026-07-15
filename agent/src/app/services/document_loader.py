import os
import urllib.request
import tempfile
import logging
from typing import Any, Dict, List
from src.app.services.llama_service import llama_service

logger = logging.getLogger("DocumentLoader")

class DocumentLoader:
    """
    Handles Step 1 (Download & Size/Format Validation) and Step 2 (Document Loading & Parsing)
    with LlamaParse layout extraction and PyMuPDF fallback.
    """

    ALLOWED_EXTENSIONS = {
        ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".md", ".csv", ".xlsx", ".xls"
    }
    MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB limit

    def __init__(self):
        pass

    def validate_file_metadata(self, file_url: str, file_key: str) -> None:
        """
        Validate file extension and ensure it is supported.
        """
        _, ext = os.path.splitext(file_key.lower())
        if not ext:
            # Fallback to URL extension parsing
            _, ext = os.path.splitext(file_url.split("?")[0].lower())
            
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file format '{ext}'. Allowed: {sorted(list(self.ALLOWED_EXTENSIONS))}")

        logger.info(f"[Step 1] File format validation passed for format '{ext}'")

    def download_file(self, file_url: str, file_key: str) -> str:
        """
        Downloads a file from the provided URL, monitors download size, and returns the path to a temporary file.
        Size validation is checked before download and enforced during download.
        """
        self.validate_file_metadata(file_url, file_key)

        # Get file extension for temp file
        _, ext = os.path.splitext(file_key.lower())
        if not ext:
            _, ext = os.path.splitext(file_url.split("?")[0].lower())

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        temp_path = temp_file.name
        temp_file.close()  # Close so we can write to it with urllib

        logger.info(f"[Step 1] Initializing download from: {file_url}")
        
        try:
            # Perform HEAD request if possible to check Content-Length beforehand
            try:
                head_req = urllib.request.Request(file_url, method="HEAD")
                with urllib.request.urlopen(head_req, timeout=10) as head_resp:
                    content_length = head_resp.getheader("Content-Length")
                    if content_length:
                        size_bytes = int(content_length)
                        logger.info(f"[Step 1] File size from Content-Length header: {size_bytes / (1024*1024):.2f} MB")
                        if size_bytes > self.MAX_FILE_SIZE_BYTES:
                            raise ValueError(f"File size ({size_bytes / (1024*1024):.2f} MB) exceeds the maximum allowed limit of 25MB.")
            except Exception as head_err:
                if isinstance(head_err, ValueError):
                    raise head_err
                logger.warning(f"[Step 1] Could not retrieve Content-Length via HEAD request: {head_err}. Downloading with streaming validation.")

            # Stream download to enforce 25MB limit on the fly
            req = urllib.request.Request(
                file_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=30) as response, open(temp_path, "wb") as out_file:
                total_bytes = 0
                chunk_size = 1024 * 512  # 512 KB chunks
                
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    
                    total_bytes += len(chunk)
                    if total_bytes > self.MAX_FILE_SIZE_BYTES:
                        raise ValueError(f"File size exceeded the maximum allowed limit of 25MB during download.")
                    
                    out_file.write(chunk)
            
            logger.info(f"[Step 1] Download completed successfully. Size: {total_bytes / (1024*1024):.2f} MB. Saved to: {temp_path}")
            return temp_path

        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e

    async def parse_with_llamaparse(self, file_path: str) -> Dict[str, Any]:
        """
        Parses document with layout-awareness using LlamaParse.
        Extracts structured text, markdown representation, headings, and tables.
        """
        parser = llama_service.get_parser()
        if not parser:
            raise RuntimeError("LlamaParse client is not initialized or API key is missing.")

        logger.info("[Step 2] Sending document to LlamaParse API...")
        
        # Load layout-aware JSON representation which includes tables and structured page layout
        json_results = await parser.aload_data_json(file_path)
        
        if not json_results or len(json_results) == 0:
            raise RuntimeError("LlamaParse returned an empty result.")

        # LlamaParse returns a list of results, we take the first document representation
        doc_json = json_results[0]
        pages_data = []
        
        # Parse pages from the JSON structure
        raw_pages = doc_json.get("pages", [])
        combined_markdown = []
        combined_text = []

        for p in raw_pages:
            page_num = p.get("page", 0)
            page_text = p.get("text", "")
            page_md = p.get("markdown", "")
            
            combined_markdown.append(page_md)
            combined_text.append(page_text)
            
            # Extract tables if any exist in the items
            tables = []
            for item in p.get("items", []):
                if item.get("type") == "table":
                    tables.append({
                        "table_id": item.get("id"),
                        "csv": item.get("value"), # LlamaParse typically outputs tables in CSV format
                        "markdown": item.get("md_value")
                    })

            pages_data.append({
                "page_number": page_num,
                "text": page_text,
                "markdown": page_md,
                "tables": tables
            })

        logger.info(f"[Step 2] LlamaParse layout extraction complete: {len(pages_data)} pages processed.")
        
        return {
            "text": "\n\n".join(combined_text),
            "markdown": "\n\n".join(combined_markdown),
            "pages": pages_data,
            "parser_used": "llamaparse"
        }

    def parse_with_pymupdf(self, file_path: str) -> Dict[str, Any]:
        """
        Fallback parser using PyMuPDF (fitz) for fast text extraction from PDFs.
        Extracts pages and does basic layout parsing.
        """
        logger.info("[Step 2] Falling back to local PyMuPDF parser...")
        
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError(
                "PyMuPDF is not installed. To use the fallback parser, install 'pymupdf' (or import fitz)."
            )

        doc = fitz.open(file_path)
        pages_data = []
        combined_text = []
        combined_markdown = []

        for i, page in enumerate(doc):
            page_number = i + 1
            # Basic text extraction
            text = page.get_text("text")
            combined_text.append(text)
            
            # Try to build simple markdown formatting (e.g. bolding text sizes or structure if possible)
            # PyMuPDF allows block-based extraction
            blocks = page.get_text("blocks")
            page_md_lines = []
            
            # Very simple heuristic: short lines with larger fonts or single lines might be headings
            for b in blocks:
                block_text = b[4].strip()
                if not block_text:
                    continue
                # Simple rule: if block is short and in all caps or has specific line breaks, format as header
                if len(block_text) < 100 and (block_text.isupper() or block_text.count("\n") == 0):
                    page_md_lines.append(f"## {block_text}")
                else:
                    page_md_lines.append(block_text)

            page_md = "\n\n".join(page_md_lines)
            combined_markdown.append(page_md)

            # PyMuPDF table extraction if available in this version
            tables = []
            if hasattr(page, "find_tables"):
                try:
                    tabs = page.find_tables()
                    for tab_idx, tab in enumerate(tabs):
                        csv_data = []
                        # Extract table as list of rows
                        rows = tab.extract()
                        for row in rows:
                            csv_data.append(",".join([f'"{str(val).replace(chr(34), chr(34)+chr(34))}"' if val is not None else '' for val in row]))
                        tables.append({
                            "table_id": f"p{page_number}-t{tab_idx}",
                            "csv": "\n".join(csv_data),
                            "markdown": None
                        })
                except Exception as tab_err:
                    logger.warning(f"Failed to extract table from page {page_number}: {tab_err}")

            pages_data.append({
                "page_number": page_number,
                "text": text,
                "markdown": page_md,
                "tables": tables
            })

        logger.info(f"[Step 2] PyMuPDF extraction complete: {len(pages_data)} pages processed.")
        
        return {
            "text": "\n\n".join(combined_text),
            "markdown": "\n\n".join(combined_markdown),
            "pages": pages_data,
            "parser_used": "pymupdf"
        }

    async def load_and_parse(self, file_url: str, file_key: str) -> Dict[str, Any]:
        """
        Orchestrator for Step 1 and Step 2.
        Downloads document, performs checks, parses layout with LlamaParse, or falls back to PyMuPDF.
        """
        # Step 1: Download & size validation
        local_path = self.download_file(file_url, file_key)
        
        # Step 2: Document Loading & Parsing
        try:
            # Determine if we can use LlamaParse
            if llama_service.check_connection():
                try:
                    result = await self.parse_with_llamaparse(local_path)
                    return result
                except Exception as parse_err:
                    logger.error(f"LlamaParse extraction failed: {parse_err}. Falling back to PyMuPDF...")
            else:
                logger.warning("LlamaParse is not connected (check api_key). Falling back to PyMuPDF...")

            # Fallback
            result = self.parse_with_pymupdf(local_path)
            return result

        finally:
            # Clean up temp file
            if os.path.exists(local_path):
                try:
                    os.unlink(local_path)
                    logger.info(f"Cleaned up temporary file: {local_path}")
                except Exception as cleanup_err:
                    logger.warning(f"Could not clean up temp file {local_path}: {cleanup_err}")

document_loader = DocumentLoader()
