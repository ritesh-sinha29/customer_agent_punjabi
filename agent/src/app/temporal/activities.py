from temporalio import activity
from src.app.pipelines.ingest_pipeline import ingest_pipeline

@activity.defn
async def ingest_document_activity(file_url: str, file_key: str, user_id: str) -> dict:
    """
    Temporal Activity that executes the document ingestion pipeline.
    """
    activity.logger.info(f"Running ingestion pipeline for user {user_id}, file: {file_key}")
    result = await ingest_pipeline.run(file_url=file_url, file_key=file_key, user_id=user_id)
    return result
