from __future__ import annotations

from typing import Any

import pytest

from examples.news_api.newsapi_wrapper import (
    Article,
    ArticleSearchResult,
    NewsApiClient,
    NewsSource,
)


class DummyResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        url: str = "https://newsapi.org/v2/top-headlines",
        json_data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.url = url
        self._json_data = json_data
        self.headers = headers or {"content-type": "application/json"}
        import json

        self.content = json.dumps(json_data).encode("utf-8")

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")

    def json(self) -> Any:
        return self._json_data

    def close(self) -> None:
        return None


class DummySession:
    def __init__(self, responses: list[DummyResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


def test_newsapi_client_sets_auth_header():
    client = NewsApiClient(api_key="test-key", cache_path=None)
    try:
        assert client.session.headers["X-Api-Key"] == "test-key"
        assert client.session.headers["Accept"] == "application/json"
    finally:
        client.close()


def test_top_headlines_casts_typed_articles(tmp_path):
    session = DummySession(
        [
            DummyResponse(
                json_data={
                    "status": "ok",
                    "totalResults": 1,
                    "articles": [
                        {
                            "source": {"id": "bbc-news", "name": "BBC News"},
                            "author": "Reporter",
                            "title": "Headline",
                            "description": "Summary",
                            "url": "https://example.com/story",
                            "urlToImage": "https://example.com/image.jpg",
                            "publishedAt": "2026-04-22T10:30:00Z",
                            "content": "Story body",
                        }
                    ],
                }
            )
        ]
    )
    client = NewsApiClient(api_key="test-key", cache_path=str(tmp_path / "news.json"), session=session)

    try:
        result = client.top_headlines(country="us", category="technology", page_size=5)
    finally:
        client.close()

    assert isinstance(result, ArticleSearchResult)
    assert result.total_results == 1
    assert isinstance(result.articles[0], Article)
    assert result.articles[0].source.name == "BBC News"
    assert result.articles[0].published_at.isoformat() == "2026-04-22T10:30:00+00:00"
    assert session.calls[0]["params"]["pageSize"] == 5


def test_list_sources_returns_typed_sources(tmp_path):
    session = DummySession(
        [
            DummyResponse(
                url="https://newsapi.org/v2/top-headlines/sources",
                json_data={
                    "status": "ok",
                    "sources": [
                        {
                            "id": "techcrunch",
                            "name": "TechCrunch",
                            "description": "Startup news",
                            "url": "https://techcrunch.com",
                            "category": "technology",
                            "language": "en",
                            "country": "us",
                        }
                    ],
                },
            )
        ]
    )
    client = NewsApiClient(api_key="test-key", cache_path=str(tmp_path / "news.json"), session=session)

    try:
        sources = client.list_sources(category="technology", language="en", country="us")
    finally:
        client.close()

    assert len(sources) == 1
    assert isinstance(sources[0], NewsSource)
    assert sources[0].id == "techcrunch"


def test_top_headlines_rejects_invalid_param_mix():
    client = NewsApiClient(api_key="test-key", cache_path=None)
    try:
        with pytest.raises(ValueError, match="sources together with country or category"):
            client.top_headlines(country="us", sources=["bbc-news"])
    finally:
        client.close()


def test_client_requires_api_key():
    with pytest.raises(ValueError, match="requires an API key"):
        NewsApiClient(api_key=None, cache_path=None)
