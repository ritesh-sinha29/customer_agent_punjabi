import base64
import json
import redis.asyncio as redis
from typing import Any, AsyncIterator, Optional, Sequence
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    SerializerProtocol
)
from src.app.core.config import settings

def serialize_typed(typed_data: tuple[str, bytes]) -> bytes:
    """Helper to serialize a (type_str, data_bytes) tuple into JSON bytes with base64 data."""
    type_str, data_bytes = typed_data
    b64_str = base64.b64encode(data_bytes).decode("utf-8")
    return json.dumps({"t": type_str, "d": b64_str}).encode("utf-8")

def deserialize_typed(serialized_bytes: bytes) -> tuple[str, bytes]:
    """Helper to deserialize JSON bytes back into a (type_str, data_bytes) tuple."""
    obj = json.loads(serialized_bytes.decode("utf-8"))
    data_bytes = base64.b64decode(obj["d"])
    return (obj["t"], data_bytes)

class UpstashRedisSaver(BaseCheckpointSaver):
    """
    A custom LangGraph Checkpoint Saver for Upstash Redis.
    Uses standard Redis commands (hashes, sorted sets, lists) that are 100% compatible
    with Upstash, completely avoiding RediSearch (FT.*) or RedisJSON JSON.* commands.
    Uses LangGraph's typed serializer format (dumps_typed / loads_typed).
    """
    def __init__(self, redis_client: redis.Redis, *, serde: Optional[SerializerProtocol] = None):
        super().__init__(serde=serde)
        self.redis = redis_client

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id")

        # 1. Resolve latest checkpoint_id if not specified
        if not checkpoint_id:
            key_set = f"checkpoints:{thread_id}:{checkpoint_ns}"
            latest = await self.redis.zrevrange(key_set, 0, 0)
            if not latest:
                return None
            checkpoint_id = latest[0].decode("utf-8")

        # 2. Get checkpoint hash data
        key = f"checkpoint:{thread_id}:{checkpoint_ns}:{checkpoint_id}"
        data = await self.redis.hgetall(key)
        if not data:
            return None

        # Deserialize using typed serialization format
        checkpoint = self.serde.loads_typed(deserialize_typed(data[b"checkpoint"]))
        metadata = self.serde.loads_typed(deserialize_typed(data[b"metadata"]))
        
        parent_checkpoint_id = data.get(b"parent_checkpoint_id")
        parent_config = None
        if parent_checkpoint_id:
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": parent_checkpoint_id.decode("utf-8")
                }
            }

        # 3. Retrieve writes for this checkpoint
        writes = []
        writes_key_pattern = f"writes:{thread_id}:{checkpoint_ns}:{checkpoint_id}:*"
        keys = await self.redis.keys(writes_key_pattern)
        for k in keys:
            task_id = k.decode("utf-8").split(":")[-1]
            raw_writes = await self.redis.lrange(k, 0, -1)
            for w in raw_writes:
                typed_data = deserialize_typed(w)
                channel, val_bytes = self.serde.loads_typed(typed_data)
                writes.append((task_id, channel, val_bytes))

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id
                }
            },
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=writes
        )

    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: dict) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]

        key = f"checkpoint:{thread_id}:{checkpoint_ns}:{checkpoint_id}"
        parent_id = config["configurable"].get("checkpoint_id")

        # Serialize using typed serialization format
        checkpoint_typed = self.serde.dumps_typed(checkpoint)
        metadata_typed = self.serde.dumps_typed(metadata)

        mapping = {
            "checkpoint": serialize_typed(checkpoint_typed),
            "metadata": serialize_typed(metadata_typed),
        }
        if parent_id:
            mapping["parent_checkpoint_id"] = parent_id.encode("utf-8")

        # Save hash
        await self.redis.hset(key, mapping=mapping)

        # Save to sorted set index for list/retrieve ordering (using timestamp as score)
        key_set = f"checkpoints:{thread_id}:{checkpoint_ns}"
        
        # Parse or default score timestamp
        ts = 0.0
        if checkpoint.get("ts"):
            try:
                # If ISO string
                from datetime import datetime
                dt = datetime.fromisoformat(checkpoint["ts"].replace("Z", "+00:00"))
                ts = dt.timestamp()
            except ValueError:
                ts = 0.0
        
        await self.redis.zadd(key_set, {checkpoint_id: ts})

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id
            }
        }

    async def aput_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = "") -> None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        key = f"writes:{thread_id}:{checkpoint_ns}:{checkpoint_id}:{task_id}"
        serialized_writes = []
        for channel, value in writes:
            typed_data = self.serde.dumps_typed((channel, value))
            serialized_writes.append(serialize_typed(typed_data))

        if serialized_writes:
            await self.redis.rpush(key, *serialized_writes)

    async def alist(self, config: RunnableConfig | None, *, filter: dict[str, Any] | None = None, before: RunnableConfig | None = None, limit: int | None = None) -> AsyncIterator[CheckpointTuple]:
        if not config:
            return
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")

        key_set = f"checkpoints:{thread_id}:{checkpoint_ns}"
        
        checkpoint_ids = await self.redis.zrevrange(key_set, 0, -1)
        
        count = 0
        for cid_bytes in checkpoint_ids:
            cid = cid_bytes.decode("utf-8")
            
            if before and cid == before["configurable"].get("checkpoint_id"):
                continue
                
            tup = await self.aget_tuple({
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": cid
                }
            })
            if tup:
                if filter:
                    match = True
                    for k, v in filter.items():
                        if tup.metadata.get(k) != v:
                            match = False
                            break
                    if not match:
                        continue
                        
                yield tup
                count += 1
                if limit and count >= limit:
                    break

# ─── Singleton Loader ─────────────────────────────────────────────────────────
_CHECKPOINTER = None

def get_redis_checkpointer() -> UpstashRedisSaver:
    """
    Returns a singleton instance of our custom UpstashRedisSaver.
    """
    global _CHECKPOINTER
    if _CHECKPOINTER is None:
        redis_url = settings.UPSTASH_REDIS_URL
        if not redis_url:
            raise ValueError("UPSTASH_REDIS_URL is not configured in the settings.")
            
        client = redis.from_url(redis_url)
        _CHECKPOINTER = UpstashRedisSaver(client)
        
    return _CHECKPOINTER
