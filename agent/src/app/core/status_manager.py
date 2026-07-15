import time
import json
import logging
from typing import Any, Dict
import redis
from src.app.core.config import settings

logger = logging.getLogger("StatusManager")

class StatusManager:
    """
    Manages job status tracking and real-time event publishing using Upstash Redis.
    Allows worker process (Temporal) to push status updates and API process to stream them via SSE.
    """

    def __init__(self):
        self.redis_url = settings.UPSTASH_REDIS_URL
        self.client = None
        
        if self.redis_url:
            try:
                # Initialize Redis connection
                self.client = redis.from_url(
                    self.redis_url, 
                    decode_responses=True,
                    socket_timeout=10.0,
                    socket_keepalive=True
                )
                # Ping test
                self.client.ping()
                logger.info("Successfully connected to Upstash Redis for status tracking.")
            except Exception as e:
                logger.error(f"Failed to connect to Upstash Redis: {e}")
        else:
            logger.warning("UPSTASH_REDIS_URL is not configured. Job status tracking will be inactive.")

    def initialize_job(self, job_id: str, file_name: str) -> None:
        """
        Creates an initial record for the job in Redis.
        """
        if not self.client:
            return
            
        # Clean the file_name by extracting the basename and stripping the unique upload ID/timestamp prefix
        import os
        import re
        base_name = os.path.basename(file_name)
        match = re.match(r"^\d+-[a-z0-9]+-(.+)$", base_name)
        display_name = match.group(1) if match else base_name

        payload = {
            "job_id": job_id,
            "file_name": display_name,
            "status": "processing",
            "current_step": 0,
            "step_message": "Job initiated",
            "updated_at": time.time()
        }
        try:
            self.client.hset("ingest_jobs", job_id, json.dumps(payload))
            self.client.publish(f"job-channel-{job_id}", json.dumps(payload))
        except Exception as e:
            logger.error(f"Failed to initialize job {job_id} in Redis: {e}")

    def update_status(self, job_id: str, step: int, message: str, status: str = "processing") -> None:
        """
        Updates the status of a job and publishes the progress to its pubsub channel.
        """
        if not self.client:
            return

        try:
            # Retrieve existing job data to keep file_name
            job_data_str = self.client.hget("ingest_jobs", job_id)
            file_name = "unknown"
            if job_data_str:
                job_data = json.loads(job_data_str)
                file_name = job_data.get("file_name", "unknown")

            payload = {
                "job_id": job_id,
                "file_name": file_name,
                "status": status,
                "current_step": step,
                "step_message": message,
                "updated_at": time.time()
            }
            # Save status
            self.client.hset("ingest_jobs", job_id, json.dumps(payload))
            # Publish event for SSE stream
            self.client.publish(f"job-channel-{job_id}", json.dumps(payload))
            logger.info(f"[StatusManager] Job {job_id} -> Step {step}/6: {message} ({status})")
        except Exception as e:
            logger.error(f"Failed to update job status {job_id} in Redis: {e}")

    def get_job_status(self, job_id: str) -> Dict[str, Any] | None:
        """
        Retrieves the current status of a job.
        """
        if not self.client:
            return None
        try:
            data = self.client.hget("ingest_jobs", job_id)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Failed to get job status {job_id} from Redis: {e}")
        return None

status_manager = StatusManager()
