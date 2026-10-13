"""LangChain tools that replace the Tavily search tool in an agent's tool list."""
from typing import Literal

from langchain_core.tools import tool

from retrieval import get_retriever, page_quality

retriever = get_retriever()
MAX_PAGE_CHARS = 12_000  # Limit each fetched page so it doesn't fill the context window


@tool(parse_docstring=True)
def web_search(query: str, domains: list[str] | None = None,
               time_range: Literal["day", "week", "month", "year"] | None = None) -> str:
    """Search the live web. Returns up to 5 results with title, URL, and snippet.

    Args:
        query: The search query.
        domains: Only return results from these domains, such as ["github.com"].
        time_range: Only return results from the last day, week, month, or year.
    """
    try:
        docs = retriever.search(query, max_results=5, domains=domains, time_range=time_range)
    except Exception as exc:  # Return the error to the agent instead of ending the run
        return f"Search failed for {query!r}: {exc}"
    return "\n\n".join(f"{d.title}\n{d.url}\n{d.text}" for d in docs) or "No results."


@tool
def fetch_page(url: str) -> str:
    """Fetch one URL and return its main content as markdown."""
    try:
        text = retriever.fetch(url).text
    except Exception as exc:  # Return the error to the agent instead of ending the run
        return f"Fetch failed for {url}: {exc}"
    if page_quality(text) == "blocked":  # Don't pass a CAPTCHA or block page to the model as content
        return f"Fetch failed for {url}: the site returned a block page instead of content."
    start = text.find("\n# ")  # Skip site navigation when the page has a title heading
    return text[max(start, 0):][:MAX_PAGE_CHARS].strip()


if __name__ == "__main__":
    results = web_search.invoke({"query": "fastapi dependency injection tutorial"})
    print(results.split("\n\n")[0])  # First result
    print("---")
    print(fetch_page.invoke({"url": "https://fastapi.tiangolo.com/tutorial/dependencies/"})[:250])
