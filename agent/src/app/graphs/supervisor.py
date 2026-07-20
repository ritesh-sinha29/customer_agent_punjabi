import os
import json
import logging
from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END

from src.app.graphs.rag_agent import run_rag_agent
from src.app.tools.booking_tools import create_booking, get_booking_updates
from src.app.tools.query_tools import create_query, get_user_queries
from src.app.core.config import settings
from src.app.graphs.state import SupervisorState

logger = logging.getLogger("SupervisorAgent")

# Retrieve supervisor model names
model_name = os.getenv("SUPERVISOR_MODEL", "gpt-4.1-mini")
sub_agent_model = "gpt-4.1-mini"

# Supervisor main routing model (gpt-5.1)
llm = ChatOpenAI(model=model_name, temperature=0.3, api_key=settings.OPENAI_API_KEY)
# Sub-agent model (gpt-4.1-mini)
sub_agent_llm = ChatOpenAI(model=sub_agent_model, temperature=0.2, api_key=settings.OPENAI_API_KEY)

# Bind tools directly
booking_llm = sub_agent_llm.bind_tools([create_booking, get_booking_updates])
query_llm = sub_agent_llm.bind_tools([create_query, get_user_queries])


# -----------------------------------------------------------------------------
# Router Decision Model
# -----------------------------------------------------------------------------
class SupervisorDecision(BaseModel):
    action_type: str = Field(
        description="Next node to route to: 'RAG_SEARCH' (for questions about catalog products, milk yield, fat %, ingredients, dosage), 'BOOKING_NODE' (for ordering/booking products or checking booking history/updates), 'QUERY_NODE' (for creating support tickets/callbacks or checking user support tickets), or 'NONE' (greetings, standard chit-chat, general topics)."
    )
    reasoning: str = Field(description="Reasoning for decision.")


ROUTER_PROMPT = """
You are the Supervisor Decision Engine for Vrsa Agrotech (Animal Nutrition & Dairy Supplements).
Catalog: Horsa-550X-Turbo, TrioSan Gold, MaxaPro-DS Dairy, MaxaPro Liquid, Buffalo-Power 2X, Buffalo-F 1.5X.

Analyze the user's message and history to classify the next action:
1. Product details/ingredients, dosage, animal species recommendation, milk fat yield -> action_type = "RAG_SEARCH" (routes to rag_agent)
2. Place a product order/booking, check order/booking updates/history -> action_type = "BOOKING_NODE" (routes to booking_node)
3. Create a support ticket/query/callback request, check existing support tickets -> action_type = "QUERY_NODE" (routes to query_node)
4. Greetings, general chit-chat, or general sales discussion -> action_type = "NONE" (routes directly to sales agent)
"""


async def supervisor_router(state: SupervisorState) -> Dict[str, Any]:
    """Decides if we route to RAG Sub-Agent, Booking Node, Query Node, or Supervisor Sales Agent."""
    messages = state.get("messages", [])

    try:
        structured_llm = llm.with_structured_output(SupervisorDecision)
        decision: SupervisorDecision = await structured_llm.ainvoke([SystemMessage(content=ROUTER_PROMPT)] + messages)
        
        if decision.action_type == "RAG_SEARCH":
            next_node = "rag_agent"
        elif decision.action_type == "BOOKING_NODE":
            next_node = "booking_node"
        elif decision.action_type == "QUERY_NODE":
            next_node = "query_node"
        else:
            next_node = "supervisor_sales_agent"

        return {
            "next": next_node,
            "action_type": decision.action_type
        }
    except Exception as e:
        logger.error(f"Router error: {e}")
        return {"next": "supervisor_sales_agent", "action_type": "NONE"}


