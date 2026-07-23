import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from src.app.services.eval_service import eval_service

logger = logging.getLogger("EvaluationEndpoints")

router = APIRouter(prefix="/eval", tags=["evaluation"])


class TriggerEvalRequest(BaseModel):
    suite_name: str = "Quick Benchmark"
    sample_count: int = 2


class TriggerCustomEvalRequest(BaseModel):
    query: str
    ground_truth: str = ""
    expected_route: str = "RAG_SEARCH"


@router.post("/runs")
async def trigger_eval_run(req: TriggerEvalRequest = TriggerEvalRequest()):
    """Triggers a quick benchmark run (default 2 random samples to save API tokens)."""
    try:
        res = await eval_service.trigger_eval_run(suite_name=req.suite_name, sample_count=req.sample_count)
        return res
    except Exception as e:
        logger.error(f"Error triggering eval run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/custom")
async def trigger_custom_eval_query(req: TriggerCustomEvalRequest):
    """Triggers an evaluation background job for a single admin custom test question."""
    try:
        res = await eval_service.trigger_custom_eval_query(
            query=req.query,
            ground_truth=req.ground_truth,
            expected_route=req.expected_route,
        )
        return res
    except Exception as e:
        logger.error(f"Error triggering custom eval: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs")
async def list_eval_runs():
    """Lists all historical benchmark runs."""
    try:
        runs = eval_service.list_eval_runs()
        return {"runs": runs}
    except Exception as e:
        logger.error(f"Error fetching eval runs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}")
async def get_eval_run_details(run_id: str):
    """Fetches details and individual sample metrics for a specific benchmark run."""
    try:
        data = eval_service.get_eval_run_details(run_id)
        if not data:
            raise HTTPException(status_code=44, detail="Evaluation run not found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching run details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/testcases")
async def get_testcases():
    """Fetches golden testcases dataset."""
    try:
        testcases = eval_service.load_golden_set()
        return {"testcases": testcases, "total": len(testcases)}
    except Exception as e:
        logger.error(f"Error fetching testcases: {e}")
        raise HTTPException(status_code=500, detail=str(e))
