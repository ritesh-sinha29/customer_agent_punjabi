import os
import json
import logging
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langgraph.types import Send

from src.app.core.config import settings
from src.app.graphs.state import SupervisorState
from src.app.tools.web_search_tools import execute_tavily_search

logger = logging.getLogger("WebSearchAgent")

sub_agent_model = "gpt-4.1-mini"
sub_agent_llm = ChatOpenAI(model=sub_agent_model, temperature=0.2, api_key=settings.OPENAI_API_KEY)


class QueryDecomposition(BaseModel):
    queries: List[str] = Field(
        description="3 to 5 distinct search queries expressing the user's request from different perspectives (max 5 queries)."
    )


def web_search_fanout(state: SupervisorState):
    """
    Decomposes the user query into up to 5 distinct search perspectives (max limit 5) and executes parallel web search workers.
    """
    messages = state.get("messages", [])
    last_user_query = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_query = msg.content
            break
        elif isinstance(msg, dict) and msg.get("role") == "user":
            last_user_query = msg.get("content", "")
            break

    if not last_user_query:
        last_user_query = "latest dairy farming and livestock market trends"

    decomp_prompt = (
        f"You are a Search Query Architect for Vrsa Agrotech.\n"
        f"User query: '{last_user_query}'\n"
        f"Generate 3 to 5 distinct search query strings (maximum 5) to query the web in parallel:\n"
        f"1. Factual / Direct Query\n"
        f"2. Scientific / Technical Domain Query\n"
        f"3. Practical Market / Farmer Use-case Query\n"
        f"4. Innovation / Future Industry Query (if applicable)"
    )

    try:
        structured_llm = sub_agent_llm.with_structured_output(QueryDecomposition, method="function_calling")
        res: QueryDecomposition = structured_llm.invoke([SystemMessage(content=decomp_prompt)])
        queries = res.queries[:5]  # Hard limit max 5 queries
        if len(queries) < 3:
            queries.extend([last_user_query] * (3 - len(queries)))
    except Exception as e:
        logger.error(f"[WEB SEARCH AGENT] Query decomposition error: {e}")
        queries = [last_user_query, f"{last_user_query} research trends", f"{last_user_query} market price"]

    return {"web_search_queries": queries}


def route_web_search_fanout(state: SupervisorState) -> List[Send]:
    """
    Conditional edge router exiting web_search_fanout node.
    Spawns parallel web_search_worker nodes using Send().
    """
    queries = state.get("web_search_queries", [])
    if not queries:
        queries = ["latest AI technology 2026"]
    return [Send("web_search_worker", {"query": q}) for q in queries[:5]]


async def web_search_worker(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parallel worker node that executes Tavily web search for a single query perspective.
    Appends search results into web_search_raw_results via operator.add without overwriting.
    """
    query = state.get("query", "")
    logger.info(f"[WEB SEARCH WORKER] Searching Tavily for query: '{query}'")
    
    search_res = await execute_tavily_search(query, max_results=3)
    results = search_res.get("results", [])

    worker_items = []
    for idx, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("url", "")
        if title:
            worker_items.append({"title": title, "url": url})
    
    return {
        "web_search_raw_results": [search_res],
        "web_search_worker_items": worker_items
    }


class CitationItem(BaseModel):
    title: str = Field(default="", description="Title of the web source.")
    url: str = Field(default="", description="URL of the web source.")


class CriticEvaluation(BaseModel):
    verified_facts: str = Field(description="Concise, de-duplicated essential facts synthesized from web results.")
    citations: List[CitationItem] = Field(default_factory=list, description="List of source citations used.")


async def critic_agent(state: SupervisorState) -> Dict[str, Any]:
    """
    Critic Agent node: Aggregates parallel search results, de-duplicates content, adds citations,
    and extracts minimal concise essential facts to send to supervisor_sales_agent.
    """
    raw_results = state.get("web_search_raw_results") or []
    formatted_docs = ""
    idx = 1
    for item in raw_results:
        q = item.get("query", "")
        results = item.get("results", [])
        formatted_docs += f"\n--- Search Stream for Query: '{q}' ---\n"
        for r in results:
            formatted_docs += f"[{idx}] Title: {r.get('title')}\nURL: {r.get('url')}\nContent: {r.get('content')}\n\n"
            idx += 1

    critic_prompt = (
        f"You are the Lead Critic & Fact Verification Agent for Vrsa Agrotech.\n"
        f"Review the 3 parallel web search streams below.\n\n"
        f"RULES:\n"
        f"1. De-duplicate overlapping information across streams.\n"
        f"2. Extract ONLY highly relevant, verified, minimal, concise essential facts.\n"
        f"3. Include inline URL citations wherever external facts are asserted.\n\n"
        f"DOCUMENT SEARCH STREAMS:\n{formatted_docs}"
    )

    try:
        structured_critic = sub_agent_llm.with_structured_output(CriticEvaluation, method="function_calling")
        critic_res: CriticEvaluation = await structured_critic.ainvoke([SystemMessage(content=critic_prompt)])
        verified_facts = critic_res.verified_facts
        citations = [{"title": c.title, "url": c.url} for c in critic_res.citations]
    except Exception as e:
        logger.error(f"[CRITIC AGENT] Fact verification error: {e}")
        verified_facts = formatted_docs[:1000]
        citations = []

    existing_facts = list(state.get("internal_facts") or [])
    payload = {
        "subagent": "critic_agent",
        "verified_web_facts": verified_facts,
        "citations": citations
    }
    existing_facts.append(payload)

    return {
        "internal_facts": existing_facts,
        "next": "supervisor_sales_agent"
    }
