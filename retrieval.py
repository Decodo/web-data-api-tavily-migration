"""A retrieval interface that makes the web search vendor a config value.

Set RETRIEVER=decodo or RETRIEVER=tavily. The agent code only sees search() and fetch().
"""
import os
import re
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

BLOCK = re.compile(r"(?i)captcha|access denied|verify you are human|enable javascript|unusual traffic")
MIN_PAGE_CHARS = 2_000  # Below this, treat the result as a snippet, an error page, or a page that still needs rendering
LINK_TARGETS = re.compile(r"!\[[^\]]*\]\([^)]*\)|(?<=\])\([^)]*\)")  # Images and link URLs, which aren't readable text
TIME_RANGES = {"day": "qdr:d", "week": "qdr:w", "month": "qdr:m", "year": "qdr:y"}
RETRY_STATUS = {429, 500, 502, 503, 504}


@dataclass
class Doc:
    url: str
    title: str
    text: str
    kind: str  # "snippet" for a search result, "page" for fetched content


def page_quality(text: str) -> str:
    """Label fetched text as complete, partial, or blocked."""
    if BLOCK.search(text[:5_000]):
        return "blocked"
    # Count readable text only, because a page shell full of menu links can be long and still have no content
    return "complete" if len(LINK_TARGETS.sub("", text)) >= MIN_PAGE_CHARS else "partial"


class Retriever(Protocol):
    def search(self, query: str, max_results: int = 5, domains: list[str] | None = None,
               time_range: str | None = None) -> list[Doc]: ...
    def fetch(self, url: str) -> Doc: ...


class DecodoRetriever:
    """Decodo Web Data API: parsed Google results for search, /scrape for the page itself."""

    def __init__(self, api_key: str | None = None, geo: str = "United States", timeout: float = 150.0):
        key = api_key or os.environ["DECODO_AUTH_TOKEN"]
        self.geo = geo
        self.http = httpx.Client(
            base_url="https://data.decodo.com/v1",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            timeout=timeout,
        )

    def _post(self, path: str, body: dict, attempts: int = 3) -> dict:
        for attempt in range(1, attempts + 1):
            try:
                resp = self.http.post(path, json=body)
                resp.raise_for_status()
                data = resp.json()
                if data.get("status") in ("failed", "faulted"):
                    raise RuntimeError(f"{path} failed: {data.get('message')}")
                return data
            except (httpx.TransportError, httpx.HTTPStatusError, RuntimeError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in RETRY_STATUS:
                    raise  # Don't retry a bad request or a bad key
                if attempt == attempts:
                    raise
                time.sleep(2 ** attempt)  # Wait 2 s, then 4 s

    def search(self, query: str, max_results: int = 5, domains: list[str] | None = None,
               time_range: str | None = None) -> list[Doc]:
        if domains:
            query += " (" + " OR ".join(f"site:{d}" for d in domains) + ")"
        # google_nfpr disables autocorrect, so Google searches the exact query
        body = {"target": "google_search", "query": query, "parse": True, "geo": self.geo, "google_nfpr": True}
        if time_range:
            body["google_tbs"] = TIME_RANGES[time_range]
        data = self._post("/scrape", body)
        organic = data["results"][0]["content"]["results"]["results"].get("organic", [])
        return [
            Doc(url=r["url"], title=r.get("title", ""), kind="snippet",
                text=r.get("desc", "").removesuffix("Read more"))  # Remove Google's "Read more" label
            for r in organic[:max_results]
        ]

    def _scrape(self, url: str, options: dict, attempts: int = 3) -> str:
        body = {"url": url, "markdown": True, "geo": self.geo, **options}
        try:
            data = self._post("/scrape", body, attempts)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 400:
                raise
            body.pop("geo")  # Retry once with the default location
            data = self._post("/scrape", body, attempts)
        result = data["results"][0]
        text = result.get("content") or ""
        if not text:  # Some sites send a real page with a 403, so judge the content, not the code
            raise RuntimeError(f"{url} returned no content (HTTP {result.get('status_code')})")
        return text

    def fetch(self, url: str) -> Doc:
        # Try the lowest-cost settings first, and add JavaScript rendering only for pages that need it
        steps = [{"proxy_pool": "standard"}, {"proxy_pool": "premium"},
                 {"proxy_pool": "premium", "headless": "html"}]
        for i, options in enumerate(steps):
            last = i == len(steps) - 1
            try:
                text = self._scrape(url, options, attempts=3 if last else 1)
            except (httpx.HTTPError, RuntimeError):
                if last:
                    raise
                continue
            if last or page_quality(text) == "complete":
                return Doc(url=url, title="", text=text, kind="page")


class TavilyRetriever:
    """The existing Tavily setup, kept behind the same interface as a fallback."""

    def __init__(self, api_key: str | None = None):
        from tavily import TavilyClient

        self.client = TavilyClient(api_key=api_key or os.environ["TAVILY_API_KEY"])

    def search(self, query: str, max_results: int = 5, domains: list[str] | None = None,
               time_range: str | None = None) -> list[Doc]:
        data = self.client.search(query, max_results=max_results, include_domains=domains, time_range=time_range)
        return [
            Doc(url=r["url"], title=r.get("title", ""), text=r.get("content", ""), kind="snippet")
            for r in data.get("results", [])
        ]

    def fetch(self, url: str) -> Doc:
        data = self.client.extract(urls=[url], format="markdown")
        results = data.get("results", [])
        if not results:
            raise RuntimeError(f"{url} could not be extracted")
        return Doc(url=url, title="", text=results[0].get("raw_content") or "", kind="page")


def get_retriever() -> Retriever:
    name = os.environ.get("RETRIEVER", "decodo")
    return {"decodo": DecodoRetriever, "tavily": TavilyRetriever}[name]()
