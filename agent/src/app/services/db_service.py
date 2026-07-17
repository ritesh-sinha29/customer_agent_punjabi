import logging
import psycopg
from psycopg.rows import dict_row
from src.app.core.config import settings

logger = logging.getLogger("DbService")


class DbService:
    """
    Service to execute database queries directly against the Neon PostgreSQL instance.
    Uses psycopg for high-performance direct SQL interaction.
    """

    def __init__(self):
        self.db_url = settings.DATABASE_URL
        if not self.db_url:
            logger.error("DATABASE_URL is not set in settings!")

    def get_connection(self):
        """
        Creates and returns a standard connection with dictionary row formatting.
        """
        if not self.db_url:
            raise ValueError("DATABASE_URL is not configured.")
        return psycopg.connect(self.db_url, row_factory=dict_row)

    def execute_query(self, query: str, params: tuple = ()) -> list[dict]:
        """
        Executes a SELECT query and returns the results as a list of dicts.
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error executing query '{query}' with params {params}: {e}")
            raise e

    def execute_insert(self, query: str, params: tuple = ()) -> dict | None:
        """
        Executes an INSERT, UPDATE, or DELETE query and commits the transaction.
        If a RETURNING clause is present, returns the affected row as a dict.
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    conn.commit()
                    try:
                        return cur.fetchone()
                    except psycopg.ProgrammingError:
                        # No returning clause / results
                        return None
        except Exception as e:
            logger.error(f"Error executing insert '{query}' with params {params}: {e}")
            raise e


db_service = DbService()
