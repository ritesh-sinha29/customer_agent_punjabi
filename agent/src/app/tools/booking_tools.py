import uuid
import logging
import json
import re
import difflib
from pathlib import Path
from src.app.services.db_service import db_service

logger = logging.getLogger("BookingTools")

# 1. Load valid products from central product.json
# Path resolution relative to booking_tools.py: tools -> app -> src -> agent -> root
root_dir = Path(__file__).resolve().parents[4]
product_json_path = root_dir / "product.json"

try:
    with open(product_json_path, "r", encoding="utf-8") as f:
        VALID_PRODUCTS = json.load(f)
except Exception as e:
    logger.warning(f"Could not load central product.json: {e}. Falling back to hardcoded list.")
    VALID_PRODUCTS = [
        "Horsa-550X-Turbo",
        "TrioSan Gold",
        "MaxaPro-DS Dairy",
        "MaxaPro Liquid",
        "Buffalo-Power 2X",
        "Buffalo-F 1.5X"
    ]

# Common variations, abbreviations, typos, and Punjabi transliterations/translations
ALIASES = {
    # Horsa-550X-Turbo
    "horsa": "Horsa-550X-Turbo",
    "horsa 550x": "Horsa-550X-Turbo",
    "horsa 550": "Horsa-550X-Turbo",
    "horsa 550x turbo": "Horsa-550X-Turbo",
    "horsa-550x": "Horsa-550X-Turbo",
    "horsa550x": "Horsa-550X-Turbo",
    "horsa550xturbo": "Horsa-550X-Turbo",
    "ਹੋਰਸਾ": "Horsa-550X-Turbo",
    "ਹੋਰਸਾ 550": "Horsa-550X-Turbo",
    "ਹੋਰਸਾ 550ਐਕਸ": "Horsa-550X-Turbo",
    "ਹੋਰਸਾ 550 ਐਕਸ": "Horsa-550X-Turbo",
    "ਹੋਰਸਾ-550ਐਕਸ-ਟਰਬੋ": "Horsa-550X-Turbo",
    
    # TrioSan Gold
    "triosan": "TrioSan Gold",
    "trio san": "TrioSan Gold",
    "triosan gold": "TrioSan Gold",
    "ਟ੍ਰੀਓਸੈਨ": "TrioSan Gold",
    "ਟ੍ਰੀਓਸੈਨ ਗੋਲਡ": "TrioSan Gold",
    
    # MaxaPro-DS Dairy
    "maxapro ds": "MaxaPro-DS Dairy",
    "maxapro-ds": "MaxaPro-DS Dairy",
    "maxapro ds dairy": "MaxaPro-DS Dairy",
    "maxapro-ds dairy": "MaxaPro-DS Dairy",
    "maxapro dairy": "MaxaPro-DS Dairy",
    "ਮੈਕਸਾਪ੍ਰੋ ਡੀਐਸ": "MaxaPro-DS Dairy",
    "ਮੈਕਸਾਪ੍ਰੋ ਡੀ.ਐਸ": "MaxaPro-DS Dairy",
    "ਮੈਕਸਾਪ੍ਰੋ ਡੀਐਸ ਡੇਅਰੀ": "MaxaPro-DS Dairy",
    
    # MaxaPro Liquid
    "maxapro liquid": "MaxaPro Liquid",
    "maxapro-liquid": "MaxaPro Liquid",
    "maxaproliquid": "MaxaPro Liquid",
    "ਮੈਕਸਾਪ੍ਰੋ ਲਿਕਵਿਡ": "MaxaPro Liquid",
    "ਮੈਕਸਾਪ੍ਰੋ": "MaxaPro Liquid",
    
    # Buffalo-Power 2X
    "buffalo power": "Buffalo-Power 2X",
    "buffalo-power": "Buffalo-Power 2X",
    "buffalo power 2x": "Buffalo-Power 2X",
    "buffalo-power 2x": "Buffalo-Power 2X",
    "buffalo 2x": "Buffalo-Power 2X",
    "ਬਫਲੋ ਪਾਵਰ": "Buffalo-Power 2X",
    "ਬਫਲੋ ਪਾਵਰ 2ਐਕਸ": "Buffalo-Power 2X",
    
    # Buffalo-F 1.5X
    "buffalo f": "Buffalo-F 1.5X",
    "buffalo-f": "Buffalo-F 1.5X",
    "buffalo f 1.5x": "Buffalo-F 1.5X",
    "buffalo-f 1.5x": "Buffalo-F 1.5X",
    "buffalo f1.5x": "Buffalo-F 1.5X",
    "buffalo f 1.5": "Buffalo-F 1.5X",
    "buffalo 1.5x": "Buffalo-F 1.5X",
    "buffalo 1.5": "Buffalo-F 1.5X",
    "ਬਫਲੋ ਐਫ": "Buffalo-F 1.5X",
    "ਬਫਲੋ ਐਫ 1.5": "Buffalo-F 1.5X",
    "ਬਫਲੋ ਐਫ 1.5ਐਕਸ": "Buffalo-F 1.5X",
}


def normalize_str(s: str) -> str:
    """
    Normalizes string by lowercasing and keeping only alphanumeric and Punjabi characters.
    """
    return re.sub(r'[^a-zA-Z0-9\u0a00-\u0a7f]', '', s.lower())


def get_canonical_product_name(product_name: str) -> str:
    """
    Validates and maps a potentially hallucinated or misspelled product name to its canonical name.
    If the name is invalid/unrecognized, raises a ValueError listing valid products.
    """
    if not product_name:
        raise ValueError("Product name cannot be empty.")
        
    name_stripped = product_name.strip()
    
    # 1. Exact match (case-insensitive)
    for p in VALID_PRODUCTS:
        if name_stripped.lower() == p.lower():
            return p
            
    # 2. Check the pre-defined aliases (case-insensitive)
    name_lower = name_stripped.lower()
    if name_lower in ALIASES:
        return ALIASES[name_lower]
        
    # 3. Check normalized version of input against normalized canonical/alias names
    norm_input = normalize_str(name_stripped)
    if norm_input:
        for p in VALID_PRODUCTS:
            if norm_input == normalize_str(p):
                return p
        for alias_name, canonical_name in ALIASES.items():
            if norm_input == normalize_str(alias_name):
                return canonical_name
                
    # 4. Fuzzy match using difflib for close english variants
    close_matches = difflib.get_close_matches(name_stripped, VALID_PRODUCTS, n=1, cutoff=0.6)
    if close_matches:
        return close_matches[0]
        
    close_aliases = difflib.get_close_matches(name_lower, list(ALIASES.keys()), n=1, cutoff=0.7)
    if close_aliases:
        return ALIASES[close_aliases[0]]

    # Raise error if no match can be resolved (e.g., "abcd")
    raise ValueError(
        f"Invalid product name '{product_name}'. We could not identify this product. "
        f"Valid products are: {', '.join(VALID_PRODUCTS)}."
    )


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
    # 1. Verify and map product name to canonical name
    try:
        canonical_name = get_canonical_product_name(product_name)
    except ValueError as e:
        logger.error(f"Validation failed for booking: {e}")
        raise e

    # 2. Create the booking with canonical name
    booking_id = f"b-{uuid.uuid4().hex}"
    sql = """
        INSERT INTO "booking" (id, product_name, qty, user_id, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, 'requested', NOW(), NOW())
        RETURNING id, product_name, qty, user_id, status, created_at, updated_at;
    """
    try:
        record = db_service.execute_insert(sql, (booking_id, canonical_name, qty, user_id))
        logger.info(f"Created booking {booking_id} for user {user_id} with product {canonical_name}")
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
