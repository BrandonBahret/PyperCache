from __future__ import annotations

import os
import sys
import time
from pathlib import Path

try:
    from .newsapi_wrapper import NewsApiClient
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from examples.news_api.newsapi_wrapper import NewsApiClient


def timed(label: str, fn):
    started = time.perf_counter()
    result = fn()
    elapsed_ms = (time.perf_counter() - started) * 1000
    print(f"{label}: {elapsed_ms:.1f} ms")
    return result


def main() -> None:
    if not os.getenv("NEWSAPI_API_KEY"):
        raise SystemExit("Set NEWSAPI_API_KEY before running this example.")

    client = NewsApiClient(
        cache_path="newsapi_cache.json",
        request_log_path="newsapi_requests.log",
    )

    try:
        headlines = timed(
            "Fetch US technology headlines",
            lambda: client.top_headlines(country="us", category="technology", page_size=5),
        )
        print(f"Returned: {headlines.total_results} total matches")
        for article in headlines.articles[:3]:
            print(f"- {article.title} ({article.source.name})")
        print()

        cached = timed(
            "Fetch US technology headlines again",
            lambda: client.top_headlines(country="us", category="technology", page_size=5),
        )
        print(f"Cached article count matches: {len(cached.articles) == len(headlines.articles)}")
        print()

        search = timed(
            "Search everything for Python AND caching",
            lambda: client.everything(
                query='"Python" AND caching',
                language="en",
                sort_by="publishedAt",
                page_size=3,
            ),
        )
        for article in search.articles:
            print(f"- {article.published_at.isoformat()}  {article.title}")
        print()

        sources = timed(
            "List US technology sources",
            lambda: client.list_sources(category="technology", language="en", country="us"),
        )
        print(f"Sources returned: {len(sources)}")
        if sources:
            print(f"First source: {sources[0].id} -> {sources[0].name}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
