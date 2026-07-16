import asyncio
import logging

from temporalio.worker import Worker

from src.app.temporal.activities import ingest_document_activity
from src.app.temporal.temporal_client import get_temporal_client
from src.app.temporal.workflows import DocumentIngestionWorkflow

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def main():
    # Connect to the Temporal client
    client = await get_temporal_client()

    # Initialize the worker with our workflow and activity
    worker = Worker(
        client,
        task_queue="ingestion-task-queue",
        workflows=[DocumentIngestionWorkflow],
        activities=[ingest_document_activity],
    )

    logging.info(
        "Temporal Worker started. Listening on task queue 'ingestion-task-queue'..."
    )
    await worker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Worker stopped.")
