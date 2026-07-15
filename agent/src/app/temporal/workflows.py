from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

# Allow unsafe imports for activities
with workflow.unsafe.imports_passed_through():
    from src.app.temporal.activities import ingest_document_activity

@workflow.defn
class DocumentIngestionWorkflow:
    @workflow.run
    async def run(
        self, 
        file_url: str, 
        file_key: str, 
        user_id: str, 
        chunking_strategy: str = "structure_aware",
        tenant: str = "default",
        permissions: list[str] = None,
        version: str = "1.0.0"
    ) -> dict:
        """
        Orchestrates the document ingestion pipeline activity with configured retries.
        """
        # Execute the activity with an explicit Retry Policy
        return await workflow.execute_activity(
            ingest_document_activity,
            args=[file_url, file_key, user_id, chunking_strategy, tenant, permissions or ["read:all"], version],
            schedule_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=5),
                backoff_coefficient=2.0,
                maximum_attempts=2,
            ),
        )
