import os
import json
import logging
import re
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.types import Send

from src.app.graphs.rag_agent import run_rag_agent
from src.app.graphs.web_search_agent import web_search_fanout, route_web_search_fanout, web_search_worker, critic_agent
from src.app.tools.booking_tools import create_booking, get_booking_updates
from src.app.tools.query_tools import create_query, get_user_queries
from src.app.tools.web_search_tools import execute_tavily_search
from src.app.core.config import settings
from src.app.graphs.state import SupervisorState
from src.app.services.retrieval_service import retrieval_service
from src.app.services.db_service import db_service
from src.app.core.circuit_breaker import llm_circuit_breaker

logger = logging.getLogger("SupervisorAgent")

# (Commented out - replaced gpt-4.1-mini router with ultra-fast Groq model)
# model_name = os.getenv("SUPERVISOR_MODEL", "gpt-4.1-mini")
# llm = ChatOpenAI(model=model_name, temperature=0.3, api_key=settings.OPENAI_API_KEY)

# Supervisor main routing model using Groq (openai/gpt-oss-20b) for ms latency
groq_router_model = os.getenv("GROQ_ROUTER_MODEL", getattr(settings, "GROQ_ROUTER_MODEL", "openai/gpt-oss-20b"))
groq_key = getattr(settings, "GROQ_API_KEY", os.getenv("GROQ_API_KEY", "")).strip('"')

if groq_key:
    logger.info(f"[Supervisor] Initializing Groq router with model: {groq_router_model}")
    llm = ChatOpenAI(
        model=groq_router_model,
        temperature=0.0,
        api_key=groq_key,
        base_url="https://api.groq.com/openai/v1"
    )
else:
    logger.warning("[Supervisor] GROQ_API_KEY not found. Falling back to OpenAI router model.")
    model_name = os.getenv("SUPERVISOR_MODEL", "gpt-4.1-mini")
    llm = ChatOpenAI(model=model_name, temperature=0.3, api_key=settings.OPENAI_API_KEY)

sub_agent_model = "gpt-4.1-mini"
# Sub-agent model (gpt-4.1-mini)
sub_agent_llm = ChatOpenAI(model=sub_agent_model, temperature=0.2, api_key=settings.OPENAI_API_KEY)

# Bind tools directly
booking_llm = sub_agent_llm.bind_tools([create_booking, get_booking_updates])
query_llm = sub_agent_llm.bind_tools([create_query, get_user_queries])


# -----------------------------------------------------------------------------
# Router Decision Model
# -----------------------------------------------------------------------------
# Router Decision Model (Multi-Action Parallel Fan-Out Support)
# -----------------------------------------------------------------------------
class SupervisorDecision(BaseModel):
    actions: List[str] = Field(
        description="List of sub-agent actions to trigger in parallel (can select 1 or multiple): 'RAG_SEARCH' (for catalog products, dosage, ingredients, milk fat %), 'BOOKING_NODE' (for placing orders or checking booking status), 'QUERY_NODE' (for support tickets/callbacks), 'DEEP_MEMORY' (for past user history, past queries, memory, or profile facts), 'WEB_SEARCH' (for market prices, external news, scientific studies outside catalog), or 'NONE' (greetings, general topics)."
    )
    reasoning: str = Field(description="Reasoning for routing decision.")


ROUTER_PROMPT = """
You are the Supervisor Decision Engine for Vrsa Agrotech (Animal Nutrition & Dairy Supplements).
Catalog: Horsa-550X-Turbo, TrioSan Gold, MaxaPro-DS Dairy, MaxaPro Liquid, Buffalo-Power 2X, Buffalo-F 1.5X.

Analyze the user's message and context history to select ALL applicable actions to execute in parallel:
1. Product details/ingredients, dosage, animal species recommendation, milk fat yield -> include "RAG_SEARCH"
2. Place a product order/booking, check order/booking updates/history -> include "BOOKING_NODE"
3. Create a support ticket/query/callback request, check existing support tickets -> include "QUERY_NODE"
4. User asks about their past interactions, past queries, memory, stored farmer/cattle profile, previous recommendations -> include "DEEP_MEMORY"
5. General web queries, current raw milk or grain commodity prices, general livestock market news, or scientific studies outside internal catalog -> include "WEB_SEARCH"
6. Greetings, general chit-chat, or simple sales discussion -> include "NONE"

If a user request contains multiple intents (e.g. asking about past queries AND product nutrition sources AND market prices), select ALL corresponding actions in the actions list so they can execute in parallel.
"""