# -----------------------------------------------------------------------------
# 1. Booking Agent Node (Invokes LLM with booking tools)
# -----------------------------------------------------------------------------
async def booking_node(state: SupervisorState) -> Dict[str, Any]:
    """Runs the LLM bound with booking tools to decide if it should call a tool or chat."""
    messages = state.get("messages", [])
    user_id = state.get("user_id", "guest_user")
    
    system_prompt = (
        f"You are the Product Booking Assistant for Vrsa Agrotech.\n"
        f"Your active user_id: {user_id}\n"
        f"Always pass this user_id when calling any booking tool.\n"
        f"Use create_booking to place product orders (you can pass 1 or multiple items in the items list), or get_booking_updates to check history.\n"
        f"Do not ask the user for user_id, it is already provided above.\n"
        f"If you need details like product name or quantity, ask the user directly before calling the tool."
    )
    
    response = await booking_llm.ainvoke([SystemMessage(content=system_prompt)] + messages)
    
    if response.tool_calls:
        tool_call = response.tool_calls[0]
        tool_name = tool_call["name"]
        
        if tool_name == "create_booking":
            items = tool_call["args"].get("items", [])
            # Fallback if model passes product_name and qty at top-level
            if not items and "product_name" in tool_call["args"]:
                items = [{"product_name": tool_call["args"]["product_name"], "qty": tool_call["args"].get("qty", 1)}]
                
            product_names = ", ".join([i.get("product_name", "") for i in items if i.get("product_name")])
            quantities = ", ".join([f"{i.get('qty', 1)}x {i.get('product_name', '')}" for i in items if i.get("product_name")])
            
            pending_details = {
                "product_name": product_names or "Product Order",
                "quantity": quantities or "1",
                "items": items,
                "tool_call_id": tool_call["id"]
            }
            return {
                "messages": [response],
                "pending_action_details": pending_details,
                "next": "booking_agent"
            }
        elif tool_name == "get_booking_updates":
            return {
                "messages": [response],
                "next": "booking_read_agent"
            }
            
    return {
        "messages": [response],
        "next": END
    }


async def run_booking_agent(state: SupervisorState) -> Dict[str, Any]:
    """Executes create_booking tool call with HITL approval/rejection check."""
    pending_details = state.get("pending_action_details")
    messages = state.get("messages", [])
    user_id = state.get("user_id", "guest_user")
    
    last_msg = messages[-1]
    tool_call_id = None
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        tool_call_id = last_msg.tool_calls[0]["id"]
    elif pending_details and "tool_call_id" in pending_details:
        tool_call_id = pending_details["tool_call_id"]
        
    tool_call_id = tool_call_id or "unknown"
    
    if not pending_details:
        # Cancelled by user
        tool_msg = ToolMessage(
            content="❌ Booking creation cancelled by user.",
            tool_call_id=tool_call_id,
            name="create_booking"
        )
        return {
            "messages": [tool_msg],
            "pending_action_details": None,
            "next": "supervisor_sales_agent"
        }
        
    items = pending_details.get("items", [])
    
    try:
        result = create_booking.invoke({"user_id": user_id, "items": items})
        tool_msg = ToolMessage(
            content=str(result),
            tool_call_id=tool_call_id,
            name="create_booking"
        )
    except Exception as e:
        tool_msg = ToolMessage(
            content=f"❌ Failed to create booking: {str(e)}",
            tool_call_id=tool_call_id,
            name="create_booking"
        )
        
    return {
        "messages": [tool_msg],
        "pending_action_details": None,
        "next": "supervisor_sales_agent"
    }


async def run_booking_read_agent(state: SupervisorState) -> Dict[str, Any]:
    """Executes get_booking_updates read tool call directly."""
    messages = state.get("messages", [])
    user_id = state.get("user_id", "guest_user")
    
    last_msg = messages[-1]
    tool_call_id = last_msg.tool_calls[0]["id"] if hasattr(last_msg, "tool_calls") and last_msg.tool_calls else "unknown"
    
    try:
        result = get_booking_updates(user_id=user_id)
        tool_msg = ToolMessage(
            content=str(result),
            tool_call_id=tool_call_id,
            name="get_booking_updates"
        )
    except Exception as e:
        tool_msg = ToolMessage(
            content=f"❌ Failed to retrieve bookings: {str(e)}",
            tool_call_id=tool_call_id,
            name="get_booking_updates"
        )
        
    return {
        "messages": [tool_msg],
        "next": "supervisor_sales_agent"
    }


