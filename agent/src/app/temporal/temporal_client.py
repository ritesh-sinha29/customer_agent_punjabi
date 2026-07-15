from temporalio.client import Client
import os

# Read Temporal connection details from environment (default to localhost:7233)
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")

class TemporalClientManager:
    _client = None

    @classmethod
    async def get_client(cls) -> Client:
        if cls._client is None:
            cls._client = await Client.connect(TEMPORAL_HOST)
        return cls._client

async def get_temporal_client() -> Client:
    return await TemporalClientManager.get_client()
