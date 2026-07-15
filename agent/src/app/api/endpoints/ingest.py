import uuid
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from temporalio.client import WorkflowExecutionStatus
from temporalio.exceptions import RPCError

from src.app.temporal.temporal_client import get_temporal_client
from src.app.temporal.workflows import DocumentIngestionWorkflow

router = APIRouter(prefix="/v1/ingest", tags=["Ingest"])

class IngestRequest(BaseModel):
    file_url: str = Field(..., description="The direct download URL of the uploaded file on Wasabi")
    file_key: str = Field(..., description="The S3 Object key of the uploaded file")
    userId: str = Field(..., description="The user ID of the document owner")
    chunking_strategy: str = Field("structure_aware", description="Chunking strategy: 'structure_aware', 'semantic', or 'hierarchical'")
    tenant: str = Field("default", description="Namespace / Tenancy key")
    permissions: list[str] = Field(["read:all"], description="User permissions/roles for access control")
    version: str = Field("1.0.0", description="Document revision version")

@router.post("")
async def start_ingestion(request: IngestRequest):
    job_id = str(uuid.uuid4())
    workflow_id = f"ingest-{job_id}"
    
    try:
        client = await get_temporal_client()
        await client.start_workflow(
            DocumentIngestionWorkflow.run,
            args=[
                request.file_url, 
                request.file_key, 
                request.userId, 
                request.chunking_strategy,
                request.tenant,
                request.permissions,
                request.version
            ],
            id=workflow_id,
            task_queue="ingestion-task-queue",
        )
    except Exception as e:
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

@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
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

