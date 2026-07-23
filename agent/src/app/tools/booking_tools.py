import uuid
import logging
from langchain_core.tools import tool
from src.app.services.db_service import db_service

logger = logging.getLogger("BookingTools")


@tool
def create_booking(user_id: str, items: list[dict]) -> list[dict]:
    """
    Creates product bookings/reservations in the database for one or multiple products.

    Args:
        user_id (str): The unique ID of the user placing the booking.
        items (list[dict]): List of items to book, where each item has "product_name" (str) and "qty" (int).
                            Example: [{"product_name": "MaxaPro-DS Dairy", "qty": 1}, {"product_name": "MaxaPro Liquid", "qty": 2}]

    Returns:
        list[dict]: A list of created booking records from the database.
    """
    if not items or not isinstance(items, list):
        raise ValueError("Items list must not be empty.")

    results = []
    for item in items:
        pname = item.get("product_name")
        if not pname:
            continue
        qty = int(item.get("qty", 1))
        booking_id = f"b-{uuid.uuid4().hex}"
        sql = """
            INSERT INTO "booking" (id, product_name, qty, user_id, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, 'requested', NOW(), NOW())
            RETURNING id, product_name, qty, user_id, status, created_at, updated_at;
        """
        try:
            record = db_service.execute_insert(sql, (booking_id, pname, qty, user_id))
            if record:
                results.append(record)
                logger.info(f"Created booking {booking_id} for user {user_id} with product {pname} (qty={qty})")
        except Exception as e:
            logger.error(f"Failed to create booking item {pname} for user {user_id}: {e}")
            raise ValueError(f"Failed to create booking for '{pname}' in database: {str(e)}")

    if not results:
        raise ValueError("Failed to create any booking records in database.")

    return results


@tool
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
        raise ValueError(f"Failed to retrieve bookings from database: {str(e)}")
