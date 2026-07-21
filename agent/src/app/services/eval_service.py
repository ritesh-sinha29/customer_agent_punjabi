import os
import json
import uuid
import logging
from typing import List, Dict, Any

from src.app.services.db_service import db_service
from src.app.temporal.temporal_client import get_temporal_client
from src.app.temporal.eval_workflows import EvaluationSuiteWorkflow

logger = logging.getLogger("EvalService")

GOLDEN_SET_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "golden_set.json"
)


class EvalService:
    def load_golden_set(self) -> List[Dict[str, Any]]:
        """Loads golden benchmark dataset from disk."""
        if not os.path.exists(GOLDEN_SET_PATH):
            logger.warning(f"Golden dataset file not found at {GOLDEN_SET_PATH}")
            return []
        try:
            with open(GOLDEN_SET_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading golden set: {e}")
            return []

    async def trigger_eval_run(self, suite_name: str = "Quick Benchmark (2 Samples)", sample_count: int = 2) -> Dict[str, Any]:
        """
        Triggers a Temporal Evaluation Workflow on queue 'ingestion-task-queue'.
        Picks random sample_count (default 2) questions to save API tokens and costs.
        """
        import random
        all_samples = self.load_golden_set()
        if not all_samples:
            samples = []
        elif len(all_samples) <= sample_count:
            samples = all_samples
        else:
            samples = random.sample(all_samples, sample_count)

        run_id = f"eval-{uuid.uuid4().hex[:8]}"

        db_service.ensure_chat_tables()
        insert_sql = """
        INSERT INTO eval_suite_run 
        (id, suite_name, status, total_cases)
        VALUES (%s, %s, %s, %s);
        """
        db_service.execute_insert(insert_sql, (run_id, f"{suite_name} ({len(samples)} items)", "RUNNING", len(samples)))

        try:
            client = await get_temporal_client()
            await client.start_workflow(
                EvaluationSuiteWorkflow.run,
                {
                    "run_id": run_id,
                    "suite_name": f"{suite_name} ({len(samples)} items)",
                    "samples": samples,
                },
                id=run_id,
                task_queue="ingestion-task-queue",
            )
            logger.info(f"Triggered Temporal Evaluation Workflow {run_id} for {len(samples)} items")
            return {"run_id": run_id, "status": "RUNNING", "total_cases": len(samples), "mode": "TEMPORAL"}
        except Exception as e:
            logger.warning(f"Could not trigger Temporal workflow directly: {e}. Executing inline fallback.")
            from src.app.temporal.eval_activities import run_single_evaluation_activity, save_eval_run_activity
            
            async def run_inline():
                results = []
                for sample in samples:
                    res = await run_single_evaluation_activity(sample)
                    results.append(res)
                summary = {
                    "run_id": run_id,
                    "suite_name": f"{suite_name} ({len(samples)} items)",
                    "status": "COMPLETED",
                    "results": results,
                }
                await save_eval_run_activity(summary)

            import asyncio
            asyncio.create_task(run_inline())
            return {"run_id": run_id, "status": "RUNNING", "total_cases": len(samples), "mode": "ASYNC_FALLBACK"}

    async def trigger_custom_eval_query(
        self, query: str, ground_truth: str = "", expected_route: str = "RAG_SEARCH"
    ) -> Dict[str, Any]:
        """
        Runs evaluation for a single custom query entered by Admin in the UI.
        """
        custom_sample = {
            "id": f"custom-{uuid.uuid4().hex[:6]}",
            "category": "Admin Custom Test",
            "query": query,
            "ground_truth": ground_truth or "Factual and accurate response based on catalog documentation.",
            "expected_route": expected_route or "RAG_SEARCH",
        }

        run_id = f"eval-custom-{uuid.uuid4().hex[:6]}"
        suite_name = f"Custom Test: {query[:30]}..."

        db_service.ensure_chat_tables()
        insert_sql = """
        INSERT INTO eval_suite_run 
        (id, suite_name, status, total_cases)
        VALUES (%s, %s, %s, %s);
        """
        db_service.execute_insert(insert_sql, (run_id, suite_name, "RUNNING", 1))

        try:
            client = await get_temporal_client()
            await client.start_workflow(
                EvaluationSuiteWorkflow.run,
                {
                    "run_id": run_id,
                    "suite_name": suite_name,
                    "samples": [custom_sample],
                },
                id=run_id,
                task_queue="ingestion-task-queue",
            )
            return {"run_id": run_id, "status": "RUNNING", "total_cases": 1, "mode": "TEMPORAL"}
        except Exception as e:
            logger.warning(f"Could not trigger Temporal for custom query: {e}. Executing inline fallback.")
            from src.app.temporal.eval_activities import run_single_evaluation_activity, save_eval_run_activity

            async def run_inline():
                res = await run_single_evaluation_activity(custom_sample)
                summary = {
                    "run_id": run_id,
                    "suite_name": suite_name,
                    "status": "COMPLETED",
                    "results": [res],
                }
                await save_eval_run_activity(summary)

            import asyncio
            asyncio.create_task(run_inline())
            return {"run_id": run_id, "status": "RUNNING", "total_cases": 1, "mode": "ASYNC_FALLBACK"}

    def list_eval_runs(self) -> List[Dict[str, Any]]:
        """Fetches all evaluation runs from database."""
        db_service.ensure_chat_tables()
        sql = "SELECT * FROM eval_suite_run ORDER BY created_at DESC LIMIT 50;"
        rows = db_service.execute_query(sql)
        runs = []
        for r in rows:
            runs.append({
                "id": r["id"],
                "suite_name": r["suite_name"],
                "faithfulness_avg": round(float(r.get("faithfulness_avg") or 0.0) * 100, 1),
                "relevance_avg": round(float(r.get("relevance_avg") or 0.0) * 100, 1),
                "context_precision_avg": round(float(r.get("context_precision_avg") or 0.0) * 100, 1),
                "router_accuracy_avg": round(float(r.get("router_accuracy_avg") or 0.0) * 100, 1),
                "hallucination_rate": round(float(r.get("hallucination_rate") or 0.0) * 100, 1),
                "status": r["status"],
                "total_cases": r["total_cases"],
                "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
            })
        return runs

    def get_eval_run_details(self, run_id: str) -> Dict[str, Any]:
        """Fetches run summary and individual test case results for a given run."""
        db_service.ensure_chat_tables()
        run_sql = "SELECT * FROM eval_suite_run WHERE id = %s;"
        run_rows = db_service.execute_query(run_sql, (run_id,))
        if not run_rows:
            return {}

        run_data = run_rows[0]
        results_sql = "SELECT * FROM eval_result WHERE run_id = %s ORDER BY created_at ASC;"
        result_rows = db_service.execute_query(results_sql, (run_id,))

        detailed_results = []
        for r in result_rows:
            contexts = r["retrieved_contexts"]
            if isinstance(contexts, str):
                try:
                    contexts = json.loads(contexts)
                except Exception:
                    contexts = [contexts]

            detailed_results.append({
                "id": r["id"],
                "testcase_id": r["testcase_id"],
                "category": r["category"],
                "query": r["query"],
                "ground_truth": r["ground_truth"],
                "expected_route": r["expected_route"],
                "actual_route": r["actual_route"],
                "retrieved_contexts": contexts,
                "generated_answer": r["generated_answer"],
                "faithfulness_score": round(float(r.get("faithfulness_score") or 0.0) * 100, 1),
                "relevance_score": round(float(r.get("relevance_score") or 0.0) * 100, 1),
                "hallucination_flag": bool(r.get("hallucination_flag")),
                "judge_rationale": r["judge_rationale"],
            })

        return {
            "id": run_data["id"],
            "suite_name": run_data["suite_name"],
            "faithfulness_avg": round(float(run_data.get("faithfulness_avg") or 0.0) * 100, 1),
            "relevance_avg": round(float(run_data.get("relevance_avg") or 0.0) * 100, 1),
            "context_precision_avg": round(float(run_data.get("context_precision_avg") or 0.0) * 100, 1),
            "router_accuracy_avg": round(float(run_data.get("router_accuracy_avg") or 0.0) * 100, 1),
            "hallucination_rate": round(float(run_data.get("hallucination_rate") or 0.0) * 100, 1),
            "status": run_data["status"],
            "total_cases": run_data["total_cases"],
            "created_at": run_data["created_at"].isoformat() if hasattr(run_data["created_at"], "isoformat") else str(run_data["created_at"]),
            "results": detailed_results,
        }


eval_service = EvalService()
