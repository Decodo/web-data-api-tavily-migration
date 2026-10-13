"""Check that your Web Data API key and setup work.

Runs one search and one page fetch with your key,
then exits non-zero if any check needs attention.
"""
import sys

from retrieval import DecodoRetriever, page_quality


def main() -> int:
    retriever = DecodoRetriever()
    problems = []

    docs = retriever.search("fastapi dependency injection tutorial", max_results=3)
    if not docs:
        problems.append("search returned no results")

    page = retriever.fetch("https://fastapi.tiangolo.com/tutorial/dependencies/")
    if page_quality(page.text) != "complete":
        problems.append(f"fetch returned {page_quality(page.text)} content")

    for problem in problems:
        print(f"CHECK: {problem}")
    print("All checks passed" if not problems else f"{len(problems)} check(s) need attention")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
