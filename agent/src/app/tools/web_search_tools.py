import logging
import httpx
from typing import Dict, Any, List
from src.app.core.config import settings

logger = logging.getLogger("WebSearchTools")

TAVILY_SEARCH_URL = "https://api.tavily.com/search"

async def execute_tavily_search(query: str, max_results: int = 4) -> Dict[str, Any]:
    """
    Executes an asynchronous Tavily Web Search request.
    Returns structured results including title, url, snippet/content.
    """
    api_key = settings.TAVILY_API_KEY
    if not api_key:
        logger.error("[WebSearchTools] TAVILY_API_KEY is not set.")
        return {"query": query, "results": [], "error": "Tavily API key missing"}

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(TAVILY_SEARCH_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            logger.info(f"[WebSearchTools] Query '{query}' returned {len(results)} search results.")
            return {
                "query": query,
                "results": [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "content": r.get("content", "")
                    }
                    for r in results
                ]
            }
    except Exception as e:
        logger.error(f"[WebSearchTools] Error during Tavily search for '{query}': {e}")
        return {"query": query, "results": [], "error": str(e)}
