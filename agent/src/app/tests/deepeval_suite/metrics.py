"""
DeepEval Metrics Suite
Contains the 4 specific metric definitions requested for the customer agent:
1. Faithfulness Metric
2. Answer Relevancy Metric
3. Contextual Precision & Contextual Recall Metrics
4. Tool Correctness (Agent / Tool) Metric
"""

from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ToolCorrectnessMetric,
)

# 1. Faithfulness Metric (Ensures answer is grounded in retrieved context)
faithfulness_metric = FaithfulnessMetric(
    threshold=0.7,
    include_reason=True
)

# 2. Answer Relevancy Metric (Ensures answer directly addresses the prompt)
answer_relevancy_metric = AnswerRelevancyMetric(
    threshold=0.7,
    include_reason=True
)

# 3. Contextual Precision & Recall Metrics (Evaluates search/retrieval quality)
contextual_precision_metric = ContextualPrecisionMetric(
    threshold=0.7,
    include_reason=True
)

contextual_recall_metric = ContextualRecallMetric(
    threshold=0.7,
    include_reason=True
)

# 4. Agent / Tool Correctness Metric (Evaluates agent tool selection and calls)
tool_correctness_metric = ToolCorrectnessMetric(
    threshold=0.7,
    include_reason=True
)

# Bundled list of all 4 requested metric suites for single-turn RAG & Tool testing
TARGET_DEEPEVAL_METRICS = [
    faithfulness_metric,
    answer_relevancy_metric,
    contextual_precision_metric,
    contextual_recall_metric,
    tool_correctness_metric,
]
