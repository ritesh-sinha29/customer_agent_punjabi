from temporalio import activity

from src.app.pipelines.ingest_pipeline import ingest_pipeline


@activity.defn
async def ingest_document_activity(
    file_url: str,
    file_key: str,
    user_id: str,
    tenant: str = "default",
    permissions: list[str] = None,
    version: str = "1.0.0",
    job_id: str = None,
) -> dict:
    """
    Temporal Activity that executes the document ingestion pipeline.
    """
    activity.logger.info(
        f"Running Ingestion pipeline for user {user_id}, file: {file_key}, tenant: {tenant}"
    )
    result = await ingest_pipeline.run(
        file_url=file_url,
        file_key=file_key,
        user_id=user_id,
        tenant=tenant,
        permissions=permissions or ["read:all"],
        version=version,
        job_id=job_id,
    )
    return result


@activity.defn
async def update_failure_status_activity(job_id: str, error_message: str) -> None:
    """
    Temporal Activity that marks the job status as failed in Redis.
    """
    from src.app.core.status_manager import status_manager

    activity.logger.info(f"Marking job {job_id} as failed in Redis: {error_message}")
    status_manager.update_status(job_id, 0, error_message, status="failed")
