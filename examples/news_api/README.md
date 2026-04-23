# NewsAPI Wrapper Example

This example uses [NewsAPI](https://newsapi.org/), a real news-search API with API-key authentication. It is a good tutorial companion for learning how to:

- subclass `ApiWrapper` for a single-host JSON API
- centralize authentication in `get_session()`
- hydrate typed response models with `@apimodel(validate=True)`
- map camelCase response keys like `urlToImage` and `publishedAt` with `Alias(...)`
- parse ISO 8601 timestamps with `Timestamp()`
- cache read-heavy `GET` requests while keeping endpoint methods thin

## Before you run it

You need your own NewsAPI key.

1. Create a free developer account at [newsapi.org](https://newsapi.org/).
2. Generate an API key.
3. Set it as an environment variable instead of hard-coding it.

PowerShell:

```powershell
$env:NEWSAPI_API_KEY = "your_api_key_here"
```

The free Developer plan is intended for development and testing. As of April 22, 2026, NewsAPI's pricing page says it is `$0`, limited to `100 requests per day`, and returns articles with a `24 hour delay`, so this example README treats it as a tutorial-only setup rather than a production recipe.

## Quick start

```bash
python examples/news_api/app.py
```

## Public surface

```python
from examples.news_api.newsapi_wrapper import NewsApiClient

client = NewsApiClient(
    api_key="your_api_key_here",
    cache_path="newsapi_cache.json",
)

headlines = client.top_headlines(country="us", category="technology", page_size=5)
search = client.everything(
    query='"Python" AND caching',
    language="en",
    sort_by="publishedAt",
    page_size=10,
)
sources = client.list_sources(category="technology", language="en", country="us")
```

## Why this example is useful

Compared to the simpler JSONPlaceholder demo, this wrapper adds a realistic authentication step and slightly richer query handling:

- every request needs an API key
- the key is attached once in `get_session()` through the `X-Api-Key` header
- article timestamps are hydrated into `datetime` objects
- helper methods join list-like parameters into the comma-separated strings NewsAPI expects
- `top_headlines()` validates NewsAPI's rule that `sources` cannot be mixed with `country` or `category`

That keeps the tutorial focused on a pattern many real APIs use: one shared authenticated session plus thin endpoint methods.

## Upstream docs

- [NewsAPI docs](https://newsapi.org/docs)
- [Authentication docs](https://newsapi.org/docs/authentication)
- [Everything endpoint](https://newsapi.org/docs/endpoints/everything)
- [Top headlines endpoint](https://newsapi.org/docs/endpoints/top-headlines)
- [Sources endpoint](https://newsapi.org/docs/endpoints/sources)
- [Pricing](https://newsapi.org/pricing)
