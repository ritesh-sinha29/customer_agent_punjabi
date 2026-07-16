import uuid
import json
import asyncio
import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from temporalio.client import WorkflowExecutionStatus, RPCError

from src.app.temporal.temporal_client import get_temporal_client
from src.app.temporal.workflows import DocumentIngestionWorkflow
from src.app.core.status_manager import status_manager

logger = logging.getLogger("IngestRouter")

router = APIRouter(prefix="/v1/ingest", tags=["Ingest"])

class IngestRequest(BaseModel):
    file_url: str = Field(..., description="The direct download URL of the uploaded file on Wasabi")
    file_key: str = Field(..., description="The S3 Object key of the uploaded file")
    userId: str = Field(..., description="The user ID of the document owner")
    tenant: str = Field("default", description="Namespace / Tenancy key")
    permissions: list[str] = Field(["read:all"], description="User permissions/roles for access control")
    version: str = Field("1.0.0", description="Document revision version")
    job_id: str | None = Field(None, description="Optional pre-generated job/document ID")

@router.post("")
async def start_ingestion(request: IngestRequest):
    job_id = request.job_id or str(uuid.uuid4())
    workflow_id = f"ingest-{job_id}"

    
    # 1. Initialize job status in Upstash Redis
    status_manager.initialize_job(job_id, request.file_key)
    
    try:
        # 2. Trigger Temporal workflow (propagating job_id)
        client = await get_temporal_client()
        await client.start_workflow(
            DocumentIngestionWorkflow.run,
            args=[
                request.file_url, 
                request.file_key, 
                request.userId, 
                request.tenant,
                request.permissions,
                request.version,
                job_id
            ],
            id=workflow_id,
            task_queue="ingestion-task-queue",
        )
    except Exception as e:
        # Update status to failed
        status_manager.update_status(job_id, 0, f"Failed to start workflow: {str(e)}", status="failed")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start Temporal workflow: {str(e)}"
        )
    
    return {
        "success": True,
        "message": "Ingestion workflow started successfully via Temporal",
        "data": {
            "job_id": job_id,
            "workflow_id": workflow_id,
            "status": "processing"
        }
    }

@router.get("/status/{job_id}/stream")
async def stream_job_status(job_id: str):
    """
    Streams ingestion progression events in real-time via Server-Sent Events (SSE).
    """
    async def event_generator():
        if not status_manager.client:
            yield f"data: {json.dumps({'error': 'Upstash Redis client is not active'})}\n\n"
            return

        # Fetch and yield initial job status
        init_status = status_manager.get_job_status(job_id)
        if init_status:
            yield f"data: {json.dumps(init_status)}\n\n"
            if init_status.get("status") in ["completed", "failed"]:
                return
        else:
            # Yield a placeholder check
            await asyncio.sleep(0.5)
            init_status = status_manager.get_job_status(job_id)
            if init_status:
                yield f"data: {json.dumps(init_status)}\n\n"

        pubsub = status_manager.client.pubsub()
        channel_name = f"job-channel-{job_id}"
        pubsub.subscribe(channel_name)

        try:
            while True:
                # Retrieve pubsub messages asynchronously
                message = await asyncio.to_thread(
                    pubsub.get_message, 
                    ignore_subscribe_messages=True, 
                    timeout=1.0
                )
                
                if message:
                    data = message["data"]
                    yield f"data: {data}\n\n"
                    
                    # Exit stream if job state is finalized
                    payload = json.loads(data)
                    if payload.get("status") in ["completed", "failed"]:
                        break
                
                # Keepalive ping
                yield ": keepalive\n\n"
                await asyncio.sleep(0.2)
                
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
        finally:
            try:
                pubsub.unsubscribe(channel_name)
                pubsub.close()
            except Exception:
                pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    # Check status manager first
    redis_status = status_manager.get_job_status(job_id)
    if redis_status:
        return redis_status

    workflow_id = f"ingest-{job_id}"
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        
        status_map = {
            WorkflowExecutionStatus.RUNNING: "processing",
            WorkflowExecutionStatus.COMPLETED: "completed",
            WorkflowExecutionStatus.FAILED: "failed",
            WorkflowExecutionStatus.CANCELED: "cancelled",
            WorkflowExecutionStatus.TERMINATED: "terminated",
            WorkflowExecutionStatus.TIMED_OUT: "timed_out",
            WorkflowExecutionStatus.CONTINUED_AS_NEW: "continued_as_new"
        }
        
        status_str = status_map.get(desc.status, "unknown")
        response_data = {
            "job_id": job_id,
            "workflow_id": workflow_id,
            "status": status_str,
            "start_time": desc.start_time.isoformat() if desc.start_time else None,
            "close_time": desc.close_time.isoformat() if desc.close_time else None,
        }
        
        if desc.status == WorkflowExecutionStatus.COMPLETED:
            result = await handle.result()
            response_data["result"] = result
        elif desc.status == WorkflowExecutionStatus.FAILED:
            response_data["error"] = "Workflow execution failed. Check worker logs or Temporal Web UI for details."
            
        return response_data
        
    except RPCError as e:
        if "not found" in str(e).lower() or e.status.name == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="Job not found in Temporal history")
        raise HTTPException(status_code=500, detail=f"Temporal RPC error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.delete("/{doc_id}")
async def delete_document(doc_id: str, tenant: str = "default"):
    """
    Deletes a document from the Pinecone vector index within the specified tenant namespace.
    """
    try:
        from src.app.services.pinecone_service import pinecone_service
        success = pinecone_service.delete_by_doc_id(doc_id, namespace=tenant)
        if not success:
            # We treat empty namespace or not found as ok for cleanup
            pass
        
        # Also clean up the job record in Redis
        if status_manager.client:
            status_manager.client.hdel("ingest_jobs", doc_id)
            
        return {"success": True, "message": f"Document {doc_id} successfully deleted from Pinecone."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
