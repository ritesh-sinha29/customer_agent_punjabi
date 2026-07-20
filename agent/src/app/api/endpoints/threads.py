import logging
from fastapi import APIRouter, HTTPException
from src.app.services.db_service import db_service

logger = logging.getLogger("ThreadsApi")
router = APIRouter(
    prefix="/v1/agent",
    tags=["Agent Threads"]
)

@router.get("/threads")
async def get_threads(user_id: str):
    try:
        threads = db_service.execute_query(
            "SELECT id, title, created_at, updated_at FROM chat_thread WHERE user_id = %s ORDER BY updated_at DESC",
            (user_id,)
        )
        formatted_threads = []
        for t in threads:
            formatted_threads.append({
                "id": t["id"],
                "title": t["title"],
                "createdAt": t["created_at"].isoformat() if t.get("created_at") else None,
                "updatedAt": t["updated_at"].isoformat() if t.get("updated_at") else None,
            })
        return {"success": True, "threads": formatted_threads}
    except Exception as e:
        logger.error(f"Error fetching threads for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str):
    try:
        messages = db_service.execute_query(
            "SELECT id, role, content, created_at FROM chat_message WHERE thread_id = %s ORDER BY created_at ASC",
            (thread_id,)
        )
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "id": msg["id"],
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg["created_at"].strftime("%I:%M %p").lower() if msg.get("created_at") else ""
            })
        return {"success": True, "messages": formatted_messages}
    except Exception as e:
        logger.error(f"Error fetching messages for thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    try:
        db_service.execute_insert(
            "DELETE FROM chat_thread WHERE id = %s", (thread_id,)
        )
        return {"success": True}
    except Exception as e:
        logger.error(f"Error deleting thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
