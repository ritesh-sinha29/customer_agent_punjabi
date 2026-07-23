from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# Allow unsafe imports for activities
with workflow.unsafe.imports_passed_through():
    from src.app.temporal.activities import (
        ingest_document_activity,
        update_failure_status_activity,
        fetch_user_conversation_activity,
        check_message_usefulness_groq_activity,
        consolidate_user_memory_activity,
        embed_and_save_user_memory_activity,
        translate_message_activity,
    )


@workflow.defn
class MessageTranslationWorkflow:
    @workflow.run
    async def run(self, text: str) -> str:
        """
        Executes message translation to Punjabi with a strict 25-second timeout and retry policy.
        """
        return await workflow.execute_activity(
            translate_message_activity,
            args=[text],
            schedule_to_close_timeout=timedelta(seconds=25),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=1.5,
                maximum_attempts=2,
            ),
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


@workflow.defn
class UserMemoryWorkflow:
    @workflow.run
    async def run(self, user_id: str, thread_id: str) -> dict:
        """
        Orchestrates the background user memory consolidation workflow.
        """
        try:
            # 1. Fetch thread history and current memory
            history_data = await workflow.execute_activity(
                fetch_user_conversation_activity,
                args=[user_id, thread_id],
                schedule_to_close_timeout=timedelta(seconds=60),
            )
            
            messages = history_data.get("messages", [])
            current_facts = history_data.get("current_facts", [])
            
            if not messages:
                workflow.logger.info(f"No messages found for thread {thread_id}. Skipping memory consolidation.")
                return {"status": "skipped", "reason": "no_messages"}
                
            # 2. Check usefulness gate using Llama-3.1-8b-instant on Groq
            is_useful = await workflow.execute_activity(
                check_message_usefulness_groq_activity,
                args=[messages],
                schedule_to_close_timeout=timedelta(seconds=30),
            )
            
            if not is_useful:
                workflow.logger.info(f"Conversation classified as NOT useful for user {user_id}. Skipping memory consolidation.")
                return {"status": "skipped", "reason": "not_useful"}
                
            # 3. Consolidate memory using Llama-3.3-70b-versatile on Groq
            consolidation_result = await workflow.execute_activity(
                consolidate_user_memory_activity,
                args=[messages, current_facts],
                schedule_to_close_timeout=timedelta(seconds=60),
            )
            
            updated_facts = consolidation_result.get("semantic_facts", current_facts)
            new_summary = consolidation_result.get("episodic_summary", "")
            
            # 4. Save and index
            if new_summary or updated_facts != current_facts:
                await workflow.execute_activity(
                    embed_and_save_user_memory_activity,
                    args=[user_id, updated_facts, new_summary],
                    schedule_to_close_timeout=timedelta(seconds=60),
                )
                return {"status": "completed", "updated": True}
                
            return {"status": "completed", "updated": False}
        except Exception as e:
            workflow.logger.error(f"UserMemoryWorkflow failed: {e}")
            raise e
