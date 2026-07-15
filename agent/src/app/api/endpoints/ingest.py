import uuid
from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from src.app.pipelines.ingest_pipeline import ingest_pipeline

router = APIRouter(prefix="/v1/ingest", tags=["Ingest"])

# Simple in-memory database to track async job statuses
jobs_db: Dict[str, Dict[str, Any]] = {}

class IngestRequest(BaseModel):
    file_url: str = Field(..., description="The direct download URL of the uploaded file on Wasabi")
    file_key: str = Field(..., description="The S3 Object key of the uploaded file")
    userId: str = Field(..., description="The user ID of the document owner")

async def run_pipeline_task(job_id: str, file_url: str, file_key: str, user_id: str):
    jobs_db[job_id]["status"] = "processing"
    try:
        result = await ingest_pipeline.run(file_url, file_key, user_id)
        jobs_db[job_id]["status"] = "completed"
        jobs_db[job_id]["result"] = result
    except Exception as e:
        jobs_db[job_id]["status"] = "failed"
        jobs_db[job_id]["error"] = str(e)

@router.post("")
async def start_ingestion(request: IngestRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    
    # Store initial job state
    jobs_db[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "file_key": request.file_key,
        "user_id": request.userId,
    }
    
    # Run the parsing/ingestion in background task so API responds immediately (non-blocking)
    background_tasks.add_task(
        run_pipeline_task, 
        job_id, 
        request.file_url, 
        request.file_key, 
        request.userId
    )
    
    return {
        "success": True,
        "message": "Ingestion task queued successfully",
        "data": {
            "job_id": job_id,
            "status": "queued"
        }
    }

@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs_db[job_id]
