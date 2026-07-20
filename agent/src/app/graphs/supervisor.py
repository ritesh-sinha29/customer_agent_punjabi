import os
import json
import logging
from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

from src.app.graphs.rag_agent import run_rag_agent
from src.app.tools.booking_tools import create_booking, get_booking_updates, get_canonical_product_name
from src.app.tools.query_tools import create_query, get_user_queries
from src.app.core.config import settings
from src.app.graphs.state import SupervisorState

logger = logging.getLogger("SupervisorAgent")

llm = ChatOpenAI(model=os.getenv("SUPERVISOR_MODEL", "gpt-5.1"), temperature=0.3, api_key=settings.OPENAI_API_KEY)


# -----------------------------------------------------------------------------
# Router Decision Model
# -----------------------------------------------------------------------------
class SupervisorDecision(BaseModel):
    action_type: str = Field(
        description="Action to take: 'RAG_SEARCH' (call RAG sub-agent), 'BOOK_PRODUCT' (create order), 'GET_BOOKINGS' (check order status), 'BOOK_QUERY' (create support ticket), 'GET_QUERIES' (check user queries), or 'NONE' (direct sales pitch)."
    )
    product_name: str = Field(
        default="",
        description="Product name if ordering (e.g. 'MaxaPro-DS Dairy', 'Horsa-550X-Turbo', 'TrioSan Gold', 'Buffalo-Power 2X')."
    )
    quantity: int = Field(default=1, description="Quantity if ordering product.")
    query_title: str = Field(default="", description="Title for support query/callback request.")
    query_description: str = Field(default="", description="Detailed description for support query/callback.")
    reasoning: str = Field(description="Reasoning for decision.")


ROUTER_PROMPT = """
You are the Supervisor Decision Engine for Vrsa Agrotech (Animal Nutrition & Dairy Supplements).
Catalog: Horsa-550X-Turbo, TrioSan Gold, MaxaPro-DS Dairy, MaxaPro Liquid, Buffalo-Power 2X, Buffalo-F 1.5X.

Analyze the user's message:
1. Product questions, milk yield, fat %, ingredients, dosage -> action_type = "RAG_SEARCH" (calls rag_agent)
2. Place product order -> action_type = "BOOK_PRODUCT" (calls booking_agent -> create_booking)
3. Check order history/status -> action_type = "GET_BOOKINGS" (calls booking_agent -> get_booking_updates)
4. Create support query/callback ticket -> action_type = "BOOK_QUERY" (calls query_agent -> create_query)
5. Check existing support queries -> action_type = "GET_QUERIES" (calls query_agent -> get_user_queries)
6. General conversation -> action_type = "NONE"
"""

async def supervisor_router(state: SupervisorState) -> Dict[str, Any]:
    """Decides if we route to RAG Sub-Agent, Booking Sub-Agent, Query Sub-Agent, or Supervisor Sales Agent."""
    messages = state.get("messages", [])

    try:
        structured_llm = llm.with_structured_output(SupervisorDecision)
        decision: SupervisorDecision = await structured_llm.ainvoke([SystemMessage(content=ROUTER_PROMPT)] + messages)
        
        pending_details = {
            "product_name": decision.product_name or "MaxaPro-DS Dairy",
            "qty": decision.quantity,
            "title": decision.query_title or "Official Callback Request",
            "description": decision.query_description or (messages[-1].content if messages else "User Inquiry")
        }

        if decision.action_type == "RAG_SEARCH":
            next_node = "rag_agent"
        elif decision.action_type in ["BOOK_PRODUCT", "GET_BOOKINGS"]:
            next_node = "booking_agent"
        elif decision.action_type in ["BOOK_QUERY", "GET_QUERIES"]:
            next_node = "query_agent"
        else:
            next_node = "supervisor_sales_agent"

        return {
            "next": next_node,
            "action_type": decision.action_type,
            "pending_action_details": pending_details
        }
    except Exception as e:
        logger.error(f"Router error: {e}")
        return {"next": "supervisor_sales_agent", "action_type": "NONE"}


# -----------------------------------------------------------------------------
# 1. Booking Sub-Agent (Handles create_booking & get_booking_updates)
# -----------------------------------------------------------------------------
async def run_booking_agent(state: SupervisorState) -> Dict[str, Any]:
    """Handles product order creation and order status checks in PostgreSQL."""
    action = state.get("action_type", "BOOK_PRODUCT")
    user_id = state.get("user_id", "guest_user")
    pending_details = state.get("pending_action_details", {}) or {}
    facts = list(state.get("internal_facts") or [])

    if action == "GET_BOOKINGS":
        try:
            records = get_booking_updates(user_id=user_id)
            facts.append({"subagent": "booking_agent", "tool": "get_booking_updates", "status": "success", "user_bookings": records})
        except Exception as e:
            facts.append({"subagent": "booking_agent", "tool": "get_booking_updates", "status": "error", "error": str(e)})
    else:
        # BOOK_PRODUCT
        raw_pname = pending_details.get("product_name", "MaxaPro-DS Dairy")
        try:
            pname = get_canonical_product_name(raw_pname)
        except Exception:
            pname = "MaxaPro-DS Dairy"
        qty = int(pending_details.get("qty", 1))
        
        try:
            rec = create_booking(user_id=user_id, product_name=pname, qty=qty)
            facts.append({"subagent": "booking_agent", "tool": "create_booking", "status": "success", "booking_id": rec.get("id"), "product": pname, "qty": qty})
        except Exception as e:
            facts.append({"subagent": "booking_agent", "tool": "create_booking", "status": "error", "error": str(e)})

    return {"internal_facts": facts, "next": "supervisor_sales_agent"}


