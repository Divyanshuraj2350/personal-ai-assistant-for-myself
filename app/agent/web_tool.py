import os

from dotenv import load_dotenv
from tavily import AsyncTavilyClient


load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not TAVILY_API_KEY:
    raise RuntimeError(
        "TAVILY_API_KEY is not set. Add it to the .env file."
    )


client = AsyncTavilyClient(api_key=TAVILY_API_KEY)


async def web_search(query, limit=5):
    response = await client.search(
        query=query,
        max_results=limit,
        search_depth="basic",
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