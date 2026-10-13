# Migrate a LangChain agent from Tavily to Decodo's Web Data API

This example replaces the Tavily search tool in a LangChain agent with 2 tools, `web_search` and `fetch_page`, backed by [Decodo's Web Data API](https://decodo.com/web-data-api). Both tools call one retrieval interface, so switching the backend is a config change, and Tavily stays available as a fallback.

It's the complete, tested code from the article [Tavily alternatives: 7 agentic search APIs compared](https://decodo.com/blog/tavily-alternatives).

## What you get

- **Search and page fetch behind one API key**. The `web_search` tool returns live Google results, and the `fetch_page` tool returns the page itself as markdown.
- **Pages that search alone can't reach**. Fetches start on the lowest-cost settings and add the premium pool, then JavaScript rendering, only when a page needs it.
- **The Tavily options your agent uses**. Domain and date filters carry over, so answers don't change without warning.
- **A safe switch**. Run both backends side by side on your own URLs before you commit.

## Quickstart

You need Python 3.10 or later and a Web Data API key. Get your key on the [free plan](https://decodo.com/web-data-api), then copy `.env.example` to `.env` and add the key.

With [uv](https://docs.astral.sh/uv/), one command installs the dependencies and runs the demo:

```bash
uv run --env-file .env agent_tools.py
```

With pip:

```bash
pip install -r requirements.txt
set -a; source .env; set +a
python agent_tools.py
```

The demo runs one web search and fetches one page as markdown.

## Use the tools in your agent

Swap the Tavily tool for the 2 new tools wherever you build your agent's tool list.

```python
# Before
from langchain_tavily import TavilySearch
tools = [TavilySearch(max_results=5)]

# After
from agent_tools import web_search, fetch_page
tools = [web_search, fetch_page]
```

The model can pass the same filters it used with Tavily.

```python
web_search.invoke({"query": "langchain release", "domains": ["github.com"], "time_range": "month"})
```

## Check your setup

```bash
python smoke_test.py
```

It runs a search and a page fetch with your key, then prints "All checks passed".

## Files

| File | What it does |
|---|---|
| `retrieval.py` | The retrieval interface. The `DecodoRetriever` class searches with the Google Search target and fetches pages with `/scrape`. The `TavilyRetriever` class keeps your existing Tavily setup behind the same interface. |
| `agent_tools.py` | The LangChain tools `web_search` and `fetch_page`, plus a short demo. |
| `shadow_eval.py` | Sends the same URLs to both backends and labels each result as complete, partial, blocked, or error. |
| `smoke_test.py` | Confirms that your key and setup work. |
| `urls.txt` | Sample URLs for the shadow evaluation. Replace them with URLs from your own agent logs. |

## Tavily options and their Web Data API equivalents

| Tavily option | Web Data API equivalent |
|---|---|
| `include_domains` | `site:` operators in the query, with `google_nfpr` set to `true` so Google keeps the exact query |
| `time_range` | `google_tbs`, for example `qdr:w` for the past week |
| `include_raw_content` | A `fetch_page` call for the result URL |
| `country` | `geo`, which runs the search from that country instead of boosting results |
| `include_answer` | The agent's own model, which writes the answer from full pages instead of snippets |

## Run a shadow evaluation

Put the URLs your agent fetched in production into `urls.txt`, one per line, then run:

```bash
python shadow_eval.py urls.txt
```

With `TAVILY_API_KEY` set, each URL is checked on both backends. Compare completeness first, because a CAPTCHA page passed to the model as content can change the agent's answer.

## Keep Tavily as a fallback during the switch

Leave your Tavily setup behind the same interface for 1 release cycle, so switching backends stays a one-line config change. To route calls to it, install the optional extra and set 2 variables.

```bash
pip install tavily-python
export TAVILY_API_KEY=your-tavily-key
export RETRIEVER=tavily
```

## Learn more

- [Web Data API documentation](https://help.decodo.com/docs/web-data-api-introduction)
- [Pricing](https://decodo.com/web-data-api/pricing)
- [Decodo LangChain integration](https://decodo.com/integrations/langchain)
