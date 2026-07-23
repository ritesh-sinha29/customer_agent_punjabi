import asyncio
import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import redis.asyncio as aioredis
import logfire
from src.app.core.config import settings
from src.app.services.embedding_service import embedding_service

logger = logging.getLogger("SemanticCacheService")

TTL_SEVEN_DAYS = 604800  # 7 days in seconds
SIMILARITY_THRESHOLD = 0.90  # Cosine similarity threshold for semantic cache hit


class SemanticCacheService:
    """
    High-performance per-user Semantic Cache engine using Redis and dense embeddings.

    Optimization Features:
    1. Exact SHA-256 Prompt Hash Lookup (O(1), <3ms execution time, zero embedding overhead).
    2. Dense Vector Cosine Similarity Search (Threshold >= 0.90) for semantic hits.
    3. Auto-indexing of semantic hits back into exact hash cache for instant future lookups.
    4. 7-Day TTL (604800 seconds) auto-expiration on all cached items per user.
    """

    def __init__(self):
        self._redis_client: Optional[aioredis.Redis] = None

    def _get_redis(self) -> Optional[aioredis.Redis]:
        if self._redis_client is None and settings.UPSTASH_REDIS_URL:
            try:
                self._redis_client = aioredis.from_url(
                    settings.UPSTASH_REDIS_URL, decode_responses=True
                )
            except Exception as e:
                logger.error(f"Failed to connect to Redis for Semantic Cache: {e}")
        return self._redis_client

    def _normalize_text(self, text: str) -> str:
        return text.strip().lower()

    def _compute_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _log_cache_hit(self, user_id: str, prompt: str, match_type: str, similarity: float = 1.0):
        msg = f"[REDIS SEMANTIC CACHE HIT] User={user_id} | Type={match_type.upper()} | Similarity={similarity:.4f} | Prompt='{prompt[:50]}...'"
        print(f"\033[92m{msg}\033[0m")
        logger.info(msg)
        try:
            logfire.info(
                "REDIS SEMANTIC CACHE HIT: user={user_id} match_type={match_type} similarity={similarity} prompt={prompt}",
                user_id=user_id,
                match_type=match_type,
                similarity=round(similarity, 4),
                prompt=prompt,
            )
        except Exception as e:
            pass

    async def get_cached_response(self, user_id: str, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves cached response for user_id and prompt.
        Checks exact hash first (<3ms), then falls back to vector cosine similarity calculation.
        """
        redis_client = self._get_redis()
        if not redis_client:
            return None

        clean_prompt = self._normalize_text(prompt)
        if not clean_prompt:
            return None

        prompt_hash = self._compute_hash(clean_prompt)
        exact_key = f"semcache:{user_id}:hash:{prompt_hash}"

        # ─── 1. FAST PATH: Exact Prompt Hash Lookup (O(1)) ─────────────────────
        try:
            exact_hit = await redis_client.get(exact_key)
            if exact_hit:
                data = json.loads(exact_hit)
                data["match_type"] = "exact"
                self._log_cache_hit(user_id, prompt, "exact", 1.0)
                return data
        except Exception as e:
            logger.error(f"Error checking exact prompt cache: {e}")

        # ─── 2. SEMANTIC PATH: Dense Vector Cosine Similarity Search ───────────
        try:
            # Generate dense embedding vector for incoming query
            embeddings = await embedding_service.get_dense_embeddings([clean_prompt])
            if not embeddings or not embeddings[0]:
                return None

            query_vec = np.array(embeddings[0], dtype=np.float32)
            query_norm = np.linalg.norm(query_vec)
            if query_norm == 0:
                return None
            unit_query_vec = query_vec / query_norm

            # Fetch stored vector items for this user from Redis index
            index_key = f"semcache:{user_id}:items"
            item_ids = await redis_client.smembers(index_key)
            if not item_ids:
                return None

            # Batch retrieve vector item payloads using pipeline
            pipe = redis_client.pipeline()
            for item_id in item_ids:
                pipe.get(f"semcache:{user_id}:item:{item_id}")
            raw_items = await pipe.execute()

            best_sim = -1.0
            best_match_data = None
            expired_items = []

            for item_id, raw in zip(item_ids, raw_items):
                if not raw:
                    expired_items.append(item_id)
                    continue

                try:
                    cached_item = json.loads(raw)
                    cached_vec = np.array(cached_item["embedding"], dtype=np.float32)
                    cached_norm = np.linalg.norm(cached_vec)
                    if cached_norm == 0:
                        continue
                    
                    unit_cached_vec = cached_vec / cached_norm
                    similarity = float(np.dot(unit_query_vec, unit_cached_vec))

                    if similarity > best_sim:
                        best_sim = similarity
                        best_match_data = cached_item
                except Exception as parse_err:
                    logger.error(f"Error parsing cached vector item {item_id}: {parse_err}")

            # Clean up dangling expired item IDs asynchronously
            if expired_items:
                await redis_client.srem(index_key, *expired_items)

            # Check if best similarity exceeds threshold (>= 0.90)
            if best_sim >= SIMILARITY_THRESHOLD and best_match_data:
                self._log_cache_hit(user_id, prompt, "semantic", best_sim)
                
                # Cache-through optimization: Save hit under exact prompt hash to make next identical call O(1)!
                payload = {
                    "prompt": prompt,
                    "response": best_match_data["response"],
                    "match_type": "semantic",
                    "similarity": round(best_sim, 4),
                    "created_at": best_match_data.get("created_at", time.time())
                }
                await redis_client.setex(exact_key, TTL_SEVEN_DAYS, json.dumps(payload))
                return payload

        except Exception as e:
            logger.error(f"Error executing semantic vector cache search: {e}")

        return None

    async def set_cached_response(self, user_id: str, prompt: str, response: str) -> bool:
        """
        Saves user prompt, dense embedding vector, and agent response to Redis with 7-day TTL.
        """
        redis_client = self._get_redis()
        if not redis_client or not response or not response.strip():
            return False

        clean_prompt = self._normalize_text(prompt)
        if not clean_prompt:
            return False

        try:
            prompt_hash = self._compute_hash(clean_prompt)
            exact_key = f"semcache:{user_id}:hash:{prompt_hash}"

            # 1. Save Exact Hash Entry with 7-day TTL
            payload = {
                "prompt": prompt,
                "response": response,
                "created_at": time.time()
            }
            await redis_client.setex(exact_key, TTL_SEVEN_DAYS, json.dumps(payload))

            # 2. Save Vector Item for Semantic Matching
            embeddings = await embedding_service.get_dense_embeddings([clean_prompt])
            if embeddings and embeddings[0]:
                item_id = uuid.uuid4().hex[:12]
                item_key = f"semcache:{user_id}:item:{item_id}"
                index_key = f"semcache:{user_id}:items"

                item_payload = {
                    "prompt": prompt,
                    "response": response,
                    "embedding": embeddings[0],
                    "created_at": time.time()
                }

                pipe = redis_client.pipeline()
                pipe.setex(item_key, TTL_SEVEN_DAYS, json.dumps(item_payload))
                pipe.sadd(index_key, item_id)
                pipe.expire(index_key, TTL_SEVEN_DAYS)
                await pipe.execute()

                logger.info(f"[Semantic Cache STORED] User={user_id}, Hash={prompt_hash[:8]}, ItemId={item_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to store entry in semantic cache: {e}")

        return False


semantic_cache_service = SemanticCacheService()
