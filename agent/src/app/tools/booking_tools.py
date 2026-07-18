import uuid
import logging
from src.app.services.db_service import db_service

logger = logging.getLogger("BookingTools")


def create_booking(user_id: str, product_name: str, qty: int) -> dict:
    """
    Creates a new product booking/reservation in the database.

    Args:
        user_id (str): The unique ID of the user placing the booking.
        product_name (str): The name or SKU of the product.
        qty (int): Quantity of the product to book.

    Returns:
        dict: The created booking record from the database.
    """
    booking_id = f"b-{uuid.uuid4().hex}"
    sql = """
        INSERT INTO "booking" (id, product_name, qty, user_id, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, 'requested', NOW(), NOW())
        RETURNING id, product_name, qty, user_id, status, created_at, updated_at;
    """
    try:
        record = db_service.execute_insert(sql, (booking_id, product_name, qty, user_id))
        logger.info(f"Created booking {booking_id} for user {user_id}")
        return record
    except Exception as e:
        logger.error(f"Failed to create booking for user {user_id}: {e}")
        raise e


def get_booking_updates(user_id: str) -> list[dict]:
    """
    Retrieves all bookings and their status updates for a specific user.

    Args:
        user_id (str): The unique ID of the user.

    Returns:
        list[dict]: A list of booking records with progress tracking information.
    """
    sql = """
        SELECT id, product_name, qty, user_id, status, created_at, updated_at
        FROM "booking"
        WHERE user_id = %s
        ORDER BY created_at DESC;
    """
    try:
        records = db_service.execute_query(sql, (user_id,))
        logger.info(f"Retrieved {len(records)} bookings for user {user_id}")
        return records
    except Exception as e:
        logger.error(f"Failed to get bookings for user {user_id}: {e}")
        raise e
