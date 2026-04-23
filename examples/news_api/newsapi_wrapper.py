from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated, Iterable

from pypercache.api_wrapper import ApiWrapper
from pypercache.models.apimodel import Alias, Timestamp, apimodel


BASE_URL = "https://newsapi.org/v2"
DEFAULT_CACHE_PATH = "newsapi_cache.json"
DEFAULT_TIMEOUT = 10
ARTICLES_CACHE_SECONDS = 900
SOURCES_CACHE_SECONDS = 86_400


def _csv(values: Iterable[str] | None) -> str | None:
    if values is None:
        return None
    items = [str(value).strip() for value in values if str(value).strip()]
    return ",".join(items) or None


@apimodel(validate=True)
class ArticleSource:
    id: str | None
    name: str


@apimodel(validate=True)
class Article:
    source: ArticleSource
    author: str | None
    title: str
    description: str | None
    url: str
    url_to_image: Annotated[str | None, Alias("urlToImage")]
    published_at: Annotated[datetime, Alias("publishedAt"), Timestamp()]
    content: str | None


@apimodel(validate=True)
class ArticleSearchResult:
    status: str
    total_results: Annotated[int, Alias("totalResults")]
    articles: list[Article]


@apimodel(validate=True)
class NewsSource:
    id: str
    name: str
    description: str
    url: str
    category: str
    language: str
    country: str


@apimodel(validate=True)
class SourceSearchResult:
    status: str
    sources: list[NewsSource]


class NewsApiClient(ApiWrapper):
    """NewsAPI example client showing API-key auth with ApiWrapper."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        cache_path: str | None = DEFAULT_CACHE_PATH,
        default_expiry: int | float = ARTICLES_CACHE_SECONDS,
        request_log_path: str | None = None,
        timeout: int | float | None = DEFAULT_TIMEOUT,
        session=None,
    ) -> None:
        self.api_key = api_key or os.getenv("NEWSAPI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "NewsApiClient requires an API key. Pass api_key=... or set NEWSAPI_API_KEY."
            )

        super().__init__(
            origins={"default": BASE_URL},
            default_origin="default",
            cache_path=cache_path,
            default_expiry=default_expiry,
            request_log_path=request_log_path,
            timeout=timeout,
            session=session,
        )

    def get_session(self):
        session = super().get_session()
        session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "pypercache-newsapi-example/0.1",
                "X-Api-Key": self.api_key,
            }
        )
        return session

    def everything(
        self,
        *,
        query: str | None = None,
        search_in: Iterable[str] | None = None,
        sources: Iterable[str] | None = None,
        domains: Iterable[str] | None = None,
        exclude_domains: Iterable[str] | None = None,
        from_date: str | datetime | None = None,
        to_date: str | datetime | None = None,
        language: str | None = None,
        sort_by: str = "publishedAt",
        page_size: int = 20,
        page: int = 1,
    ) -> ArticleSearchResult:
        return self.request(
            "GET",
            "/everything",
            params={
                "q": query,
                "searchIn": _csv(search_in),
                "sources": _csv(sources),
                "domains": _csv(domains),
                "excludeDomains": _csv(exclude_domains),
                "from": self._isoformat(from_date),
                "to": self._isoformat(to_date),
                "language": language,
                "sortBy": sort_by,
                "pageSize": page_size,
                "page": page,
            },
            expected="json",
            cast=ArticleSearchResult,
            expiry=ARTICLES_CACHE_SECONDS,
        )

    def top_headlines(
        self,
        *,
        country: str | None = None,
        category: str | None = None,
        sources: Iterable[str] | None = None,
        query: str | None = None,
        page_size: int = 20,
        page: int = 1,
    ) -> ArticleSearchResult:
        source_ids = _csv(sources)
        if source_ids and (country or category):
            raise ValueError("NewsAPI does not allow sources together with country or category.")

        return self.request(
            "GET",
            "/top-headlines",
            params={
                "country": country,
                "category": category,
                "sources": source_ids,
                "q": query,
                "pageSize": page_size,
                "page": page,
            },
            expected="json",
            cast=ArticleSearchResult,
            expiry=ARTICLES_CACHE_SECONDS,
        )

    def list_sources(
        self,
        *,
        category: str | None = None,
        language: str | None = None,
        country: str | None = None,
    ) -> list[NewsSource]:
        result = self.request(
            "GET",
            "/top-headlines/sources",
            params={
                "category": category,
                "language": language,
                "country": country,
            },
            expected="json",
            cast=SourceSearchResult,
            expiry=SOURCES_CACHE_SECONDS,
        )
        return result.sources

    @staticmethod
    def _isoformat(value: str | datetime | None) -> str | None:
        if value is None or isinstance(value, str):
            return value
        return value.isoformat()


__all__ = [
    "Article",
    "ArticleSearchResult",
    "ArticleSource",
    "NewsApiClient",
    "NewsSource",
    "SourceSearchResult",
]
