import asyncio
import logging

from temporalio.worker import Worker

from src.app.temporal.activities import (
    ingest_document_activity,
    fetch_user_conversation_activity,
    check_message_usefulness_groq_activity,
    consolidate_user_memory_activity,
    embed_and_save_user_memory_activity,
)
from src.app.temporal.eval_activities import (
    run_single_evaluation_activity,
    save_eval_run_activity,
)
from src.app.temporal.temporal_client import get_temporal_client
from src.app.temporal.workflows import DocumentIngestionWorkflow, UserMemoryWorkflow
from src.app.temporal.eval_workflows import EvaluationSuiteWorkflow

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def main():
    # Connect to the Temporal client
    client = await get_temporal_client()

    # Initialize the worker with our workflows and activities
    worker = Worker(
        client,
        task_queue="ingestion-task-queue",
        workflows=[DocumentIngestionWorkflow, UserMemoryWorkflow, EvaluationSuiteWorkflow],
        activities=[
            ingest_document_activity,
            fetch_user_conversation_activity,
            check_message_usefulness_groq_activity,
            consolidate_user_memory_activity,
            embed_and_save_user_memory_activity,
            run_single_evaluation_activity,
            save_eval_run_activity,
        ],
    )

    logging.info(
        "Temporal Worker started. Listening on task queue 'ingestion-task-queue' (Ingestion, Memory, & Evaluation)..."
    )
    await worker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Worker stopped.")
