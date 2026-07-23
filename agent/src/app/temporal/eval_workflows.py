from datetime import timedelta
from typing import Dict, Any, List
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.app.temporal.eval_activities import (
        run_single_evaluation_activity,
        save_eval_run_activity,
    )


@workflow.defn
class EvaluationSuiteWorkflow:
    @workflow.run
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs full benchmark suite across golden samples.
        input_data expected keys: 'run_id', 'suite_name', 'samples'
        """
        run_id = input_data["run_id"]
        suite_name = input_data.get("suite_name", "Golden Set Benchmark")
        samples: List[Dict[str, Any]] = input_data.get("samples", [])

        results = []
        for sample in samples:
            res = await workflow.execute_activity(
                run_single_evaluation_activity,
                sample,
                start_to_close_timeout=timedelta(seconds=120),
            )
            results.append(res)

        summary = {
            "run_id": run_id,
            "suite_name": suite_name,
            "status": "COMPLETED",
            "results": results,
        }

        saved_id = await workflow.execute_activity(
            save_eval_run_activity,
            summary,
            start_to_close_timeout=timedelta(seconds=60),
        )

        return {"run_id": saved_id, "status": "COMPLETED", "total_evaluated": len(results)}
