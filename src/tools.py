"""Tools for the Xpanse Agent Pipeline.

Tools:
    1. web_search_tool — Tavily search for live market/compliance research
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Web Search Tool (Tavily)
# ---------------------------------------------------------------------------

_tavily_client = None


def _get_tavily_client():
    """Initialize the Tavily client."""
    global _tavily_client
    if _tavily_client is not None:
        return _tavily_client

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        api_key = "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"

    try:
        from tavily import TavilyClient
        _tavily_client = TavilyClient(api_key=api_key)
        return _tavily_client
    except ImportError:
        logger.error("tavily-python not installed")
        return None


def web_search_tool(query: str, max_results: int = 5) -> list[dict]:
    """Search the web using Tavily for current market/regulatory information.

    Args:
        query: Search query string.
        max_results: Maximum number of results.

    Returns:
        List of dicts with 'title', 'url', 'content' keys.
    """
    client = _get_tavily_client()

    if client is None:
        return [{"title": "Search unavailable", "url": "", "content": "Tavily client not configured."}]

    try:
        response = client.search(query=query, max_results=max_results)
        results = []
        for item in response.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
            })
        logger.info("Tavily search returned %d results for: %s", len(results), query[:50])
        return results
    except Exception as e:
        logger.error("Tavily search error: %s", e)
        return [{"title": "Search error", "url": "", "content": str(e)}]
