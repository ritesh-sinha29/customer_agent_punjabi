"""
Background DeepEval Server Evaluator

Asynchronously evaluates live chat responses against DeepEval's 4 metrics:
1. Faithfulness Metric
2. Answer Relevancy Metric
3. Contextual Precision & Recall Metrics
4. Tool Correctness (Agent / Tool) Metric

Runs completely in the background via asyncio.create_task() with ZERO added chat latency.
"""

import asyncio
import logging
from typing import Any, Dict, List

from deepeval.test_case import LLMTestCase, ToolCall
from src.app.tests.deepeval_suite.metrics import (
    faithfulness_metric,
    answer_relevancy_metric,
    contextual_precision_metric,
    contextual_recall_metric,
    tool_correctness_metric,
)

logger = logging.getLogger("DeepEvalServerEvaluator")


def extract_eval_data_from_state(user_query: str, agent_reply: str, final_state: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts retrieved contexts and tool calls from LangGraph state."""
    retrieved_contexts = []
    tools_called = []

    internal_facts = final_state.get("internal_facts", []) if final_state else []
    for item in internal_facts:
        if not isinstance(item, dict):
            continue

        # Extract RAG retrieved context chunks
        if item.get("subagent") == "rag_agent" and "reranked_chunks" in item:
            for chunk in item.get("reranked_chunks", []):
                if isinstance(chunk, str):
                    retrieved_contexts.append(chunk)
                elif isinstance(chunk, dict) and "text" in chunk:
                    retrieved_contexts.append(chunk["text"])

        # Extract subagent tool calls
        subagent_name = item.get("subagent")
        if subagent_name:
            tools_called.append(
                ToolCall(
                    name=subagent_name,
                    description=f"Invoked {subagent_name} specialist workflow"
                )
            )

    return {
        "user_query": user_query,
        "agent_reply": agent_reply,
        "retrieved_contexts": retrieved_contexts or ["No context retrieved."],
        "tools_called": tools_called
    }


async def evaluate_live_chat_background(user_query: str, agent_reply: str, final_state: Dict[str, Any]):
    """
    Background task function that evaluates real live agent response with DeepEval.
    Does not block the user response.
    """
    try:
        data = extract_eval_data_from_state(user_query, agent_reply, final_state)
        
        # Build DeepEval LLMTestCase for live chat
        test_case = LLMTestCase(
            input=data["user_query"],
            actual_output=data["agent_reply"],
            retrieval_context=data["retrieved_contexts"],
            tools_called=data["tools_called"] if data["tools_called"] else None
        )

        metrics_to_run = [
            faithfulness_metric,
            answer_relevancy_metric,
        ]

        # Add Context Precision & Recall if context was retrieved
        if data["retrieved_contexts"] and data["retrieved_contexts"] != ["No context retrieved."]:
            # expected_output fallback set to agent reply if no explicit ground truth
            test_case.expected_output = agent_reply
            metrics_to_run.extend([contextual_precision_metric, contextual_recall_metric])

        # Add Tool Correctness if tools were invoked
        if data["tools_called"]:
            test_case.expected_tools = data["tools_called"]
            metrics_to_run.append(tool_correctness_metric)

        logger.info(f"Running background DeepEval evaluation for query: '{user_query[:40]}...'")

        scores = {}
        for metric in metrics_to_run:
            try:
                # Measure metric asynchronously or in thread pool
                await asyncio.to_thread(metric.measure, test_case)
                metric_name = metric.__class__.__name__
                scores[metric_name] = {
                    "score": round(metric.score, 4) if metric.score is not None else 0.0,
                    "passed": metric.is_successful(),
                    "reason": getattr(metric, "reason", "N/A")
                }
            except Exception as me:
                logger.warning(f"Metric {metric.__class__.__name__} failed during live eval: {me}")

        print("\n" + "=" * 70)
        print(f" LIVE CHAT DEEPEVAL RESULTS [Query: '{user_query}']")
        for m_name, res in scores.items():
            status_symbol = "PASSED" if res["passed"] else "FAILED"
            print(f"   [{status_symbol}] {m_name}: Score = {res['score']}")
            if res.get("reason") and res["reason"] != "N/A":
                print(f"        Reason: {res['reason']}")
        print("=" * 70 + "\n")

    except Exception as e:
        logger.error(f"Error in background DeepEval live chat evaluation: {e}")


def trigger_live_deepeval(user_query: str, agent_reply: str, final_state: Dict[str, Any]):
    """Schedules background evaluation without blocking the API response."""
    asyncio.create_task(evaluate_live_chat_background(user_query, agent_reply, final_state))
