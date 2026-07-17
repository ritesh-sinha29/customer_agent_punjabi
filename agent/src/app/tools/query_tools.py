import uuid
import logging
from src.app.services.db_service import db_service

logger = logging.getLogger("QueryTools")


def create_query(user_id: str, title: str, description: str) -> dict:
    """
    Creates a new support query/ticket in the database.

    Args:
        user_id (str): The unique ID of the user creating the query.
        title (str): The title or summary of the query.
        description (str): Detailed explanation of the query or support request.

    Returns:
        dict: The created query record from the database.
    """
    query_id = f"q-{uuid.uuid4().hex}"
    sql = """
        INSERT INTO "query" (id, title, description, user_id, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, 'pending', NOW(), NOW())
        RETURNING id, title, description, user_id, status, created_at, updated_at;
    """
    try:
        record = db_service.execute_insert(sql, (query_id, title, description, user_id))
        logger.info(f"Created query {query_id} for user {user_id}")
        return record
    except Exception as e:
        logger.error(f"Failed to create query for user {user_id}: {e}")
        raise e


def get_user_queries(user_id: str) -> list[dict]:
    """
    Retrieves all support queries/tickets created by a specific user.

    Args:
        user_id (str): The unique ID of the user.

    Returns:
        list[dict]: A list of query records belonging to the user.
    """
    sql = """
        SELECT id, title, description, user_id, status, created_at, updated_at
        FROM "query"
        WHERE user_id = %s
        ORDER BY created_at DESC;
    """
    try:
        records = db_service.execute_query(sql, (user_id,))
        logger.info(f"Retrieved {len(records)} queries for user {user_id}")
        return records
    except Exception as e:
        logger.error(f"Failed to get queries for user {user_id}: {e}")
        raise e
