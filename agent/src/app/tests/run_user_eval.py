import asyncio
import json
import sys
import os

# Add agent root to sys.path
agent_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if agent_root not in sys.path:
    sys.path.insert(0, agent_root)


from langchain_core.messages import HumanMessage
from deepeval.test_case import LLMTestCase, ToolCall
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ToolCorrectnessMetric,
)

from src.app.graphs.graph import agent_graph
from src.app.services.deepeval_server_evaluator import extract_eval_data_from_state

async def main():
    user_query = "what are the exact micro nutrients in Horsa-550X-Turbo ? and in trisan gold ?"
    user_id = "JxEyCUaqEOQ6t3cCAIEJ3I23aZS89w9Y"

    print("=" * 80)
    print(f"RUNNING AGENT WITH USER QUERY:")
    print(f"User ID: {user_id}")
    print(f"Query: {user_query}")
    print("=" * 80)

    initial_state = {
        "messages": [HumanMessage(content=user_query)],
        "user_id": user_id,
        "user_profile": {"semantic_facts": [], "episodic_summaries": []},
        "internal_facts": [],
        "action_type": None,
        "pending_action_details": None,
    }
    config = {"configurable": {"thread_id": f"eval-user-{user_id}"}}

    # 1. Execute Agent Graph
    final_state = await agent_graph.ainvoke(initial_state, config)

    # 2. Extract Response
    assistant_msgs = [m.content for m in final_state["messages"] if m.type == "ai"]
    agent_reply = assistant_msgs[-1] if assistant_msgs else "No reply generated."

    print("\n--- AGENT RESPONSE ---")
    print(agent_reply)
    print("----------------------\n")

    # 3. Extract DeepEval Context & Tools
    eval_data = extract_eval_data_from_state(user_query, agent_reply, final_state)
    
    print("--- EXTRACTED EVAL DATA ---")
    print(f"Retrieved Contexts Count: {len(eval_data['retrieved_contexts'])}")
    print(f"Tools Called: {[t.name for t in eval_data['tools_called']]}")
    print("---------------------------\n")

    # 4. Construct LLMTestCase
    tools_called_list = eval_data["tools_called"] if eval_data["tools_called"] else []
    expected_tools_list = [ToolCall(name="rag_agent", description="Invoked rag_agent specialist workflow")]

    test_case = LLMTestCase(
        input=user_query,
        actual_output=agent_reply,
        expected_output=agent_reply,
        retrieval_context=eval_data["retrieved_contexts"],
        tools_called=tools_called_list,
        expected_tools=expected_tools_list
    )

    # 5. Define the 5 Metrics
    faithfulness = FaithfulnessMetric(threshold=0.7, include_reason=True)
    answer_relevancy = AnswerRelevancyMetric(threshold=0.7, include_reason=True)
    context_precision = ContextualPrecisionMetric(threshold=0.7, include_reason=True)
    context_recall = ContextualRecallMetric(threshold=0.7, include_reason=True)
    tool_correctness = ToolCorrectnessMetric(threshold=0.7, include_reason=True)

    metrics = [
        ("Faithfulness", faithfulness),
        ("Answer Relevancy", answer_relevancy),
        ("Contextual Precision", context_precision),
        ("Contextual Recall", context_recall),
        ("Tool Correctness", tool_correctness),
    ]

    print("=" * 80)
    print("EVALUATING DEEPEVAL METRICS LIVE...")
    print("=" * 80)

    results = {}
    for name, metric in metrics:
        try:
            print(f"Measuring {name}...")
            metric.measure(test_case)
            results[name] = {
                "score": round(metric.score, 4) if metric.score is not None else 0.0,
                "passed": metric.is_successful(),
                "reason": getattr(metric, "reason", "N/A")
            }
        except Exception as e:
            print(f"Error measuring {name}: {e}")
            results[name] = {
                "score": 0.0,
                "passed": False,
                "reason": f"Error during metric calculation: {str(e)}"
            }

    print("\n" + "=" * 80)
    print("FINAL DEEPEVAL SCORES FOR USER QUERY")
    print("=" * 80)
    for name, res in results.items():
        status = "PASSED" if res["passed"] else "FAILED"
        print(f"[{status}] {name:22s} | Score: {res['score']:.4f}")
        if res["reason"] and res["reason"] != "N/A":
            print(f"   Reason: {res['reason']}")
        print("-" * 80)

if __name__ == "__main__":
    asyncio.run(main())
