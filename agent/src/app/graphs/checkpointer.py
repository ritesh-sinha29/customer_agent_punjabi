import asyncio
from typing import Any, AsyncIterator, Optional, Sequence
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata, CheckpointTuple, ChannelVersions
from langgraph.checkpoint.redis import RedisSaver
from src.app.core.config import settings

class AsyncRedisSaver(RedisSaver):
    """
    An extension of RedisSaver that implements the async checkpointer methods
    by executing the synchronous methods in a thread pool.
    This resolves the NotImplementedError when using `ainvoke` with LangGraph.
    """

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.get_tuple, config)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.put, config, checkpoint, metadata, new_versions
        )

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.put_writes, config, writes, task_id, task_path
        )

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        loop = asyncio.get_running_loop()
        # Fetch the checkpoints synchronously in a thread and yield them asynchronously
        items = await loop.run_in_executor(
            None, lambda: list(self.list(config, filter=filter, before=before, limit=limit))
        )
        for item in items:
            yield item

def get_redis_checkpointer() -> AsyncRedisSaver:
    """
    Returns an AsyncRedisSaver instance connected to Upstash Redis.
    """
    if not settings.UPSTASH_REDIS_URL:
        raise ValueError("UPSTASH_REDIS_URL is not set in settings.")
    return AsyncRedisSaver(redis_url=settings.UPSTASH_REDIS_URL)