# -----------------------------------------------------------------------------
# 2. Query Agent Node (Invokes LLM with query tools)
# -----------------------------------------------------------------------------
async def query_node(state: SupervisorState) -> Dict[str, Any]:
    """Runs the LLM bound with query tools to decide if it should call a tool or chat."""
    messages = state.get("messages", [])
    user_id = state.get("user_id", "guest_user")
    
    system_prompt = (
        f"You are the Support Query Assistant for Vrsa Agrotech.\n"
        f"Your active user_id: {user_id}\n"
        f"Always pass this user_id when calling any query tool.\n"
        f"Use create_query to create support tickets, or get_user_queries to retrieve existing tickets.\n"
        f"Do not ask the user for user_id, it is already provided above.\n"
        f"If you need details like query title or description, ask the user directly before calling the tool."
    )
    
    response = await query_llm.ainvoke([SystemMessage(content=system_prompt)] + messages)
    
    if response.tool_calls:
        tool_call = response.tool_calls[0]
        tool_name = tool_call["name"]
        
        if tool_name == "create_query":
            pending_details = {
                "title": tool_call["args"].get("title"),
                "description": tool_call["args"].get("description"),
                "tool_call_id": tool_call["id"]
            }
            return {
                "messages": [response],
                "pending_action_details": pending_details,
                "next": "query_agent"
            }
        elif tool_name == "get_user_queries":
            return {
                "messages": [response],
                "next": "query_read_agent"
            }
            
    return {
        "messages": [response],
        "next": END
    }


async def run_query_agent(state: SupervisorState) -> Dict[str, Any]:
    """Executes create_query tool call with HITL approval/rejection check."""
    pending_details = state.get("pending_action_details")
    messages = state.get("messages", [])
    user_id = state.get("user_id", "guest_user")
    
    last_msg = messages[-1]
    tool_call_id = None
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        tool_call_id = last_msg.tool_calls[0]["id"]
    elif pending_details and "tool_call_id" in pending_details:
        tool_call_id = pending_details["tool_call_id"]
        
    if not pending_details:
        tool_msg = ToolMessage(
            content="❌ Support query creation cancelled by user.",
            tool_call_id=tool_call_id or "unknown",
            name="create_query"
        )
        return {
            "messages": [tool_msg],
            "pending_action_details": None,
            "next": "supervisor_sales_agent"
        }
        
    title = pending_details.get("title")
    desc = pending_details.get("description")
    
    try:
        result = create_query(user_id=user_id, title=title, description=desc)
        tool_msg = ToolMessage(
            content=str(result),
            tool_call_id=tool_call_id or "unknown",
            name="create_query"
        )
    except Exception as e:
        tool_msg = ToolMessage(
            content=f"❌ Failed to create support query: {str(e)}",
            tool_call_id=tool_call_id or "unknown",
            name="create_query"
        )
        
    return {
        "messages": [tool_msg],
        "pending_action_details": None,
        "next": "supervisor_sales_agent"
    }


async def run_query_read_agent(state: SupervisorState) -> Dict[str, Any]:
    """Executes get_user_queries read tool call directly."""
    messages = state.get("messages", [])
    user_id = state.get("user_id", "guest_user")
    
    last_msg = messages[-1]
    tool_call_id = last_msg.tool_calls[0]["id"] if hasattr(last_msg, "tool_calls") and last_msg.tool_calls else "unknown"
    
    try:
        result = get_user_queries(user_id=user_id)
        tool_msg = ToolMessage(
            content=str(result),
            tool_call_id=tool_call_id,
            name="get_user_queries"
        )
    except Exception as e:
        tool_msg = ToolMessage(
            content=f"❌ Failed to retrieve support queries: {str(e)}",
            tool_call_id=tool_call_id,
            name="get_user_queries"
        )
        
    return {
        "messages": [tool_msg],
        "next": "supervisor_sales_agent"
    }


