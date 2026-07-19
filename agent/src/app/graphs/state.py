from typing import Annotated, TypedDict, Optional
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    next: str
    user_id: str
    pending_action_details: Optional[dict]
