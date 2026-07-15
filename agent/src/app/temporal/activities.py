from temporalio import activity
from src.app.pipelines.ingest_pipeline import ingest_pipeline

@activity.defn
async def ingest_document_activity(
    file_url: str, 
    file_key: str, 
    user_id: str, 
    chunking_strategy: str = "structure_aware",
    tenant: str = "default",
    permissions: list[str] = None,
    version: str = "1.0.0"
) -> dict:
    """
    Temporal Activity that executes the document ingestion pipeline.
    """
    activity.logger.info(f"Running ingestion pipeline for user {user_id}, file: {file_key}, chunking strategy: {chunking_strategy}, tenant: {tenant}")
    result = await ingest_pipeline.run(
        file_url=file_url, 
        file_key=file_key, 
        user_id=user_id, 
        chunking_strategy=chunking_strategy,
        tenant=tenant,
        permissions=permissions or ["read:all"],
        version=version
    )
    return result