# -----------------------------------------------------------------------------
# 2. Query Sub-Agent (Handles create_query & get_user_queries)
# -----------------------------------------------------------------------------
async def run_query_agent(state: SupervisorState) -> Dict[str, Any]:
    """Handles support ticket creation and user query lookups in PostgreSQL."""
    action = state.get("action_type", "BOOK_QUERY")
    user_id = state.get("user_id", "guest_user")
    pending_details = state.get("pending_action_details", {}) or {}
    facts = list(state.get("internal_facts") or [])

    if action == "GET_QUERIES":
        try:
            records = get_user_queries(user_id=user_id)
            facts.append({"subagent": "query_agent", "tool": "get_user_queries", "status": "success", "user_queries": records})
        except Exception as e:
            facts.append({"subagent": "query_agent", "tool": "get_user_queries", "status": "error", "error": str(e)})
    else:
        # BOOK_QUERY
        title = pending_details.get("title", "Official Callback Request")
        desc = pending_details.get("description", "User requested official support callback.")
        try:
            rec = create_query(user_id=user_id, title=title, description=desc)
            facts.append({"subagent": "query_agent", "tool": "create_query", "status": "success", "ticket_id": rec.get("id"), "title": title})
        except Exception as e:
            facts.append({"subagent": "query_agent", "tool": "create_query", "status": "error", "error": str(e)})

    return {"internal_facts": facts, "next": "supervisor_sales_agent"}


# -----------------------------------------------------------------------------
# 3. Supervisor Sales Agent Node (Streams Final Answer to User)
# -----------------------------------------------------------------------------
SALES_PROMPT = """
You are Vrsa Agrotech's Lead Sales Expert.
Catalog: Horsa-550X-Turbo, TrioSan Gold, MaxaPro-DS Dairy, MaxaPro Liquid, Buffalo-Power 2X, Buffalo-F 1.5X.

MANDATE:
1. ALWAYS RESPOND IN ENGLISH.
2. Be an enthusiastic, expert sales agent. Make users confident to buy Vrsa Agrotech animal nutrition products.
3. Listen to their dairy/livestock needs (milk yield, fat %, animal stamina), explain specifically why our product is best.
4. Seamlessly use internal facts & tool results provided below.
5. End with a strong, clear call-to-action (ask to place order or confirm callback details).
"""

async def supervisor_sales_agent(state: SupervisorState) -> Dict[str, Any]:
    """Generates the final streaming response to the user in English."""
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

    response = await llm.ainvoke([SystemMessage(content=system_content)] + messages)
    return {"messages": [response], "next": "__end__"}


# -----------------------------------------------------------------------------
# Compiled LangGraph Workflow
# -----------------------------------------------------------------------------
workflow = StateGraph(SupervisorState)
workflow.add_node("supervisor_router", supervisor_router)
workflow.add_node("rag_agent", run_rag_agent)
workflow.add_node("booking_agent", run_booking_agent)
workflow.add_node("query_agent", run_query_agent)
workflow.add_node("supervisor_sales_agent", supervisor_sales_agent)

workflow.set_entry_point("supervisor_router")

def route_next(state: SupervisorState) -> str:
    return state.get("next", "supervisor_sales_agent")

workflow.add_conditional_edges("supervisor_router", route_next, {
    "rag_agent": "rag_agent",
    "booking_agent": "booking_agent",
    "query_agent": "query_agent",
    "supervisor_sales_agent": "supervisor_sales_agent"
})
workflow.add_edge("rag_agent", "supervisor_sales_agent")
workflow.add_edge("booking_agent", "supervisor_sales_agent")
workflow.add_edge("query_agent", "supervisor_sales_agent")
workflow.add_edge("supervisor_sales_agent", END)

from langgraph.checkpoint.memory import MemorySaver
from src.app.graphs.checkpointer import get_redis_checkpointer

try:
    checkpointer = get_redis_checkpointer()
    logger.info("Using Upstash Redis checkpointer for Supervisor Agent Graph.")
except Exception as e:
    logger.warning(f"Upstash Redis checkpointer initialization failed ({e}). Falling back to MemorySaver.")
    checkpointer = MemorySaver()

agent_graph = workflow.compile(checkpointer=checkpointer)
logger.info("Supervisor Agent Graph with Booking & Query Sub-Agents compiled successfully!")