# -----------------------------------------------------------------------------
# 3. Supervisor Sales Agent Node (Streams Final Answer to User)
# -----------------------------------------------------------------------------
SALES_PROMPT = """
You are Vrsa Agrotech's Lead Sales Expert.
Catalog: Horsa-550X-Turbo, TrioSan Gold, MaxaPro-DS Dairy, MaxaPro Liquid, Buffalo-Power 2X, Buffalo-F 1.5X.

MANDATE:
1. ALWAYS RESPOND IN ENGLISH.
2. Be an enthusiastic, expert sales agent. Make users confident to buy Vrsa Agrotech animal nutrition products.
3. Use the facts and tool outputs in messages history to provide a clear, final answer to the user.
4. Do NOT ask for village name, phone number, or other delivery details unless explicitly required by the tool or if you need to coordinate. (Keep the response focused and check if the tool result indicates a successful transaction/ticket).
5. If a tool was executed successfully, summarize the order or ticket details clearly (e.g. Booking ID, Ticket ID) and thank them.
6. If a tool was cancelled, inform them politely.
"""


async def supervisor_sales_agent(state: SupervisorState) -> Dict[str, Any]:
    """Generates the final response to the user in English."""
    messages = state.get("messages", [])
    facts = state.get("internal_facts", [])

    system_content = SALES_PROMPT
    if facts:
        facts_str = ""
        for item in facts:
            if "reranked_chunks" in item:
                facts_str += "\n[RAG Retrieved Product Facts]:\n" + "\n".join([f"- {c}" for c in item["reranked_chunks"]])
            elif "tool" in item:
                facts_str += f"\n[Sub-Agent Tool Result ({item.get('subagent')})]: {json.dumps(item)}"
        if facts_str:
            system_content += f"\n\n--- INTERNAL DATA FACTS ---\n{facts_str}"

    response = await sub_agent_llm.ainvoke([SystemMessage(content=system_content)] + messages)
    return {"messages": [response], "next": "__end__"}


# -----------------------------------------------------------------------------
# Compiled LangGraph Workflow
# -----------------------------------------------------------------------------
workflow = StateGraph(SupervisorState)
workflow.add_node("supervisor_router", supervisor_router)
workflow.add_node("rag_agent", run_rag_agent)
workflow.add_node("booking_node", booking_node)
workflow.add_node("booking_agent", run_booking_agent)
workflow.add_node("booking_read_agent", run_booking_read_agent)
workflow.add_node("query_node", query_node)
workflow.add_node("query_agent", run_query_agent)
workflow.add_node("query_read_agent", run_query_read_agent)
workflow.add_node("supervisor_sales_agent", supervisor_sales_agent)

workflow.set_entry_point("supervisor_router")


def route_next(state: SupervisorState) -> str:
    return state.get("next", "supervisor_sales_agent")


workflow.add_conditional_edges("supervisor_router", route_next, {
    "rag_agent": "rag_agent",
    "booking_node": "booking_node",
    "query_node": "query_node",
    "supervisor_sales_agent": "supervisor_sales_agent"
})

workflow.add_conditional_edges("booking_node", route_next, {
    "booking_agent": "booking_agent",
    "booking_read_agent": "booking_read_agent",
    "__end__": END
})

workflow.add_conditional_edges("query_node", route_next, {
    "query_agent": "query_agent",
    "query_read_agent": "query_read_agent",
    "__end__": END
})

workflow.add_edge("rag_agent", "supervisor_sales_agent")
workflow.add_edge("booking_agent", "supervisor_sales_agent")
workflow.add_edge("booking_read_agent", "supervisor_sales_agent")
workflow.add_edge("query_agent", "supervisor_sales_agent")
workflow.add_edge("query_read_agent", "supervisor_sales_agent")
workflow.add_edge("supervisor_sales_agent", END)

from langgraph.checkpoint.memory import MemorySaver
from src.app.graphs.checkpointer import get_redis_checkpointer

try:
    checkpointer = get_redis_checkpointer()
    logger.info("Using Upstash Redis checkpointer for Supervisor Agent Graph.")
except Exception as e:
    logger.warning(f"Upstash Redis checkpointer initialization failed ({e}). Falling back to MemorySaver.")
    checkpointer = MemorySaver()

agent_graph = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["booking_agent", "query_agent"]
)
logger.info("Supervisor Agent Graph compiled successfully!")
