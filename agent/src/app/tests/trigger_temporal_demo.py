import os
import sys
import time
import asyncio
import threading
import http.server
import socketserver
from pathlib import Path

# Add workspace directory to python path
workspace_dir = str(Path(__file__).resolve().parents[3])
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from src.app.temporal.temporal_client import get_temporal_client
from src.app.temporal.workflows import DocumentIngestionWorkflow

PORT = 8099
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        import urllib.parse
        # Parse the URL path to get the clean filename
        url_path = urllib.parse.urlparse(path).path
        filename = os.path.basename(url_path)
        # Force resolution to tests directory
        resolved_path = os.path.join(DIRECTORY, filename)
        print(f"[HTTP Server Debug] Requested: {path} | DIRECTORY: {DIRECTORY} | Resolved: {resolved_path} | Exists: {os.path.exists(resolved_path)}")
        return resolved_path
    
    def log_message(self, format, *args):
        # Suppress standard logging to keep console clean
        pass

def start_http_server():
    """
    Starts a simple HTTP server in a background thread to host demo.md locally.
    """
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"[HTTP Server] Hosting files from '{DIRECTORY}' at http://127.0.0.1:{PORT}")
        httpd.serve_forever()

async def trigger_workflow():
    print("\n" + "="*80)
    print("TEMPORAL INGESTION PIPELINE DEMO TRIGGER")
    print("="*80)
    
    # 1. Start HTTP Server in background thread
    server_thread = threading.Thread(target=start_http_server, daemon=True)
    server_thread.start()
    
    # Allow server a moment to bind
    await asyncio.sleep(1)
    
    # 2. Connect to Temporal client
    print("\nConnecting to Temporal server...")
    client = None
    try:
        client = await get_temporal_client()
        print("[+] Connected to Temporal successfully.")
    except Exception as e:
        print(f"[-] Failed to connect to Temporal: {e}")
        print("[!] Temporal Server is offline. Falling back to direct local pipeline execution for demo...")

    # Define workflow payload
    file_url = f"http://127.0.0.1:{PORT}/demo.md"
    file_key = "demo.md"
    user_id = "demo-user-111"
    tenant = "demo-tenant-punjabi"
    permissions = ["read:demo"]
    version = "1.0.0"
    
    workflow_id = f"demo-ingest-{int(time.time())}"
    task_queue = "ingestion-task-queue"

    print(f"\nTriggering Ingestion Demo:")
    if client:
        print(f"  Execution Mode: Temporal Workflow")
        print(f"  Workflow ID:    {workflow_id}")
    else:
        print(f"  Execution Mode: Direct Local Execution (Temporal Offline)")
    print(f"  File URL:       {file_url}")
    print(f"  Tenant:         {tenant}")
    
    start_time = time.time()
    
    try:
        if client:
            # Trigger and await completion of the workflow via Temporal
            print("\nExecuting workflow on Temporal worker... (please make sure your worker is running)")
            print("Waiting for result...")
            result = await client.execute_workflow(
                DocumentIngestionWorkflow.run,
                args=[file_url, file_key, user_id, tenant, permissions, version, workflow_id],
                id=workflow_id,
                task_queue=task_queue,
            )
        else:
            # Fallback to direct local pipeline run
            print("\nRunning ingestion pipeline directly...")
            from src.app.pipelines.ingest_pipeline import ingest_pipeline
            result = await ingest_pipeline.run(
                file_url=file_url,
                file_key=file_key,
                user_id=user_id,
                tenant=tenant,
                permissions=permissions,
                version=version,
                job_id=workflow_id
            )
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        print("\n" + "="*80)
        print("DEMO INGESTION EXECUTED SUCCESSFULLY")
        print("="*80)
        print(f"Total time taken: {elapsed_time:.3f} seconds")
        print(f"Result details:")
        print(f"  Doc ID:            {result.get('doc_id')}")
        print(f"  Parser Used:       {result.get('parser_used', 'unknown').upper()}")
        print(f"  Strategy Used:     {result.get('chunking_strategy')}")
        print(f"  Total Chunks:      {result.get('chunks_count')}")
        print(f"  Tenant Namespace:  {result.get('tenant')}")
        print(f"  Version Tag:       {result.get('version')}")
        print(f"  Pinecone Upserted: {result.get('upserted_count')}")
        print("="*80 + "\n")
        
    except Exception as e:
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"\n[-] Execution failed after {elapsed_time:.3f} seconds: {e}")

if __name__ == "__main__":
    asyncio.run(trigger_workflow())
