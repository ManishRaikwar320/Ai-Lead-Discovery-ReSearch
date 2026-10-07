from functools import lru_cache

from tavily import TavilyClient

from app.config import get_settings


@lru_cache
def get_tavily_client() -> TavilyClient:
    settings = get_settings()

    return TavilyClient(
        api_key=settings.tavily_api_key
    )


def search_web(
    query: str,
    max_results: int = 5,
) -> list[dict]:
    """
    Search the public web using Tavily.

    Returns normalized search results.
    """

    client = get_tavily_client()

    response = client.search(
        query=query,
        search_depth="basic",
        max_results=max_results,
        include_answer=False,
        include_raw_content=False,
    )

    results = []

    for result in response.get("results", []):
        results.append(
            {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", ""),
            }
        )

    return results