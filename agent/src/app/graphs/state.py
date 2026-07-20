from typing import Annotated, TypedDict, Optional, List, Dict, Any
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class SupervisorState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    next: str  # Routing tag: "product_expert", "booking_agent", "__end__" / "FINISH"
    user_id: str
    action_type: Optional[str]  # "SEARCH_PRODUCT", "BOOK_PRODUCT", "BOOK_QUERY", None
    internal_facts: Optional[List[Dict[str, Any]]]  # Facts returned silently by sub-agents
    pending_action_details: Optional[dict]  # HITL approval details for bookings/queries
    user_profile: Optional[dict]  # Placeholder for user metadata / future memory
