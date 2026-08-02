"""
DeepEval Pytest Suite for Customer Agent.

Tests real agent responses against the 4 requested DeepEval metrics:
1. Faithfulness Metric
2. Answer Relevancy Metric
3. Contextual Precision & Recall Metrics
4. Tool Correctness (Agent / Tool Metric)
"""

import asyncio
import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase, ToolCall
from langchain_core.messages import HumanMessage

from src.app.graphs.graph import agent_graph
from src.app.services.deepeval_server_evaluator import extract_eval_data_from_state
from src.app.tests.deepeval_suite.metrics import (
    faithfulness_metric,
    answer_relevancy_metric,
    contextual_precision_metric,
    contextual_recall_metric,
    tool_correctness_metric,
)


@pytest.mark.asyncio
async def test_live_agent_rag_metrics():
    """
    Executes real agent graph for product dosage query, extracts actual retrieved context,
    and evaluates Faithfulness, Answer Relevancy, Context Precision & Recall.
    """
    query = "What is the recommended daily dosage of TrioSan Gold?"
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "user_id": "eval_test_user",
        "user_profile": {"semantic_facts": [], "episodic_summaries": []},
        "internal_facts": [],
        "action_type": None,
        "pending_action_details": None,
    }
    config = {"configurable": {"thread_id": "deepeval-test-thread"}}

    # Execute real agent graph
    final_state = await agent_graph.ainvoke(initial_state, config)

    # Extract final response message
    assistant_msgs = [m.content for m in final_state["messages"] if m.type == "ai"]
    reply = assistant_msgs[-1] if assistant_msgs else ""

    # Extract evaluation data
    eval_data = extract_eval_data_from_state(query, reply, final_state)

    test_case = LLMTestCase(
        input=query,
        actual_output=reply,
        expected_output="TrioSan Gold dosage is 50–100 g per head per day or 3–5 kg per metric tonne of feed.",
        retrieved_context=eval_data["retrieved_contexts"],
    )

    # Assert test against the 4 RAG quality metrics
    assert_test(
        test_case,
        [
            faithfulness_metric,
            answer_relevancy_metric,
            contextual_precision_metric,
            contextual_recall_metric,
        ],
    )


@pytest.mark.asyncio
async def test_live_agent_tool_correctness():
    """
    Executes real agent graph for documentation lookup and evaluates Tool Correctness.
    """
    query = "Find product information for MaxaPro Liquid."
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "user_id": "eval_test_user",
        "user_profile": {"semantic_facts": [], "episodic_summaries": []},
        "internal_facts": [],
        "action_type": None,
        "pending_action_details": None,
    }
    config = {"configurable": {"thread_id": "deepeval-tool-test-thread"}}

    final_state = await agent_graph.ainvoke(initial_state, config)

    assistant_msgs = [m.content for m in final_state["messages"] if m.type == "ai"]
    reply = assistant_msgs[-1] if assistant_msgs else ""

    eval_data = extract_eval_data_from_state(query, reply, final_state)

    test_case = LLMTestCase(
        input=query,
        actual_output=reply,
        tools_called=eval_data["tools_called"] if eval_data["tools_called"] else None,
        expected_tools=[
            ToolCall(name="rag_agent", description="Invoked rag_agent specialist workflow")
        ],
    )

    assert_test(test_case, [tool_correctness_metric])
