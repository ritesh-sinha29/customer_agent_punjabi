import logging
from fastapi import APIRouter, HTTPException
from src.app.services.db_service import db_service

logger = logging.getLogger("MemoryApi")
router = APIRouter(
    prefix="/v1/agent",
    tags=["User Memory"]
)

@router.get("/memory")
async def get_user_memory(user_id: str):
    """
    Fetches the persisted semantic facts and episodic summaries for a given user.
    """
    try:
        record = db_service.execute_query(
            "SELECT semantic_facts, episodic_summaries FROM user_memory WHERE user_id = %s",
            (user_id,)
        )
        if record:
            return {
                "success": True,
                "semantic_facts": record[0].get("semantic_facts") or [],
                "episodic_summaries": record[0].get("episodic_summaries") or []
            }
        return {
            "success": True,
            "semantic_facts": [],
            "episodic_summaries": []
        }
    except Exception as e:
        logger.error(f"Error fetching memory for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
