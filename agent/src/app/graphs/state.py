from typing import Annotated, TypedDict, Optional, List, Dict, Any
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class SupervisorState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    next: str  # Routing tag: "rag_agent", "booking_node", "query_node", "deep_memory_node", "supervisor_sales_agent"
    user_id: str
    action_type: Optional[str]  # "RAG_SEARCH", "BOOKING_NODE", "QUERY_NODE", "DEEP_MEMORY", "NONE"
    internal_facts: Optional[List[Dict[str, Any]]]  # Facts returned silently by sub-agents
    pending_action_details: Optional[dict]  # HITL approval details for bookings/queries
    user_profile: Optional[dict]  # Slim core memory context (recent facts + latest summary)
