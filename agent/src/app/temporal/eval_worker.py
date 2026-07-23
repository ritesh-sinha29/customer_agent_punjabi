import asyncio
import logging
from temporalio.worker import Worker

from src.app.temporal.eval_activities import (
    run_single_evaluation_activity,
    save_eval_run_activity,
)
from src.app.temporal.eval_workflows import EvaluationSuiteWorkflow
from src.app.temporal.temporal_client import get_temporal_client

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def main():
    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue="eval-task-queue",
        workflows=[EvaluationSuiteWorkflow],
        activities=[
            run_single_evaluation_activity,
            save_eval_run_activity,
        ],
    )
    logging.info("Dedicated Evaluation Temporal Worker listening on queue 'eval-task-queue'...")
    await worker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Eval Worker stopped.")
