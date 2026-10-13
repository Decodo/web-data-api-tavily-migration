"""Send the same production URLs to two retrievers and check how complete each page is.

Usage: python shadow_eval.py urls.txt
Each line of urls.txt is one URL your agent needed in production.
"""
import os
import sys

from retrieval import DecodoRetriever, TavilyRetriever, page_quality


def check_page(retriever, url: str) -> str:
    try:
        text = retriever.fetch(url).text
    except Exception as exc:
        return f"error ({type(exc).__name__})"
    return f"{page_quality(text)} ({len(text)} chars)"


def main(path: str) -> None:
    with open(path) as f:
        urls = [line.strip() for line in f if line.strip()]
    retrievers = {"decodo": DecodoRetriever()}
    if os.environ.get("TAVILY_API_KEY"):
        retrievers["tavily"] = TavilyRetriever()
    totals = {name: 0 for name in retrievers}
    for url in urls:
        row = {name: check_page(retriever, url) for name, retriever in retrievers.items()}
        for name, label in row.items():
            totals[name] += label.startswith("complete")
        print(url, row)
    for name, n in totals.items():
        print(f"{name}: {n} of {len(urls)} complete")


if __name__ == "__main__":
    main(sys.argv[1])
