import logging
import psycopg
from psycopg.rows import dict_row
from src.app.core.config import settings

logger = logging.getLogger("DbService")


class DbService:
    """
    Service to execute database queries directly against PostgreSQL instance.
    Handles graceful fallback if database URL is missing or unreachable.
    """

    def __init__(self):
        self.db_url = settings.DATABASE_URL
        if not self.db_url:
            logger.warning("DATABASE_URL is not set in settings!")

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
        if not self.db_url:
            return []
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error executing query '{query}': {e}")
            return []

    def execute_insert(self, query: str, params: tuple = ()) -> dict | None:
        """
        Executes an INSERT, UPDATE, or DELETE query and commits the transaction.
        """
        if not self.db_url:
            return None
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    conn.commit()
                    try:
                        return cur.fetchone()
                    except Exception:
                        return None
        except Exception as e:
            logger.error(f"Error executing insert '{query}': {e}")
            return None

    def ensure_chat_tables(self):
        """
        Ensures that chat_thread and chat_message tables exist in the database.
        """
        if not self.db_url:
            logger.warning("Skipping table verification because DATABASE_URL is not set.")
            return

        create_thread_table = """
        CREATE TABLE IF NOT EXISTS chat_thread (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            user_id TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        create_message_table = """
        CREATE TABLE IF NOT EXISTS chat_message (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL REFERENCES chat_thread(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        create_memory_table = """
        CREATE TABLE IF NOT EXISTS user_memory (
            user_id TEXT PRIMARY KEY,
            semantic_facts JSONB NOT NULL DEFAULT '[]',
            episodic_summaries JSONB NOT NULL DEFAULT '[]',
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        create_eval_suite_run_table = """
        CREATE TABLE IF NOT EXISTS eval_suite_run (
            id TEXT PRIMARY KEY,
            suite_name TEXT NOT NULL,
            faithfulness_avg DOUBLE PRECISION DEFAULT 0.0,
            relevance_avg DOUBLE PRECISION DEFAULT 0.0,
            context_precision_avg DOUBLE PRECISION DEFAULT 0.0,
            router_accuracy_avg DOUBLE PRECISION DEFAULT 0.0,
            hallucination_rate DOUBLE PRECISION DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'RUNNING',
            total_cases INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        create_eval_result_table = """
        CREATE TABLE IF NOT EXISTS eval_result (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES eval_suite_run(id) ON DELETE CASCADE,
            testcase_id TEXT,
            category TEXT,
            query TEXT NOT NULL,
            retrieved_contexts JSONB NOT NULL DEFAULT '[]',
            generated_answer TEXT NOT NULL,
            ground_truth TEXT,
            expected_route TEXT,
            actual_route TEXT,
            faithfulness_score DOUBLE PRECISION DEFAULT 0.0,
            relevance_score DOUBLE PRECISION DEFAULT 0.0,
            hallucination_flag BOOLEAN DEFAULT FALSE,
            judge_rationale TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        create_thread_index = "CREATE INDEX IF NOT EXISTS idx_chat_thread_user_id ON chat_thread(user_id);"
        create_message_index = "CREATE INDEX IF NOT EXISTS idx_chat_message_thread_id ON chat_message(thread_id);"
        create_eval_result_index = "CREATE INDEX IF NOT EXISTS idx_eval_result_run_id ON eval_result(run_id);"
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(create_thread_table)
                    cur.execute(create_message_table)
                    cur.execute(create_memory_table)
                    cur.execute(create_eval_suite_run_table)
                    cur.execute(create_eval_result_table)
                    cur.execute(create_thread_index)
                    cur.execute(create_message_index)
                    cur.execute(create_eval_result_index)
                    conn.commit()
            logger.info("Chat and evaluation tables and indexes verified/created successfully.")
        except Exception as e:
            logger.warning(f"Could not connect to PostgreSQL database: {e}")


db_service = DbService()
