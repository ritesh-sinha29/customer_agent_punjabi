from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# Allow unsafe imports for activities
with workflow.unsafe.imports_passed_through():
    from src.app.temporal.activities import (
        ingest_document_activity,
        update_failure_status_activity,
    )


@workflow.defn
class DocumentIngestionWorkflow:
    @workflow.run
    async def run(
        self,
        file_url: str,
        file_key: str,
        user_id: str,
        tenant: str = "default",
        permissions: list[str] = None,
        version: str = "1.0.0",
        job_id: str = None,
    ) -> dict:
        """
        Orchestrates the document ingestion pipeline activity with configured retries.
        """
        try:
            # Execute the activity with a 3-minute timeout and 1 attempt (fail fast)
            return await workflow.execute_activity(
                ingest_document_activity,
                args=[
                    file_url,
                    file_key,
                    user_id,
                    tenant,
                    permissions or ["read:all"],
                    version,
                    job_id,
                ],
                schedule_to_close_timeout=timedelta(minutes=3),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=5),
                    backoff_coefficient=2.0,
                    maximum_attempts=1,
                ),
            )
        except Exception as e:
            # If ingestion activity fails or times out, trigger failure activity to update status in Redis
            workflow.logger.error(f"Workflow failed for job {job_id}: {e}")
            try:
                await workflow.execute_activity(
                    update_failure_status_activity,
                    args=[job_id, f"Processing timed out or failed: {str(e)}"],
                    schedule_to_close_timeout=timedelta(seconds=30),
                )
            except Exception as update_err:
                workflow.logger.error(
                    f"Failed to record failure status for job {job_id}: {update_err}"
                )
            raise e