async def supervisor_router(state: SupervisorState) -> Dict[str, Any]:
    """Decides and triggers single or multiple sub-agents in parallel (RAG, Booking, Query, Deep Memory, Web Search)."""
    messages = state.get("messages", [])

    try:
        async def primary_call():
            structured_llm = llm.with_structured_output(SupervisorDecision, method="function_calling")
            return await structured_llm.ainvoke([SystemMessage(content=ROUTER_PROMPT)] + messages)

        async def fallback_call():
            fallback_llm = llm_circuit_breaker.get_fallback_llm()
            if fallback_llm:
                fallback_structured = fallback_llm.with_structured_output(SupervisorDecision, method="function_calling")
                return await fallback_structured.ainvoke([SystemMessage(content=ROUTER_PROMPT)] + messages)
            return await primary_call()

        decision: SupervisorDecision = await llm_circuit_breaker.execute(
            primary_call, fallback_call, context_name="Supervisor Router"
        )
        
        raw_actions = decision.actions if isinstance(decision.actions, list) else [decision.actions]
        next_nodes = []
        for act in raw_actions:
            if act == "RAG_SEARCH" and "rag_agent" not in next_nodes:
                next_nodes.append("rag_agent")
            elif act == "BOOKING_NODE" and "booking_node" not in next_nodes:
                next_nodes.append("booking_node")
            elif act == "QUERY_NODE" and "query_node" not in next_nodes:
                next_nodes.append("query_node")
            elif act == "DEEP_MEMORY" and "deep_memory_node" not in next_nodes:
                next_nodes.append("deep_memory_node")
            elif act == "WEB_SEARCH" and "web_search_fanout" not in next_nodes:
                next_nodes.append("web_search_fanout")

        if not next_nodes:
            next_nodes = ["supervisor_sales_agent"]

        logger.info(f"[SUPERVISOR ROUTER] Selected parallel sub-agents: {next_nodes} | Reasoning: {decision.reasoning}")

        return {
            "next": next_nodes if len(next_nodes) > 1 else next_nodes[0],
            "action_type": ", ".join(raw_actions)
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
    
    async def primary_booking_call():
        return await booking_llm.ainvoke([SystemMessage(content=system_prompt)] + messages)

    async def fallback_booking_call():
        fallback_llm = llm_circuit_breaker.get_fallback_llm()
        if fallback_llm:
            fallback_booking = fallback_llm.bind_tools([create_booking, get_booking_updates])
            return await fallback_booking.ainvoke([SystemMessage(content=system_prompt)] + messages)
        return await primary_booking_call()

    response = await llm_circuit_breaker.execute(
        primary_booking_call, fallback_booking_call, context_name="Booking Node"
    )
    
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
    
    async def primary_query_call():
        return await query_llm.ainvoke([SystemMessage(content=system_prompt)] + messages)

    async def fallback_query_call():
        fallback_llm = llm_circuit_breaker.get_fallback_llm()
        if fallback_llm:
            fallback_query = fallback_llm.bind_tools([create_query, get_user_queries])
            return await fallback_query.ainvoke([SystemMessage(content=system_prompt)] + messages)
        return await primary_query_call()

    response = await llm_circuit_breaker.execute(
        primary_query_call, fallback_query_call, context_name="Query Node"
    )
    
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
# 3. Deep Memory Node (Retrieves Detailed Historical User Memory on Demand)
# -----------------------------------------------------------------------------
async def deep_memory_node(state: SupervisorState) -> Dict[str, Any]:
    """
    Deep Memory Node for retrieving historical facts, past user preferences,
    and detailed memory stored in Pinecone (user_memory namespace) and PostgreSQL DB.
    Invoked when supervisor/router detects user asking about past history or profile details.
    """
    messages = state.get("messages", [])
    user_id = state.get("user_id", "guest_user")
    
    last_user_query = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_query = msg.content
            break
        elif isinstance(msg, dict) and msg.get("role") == "user":
            last_user_query = msg.get("content", "")
            break
            
    if not last_user_query:
        last_user_query = "user memory profile and cattle history"
        
    logger.info(f"[DEEP MEMORY NODE] Fetching deep memory context for user '{user_id}' query: '{last_user_query}'")

    relevant_snippets = []
    # 1. Semantic Search on Pinecone user_memory namespace
    try:
        matches = await retrieval_service.retrieve_parallel(
            queries=[last_user_query],
            top_k=5,
            namespace="user_memory",
            user_id=user_id,
            original_query=last_user_query
        )
        for match in matches:
            meta = match.get("metadata") or {}
            # Double safety guard: ensure vector belongs to the requesting user
            if meta.get("user_id") and meta.get("user_id") != user_id:
                continue
            text = meta.get("text") or meta.get("content")
            if text and text not in relevant_snippets:
                relevant_snippets.append(text)
    except Exception as e:
        logger.error(f"[DEEP MEMORY NODE] Pinecone retrieval error: {e}")

    # 2. Fetch full DB memory record for complete facts coverage
    all_facts = []
    all_summaries = []
    try:
        db_record = db_service.execute_query(
            "SELECT semantic_facts, episodic_summaries FROM user_memory WHERE user_id = %s",
            (user_id,)
        )
        if db_record:
            all_facts = db_record[0].get("semantic_facts") or []
            all_summaries = db_record[0].get("episodic_summaries") or []
    except Exception as dbe:
        logger.error(f"[DEEP MEMORY NODE] DB retrieval error: {dbe}")

    existing_facts = list(state.get("internal_facts") or [])
    payload = {
        "subagent": "deep_memory_node",
        "user_id": user_id,
        "query": last_user_query,
        "relevant_facts": relevant_snippets,
        "all_facts": all_facts,
        "summaries": all_summaries
    }
    existing_facts.append(payload)

    return {
        "internal_facts": existing_facts,
        "next": "supervisor_sales_agent"
    }


# -----------------------------------------------------------------------------
# 5. Supervisor Sales Agent Node (Streams Final Answer to User)
# -----------------------------------------------------------------------------
SALES_PROMPT = """
You are VRSA AGROTECH's Lead Animal Nutrition & Product Sales Specialist.
You speak with absolute human intelligence, warmth, authority, and deep domain expertise in dairy science, livestock health, and animal nutrition supplements.

CATALOG SUMMARY:
- Horsa-550X-Turbo: Ultra-potency performance & milk yield booster (chelated trace minerals, bypass protein, vitamins A/D3/E, probiotics).
- TrioSan Gold: Triple-action fat & SNF booster (calcium salts of bypass fats, liver stimulants; boosts fat up to 1.5%+).
- MaxaPro-DS Dairy: Comprehensive double-strength daily nutrition & digestive supplement for cows/buffaloes.
- MaxaPro Liquid: Fast-acting liquid mineral/vitamin suspension for post-calving recovery & appetite.
- Buffalo-Power 2X: Specialized double-power supplement for Murrah & indigenous buffalo fat & yield.
- Buffalo-F 1.5X: Target fat-enrichment formula (1.5X power) for buffalo milk density & fat %.

MANDATE & GROUNDING RULES:
--> Always ground product facts and recommendations using facts retrieved by the rag_agent sub-agent and catalog knowledge.
--> Always ground verified external web research using facts provided by the critic_agent.
--> Always leverage user history retrieved by the deep_memory_node whenever deeper context is needed to deliver a personalized response.
1. Grounded & Adequate Facts: ALWAYS ground product claims, ingredients, dosages, and species benefits directly in internal data facts and catalog knowledge.
2. Sales & Booking CTA: Recommend the optimal product based on farmer needs. Explain financial ROI and naturally invite them to book the order.
3. Integration: Seamlessly synthesize RAG retrieved facts, Critic Agent verified web facts, Deep Memory facts, and Tool execution results.

SUGGESTED ACTIONS MANDATE:
At the very end of your response, on a new line, provide exactly 1 to 3 relevant follow-up action suggestions for the user wrapped in XML tags like this:
<suggested_actions>
- Ask about product dosage
- Check TrioSan Gold pricing
- Book Horsa-550X-Turbo order
</suggested_actions>
"""


async def supervisor_sales_agent(state: SupervisorState) -> Dict[str, Any]:
    """Generates the final response to the user in English."""
    messages = state.get("messages", [])
    facts = state.get("internal_facts", [])
    user_profile = state.get("user_profile") or {}

    system_content = SALES_PROMPT

    # Inject user core memory context (recent facts + latest summary)
    memory_str = ""
    semantic_facts = user_profile.get("semantic_facts", [])
    if semantic_facts:
        memory_str += "\n[Recent Core Farmer Profile Facts]:\n" + "\n".join([f"- {f}" for f in semantic_facts])
    
    episodic_summaries = user_profile.get("episodic_summaries", [])
    if episodic_summaries:
        memory_str += f"\n[Latest Interaction Summary]:\n- {episodic_summaries[-1]}"
        
    if memory_str:
        system_content += f"\n\n--- SLIM CORE MEMORY CONTEXT ---\n{memory_str}"

    if facts:
        facts_str = ""
        for item in facts:
            if "reranked_chunks" in item:
                facts_str += "\n[RAG Retrieved Product Facts]:\n" + "\n".join([f"- {c}" for c in item["reranked_chunks"]])
            elif item.get("subagent") == "deep_memory_node":
                facts_str += "\n[Deep Historical Memory Retrieved]:\n"
                rel = item.get("relevant_facts", [])
                if rel:
                    facts_str += "Relevant Vector Memory:\n" + "\n".join([f"- {r}" for r in rel]) + "\n"
                all_f = item.get("all_facts", [])
                if all_f:
                    facts_str += "All Stored Profile Facts:\n" + "\n".join([f"- {f}" for f in all_f]) + "\n"
                sums = item.get("summaries", [])
                if sums:
                    facts_str += "Past Summaries:\n" + "\n".join([f"- {s}" for s in sums]) + "\n"
            elif item.get("subagent") == "critic_agent":
                facts_str += f"\n[Critic Agent Verified Web Facts]:\n{item.get('verified_web_facts')}\n"
                cits = item.get("citations", [])
                if cits:
                    facts_str += "Citations:\n" + "\n".join([f"- [{c.get('title')}]({c.get('url')})" for c in cits]) + "\n"
            elif "tool" in item:
                facts_str += f"\n[Sub-Agent Tool Result ({item.get('subagent')})]: {json.dumps(item)}"
            else:
                facts_str += f"\n[Sub-Agent Fact ({item.get('subagent')})]: {json.dumps(item)}"

        if facts_str:
            system_content += f"\n\n--- INTERNAL DATA FACTS ---\n{facts_str}"

    action_type = state.get("action_type", "NONE")

    # Dynamic Model Switcher: Use Groq (llm) for simple chit-chat/greetings (NONE & no facts) for ~200ms latency,
    # and OpenAI gpt-4.1-mini (sub_agent_llm) for complex domain synthesis (RAG, web search, tools).
    if action_type == "NONE" and not facts:
        target_sales_llm = llm
        model_name_log = getattr(target_sales_llm, "model", "groq")
        print(f"[SALES AGENT] LLM SELECTED: GROQ ({model_name_log}) [CHIT-CHAT GREETING]", flush=True)
        logger.info(f"[Supervisor Sales Agent] Routing to fast Groq model ({model_name_log}) for chit-chat greeting.")
    else:
        target_sales_llm = sub_agent_llm
        model_name_log = getattr(target_sales_llm, "model", "gpt-4.1-mini")
        print(f"[SALES AGENT] LLM SELECTED: OPENAI ({model_name_log}) [DOMAIN TASK]", flush=True)
        logger.info(f"[Supervisor Sales Agent] Routing to OpenAI model ({model_name_log}) for complex domain response.")

    async def primary_sales_call():
        return await target_sales_llm.ainvoke([SystemMessage(content=system_content)] + messages)

    async def fallback_sales_call():
        fallback_llm = llm_circuit_breaker.get_fallback_llm()
        if fallback_llm:
            return await fallback_llm.ainvoke([SystemMessage(content=system_content)] + messages)
        return await primary_sales_call()

    response = await llm_circuit_breaker.execute(
        primary_sales_call, fallback_sales_call, context_name="Supervisor Sales Agent"
    )

    # Parse suggested_actions if present in response
    suggested_actions = []
    if response and hasattr(response, "content") and isinstance(response.content, str):
        match = re.search(r"<suggested_actions>\s*(.*?)\s*</suggested_actions>", response.content, re.DOTALL)
        if match:
            lines = match.group(1).strip().split("\n")
            for l in lines:
                cleaned = re.sub(r"^\s*[-*\d.]+\s*", "", l).strip()
                if cleaned:
                    suggested_actions.append(cleaned)
            suggested_actions = suggested_actions[:3]

    return {
        "messages": [response],
        "suggested_actions": suggested_actions,
        "next": "__end__"
    }


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
workflow.add_node("deep_memory_node", deep_memory_node)
workflow.add_node("web_search_fanout", web_search_fanout)
workflow.add_node("web_search_worker", web_search_worker)
workflow.add_node("critic_agent", critic_agent)
workflow.add_node("supervisor_sales_agent", supervisor_sales_agent)

workflow.set_entry_point("supervisor_router")


def route_next(state: SupervisorState) -> Any:
    next_target = state.get("next", "supervisor_sales_agent")
    if isinstance(next_target, list):
        return next_target
    return next_target


workflow.add_conditional_edges("supervisor_router", route_next, {
    "rag_agent": "rag_agent",
    "booking_node": "booking_node",
    "query_node": "query_node",
    "deep_memory_node": "deep_memory_node",
    "web_search_fanout": "web_search_fanout",
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

workflow.add_conditional_edges("web_search_fanout", route_web_search_fanout, ["web_search_worker"])

workflow.add_edge("rag_agent", "supervisor_sales_agent")
workflow.add_edge("booking_agent", "supervisor_sales_agent")
workflow.add_edge("booking_read_agent", "supervisor_sales_agent")
workflow.add_edge("query_agent", "supervisor_sales_agent")
workflow.add_edge("query_read_agent", "supervisor_sales_agent")
workflow.add_edge("deep_memory_node", "supervisor_sales_agent")
workflow.add_edge("web_search_worker", "critic_agent")
workflow.add_edge("critic_agent", "supervisor_sales_agent")
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
