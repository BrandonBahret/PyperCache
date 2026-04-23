# Build With ApiWrapper

`ApiWrapper` is the highest-level integration surface in PyperCache. Use it when you want a small Python client where endpoint methods stay thin and the base class handles HTTP, caching, and typed hydration.

It is designed for request/response-oriented clients where most reads are `GET` requests and where automatic cache lookup plus typed response hydration remove repetitive plumbing from endpoint methods.

## Constructor shape

The current implementation uses named origins, not a single `base_url`.

```python
from pypercache.api_wrapper import ApiWrapper


class MyClient(ApiWrapper):
    def __init__(self) -> None:
        super().__init__(
            origins={"default": "https://api.example.com"},
            default_origin="default",
            cache_path="example_cache.db",
            default_expiry=300,
            request_log_path="example_requests.log",
            timeout=10,
        )
```

For multi-host APIs, add more origins and select them per request:

```python
super().__init__(
    origins={
        "api": "https://api.example.com",
        "auth": "https://auth.example.com",
    },
    default_origin="api",
)
```

## Basic subclass pattern

Keep endpoint methods thin. Let `request()` handle URL building, caching, response decoding, and model hydration.

```python
from typing import Annotated

from pypercache.api_wrapper import ApiWrapper
from pypercache.models.apimodel import Alias, apimodel


@apimodel(validate=True)
class Widget:
    id: int
    display_name: Annotated[str, Alias("displayName")]


class WidgetClient(ApiWrapper):
    def __init__(self) -> None:
        super().__init__(
            origins={"default": "https://api.example.com"},
            default_origin="default",
            cache_path="widget_cache.json",
            default_expiry=300,
        )

    def get_session(self):
        session = super().get_session()
        session.headers.update({"User-Agent": "widget-client/1.0"})
        return session

    def list_widgets(self) -> list[Widget]:
        return self.request("GET", "/widgets", expected="json", cast=list[Widget])

    def get_widget(self, widget_id: int) -> Widget:
        return self.request("GET", f"/widgets/{widget_id}", expected="json", cast=Widget)

    def create_widget(self, name: str) -> Widget:
        return self.request(
            "POST",
            "/widgets",
            expected="json",
            json_body={"name": name},
            use_cache=False,
            cast=Widget,
        )
```

## Short recipes from this repo

### Single-origin JSON API client

This mirrors `examples/jsonplaceholder_api`:

```python
client = JSONPlaceholderClient(
    cache_path="jsonplaceholder_cache.json",
    request_log_path="jsonplaceholder_requests.log",
)

posts = client.list_posts()
post = client.get_post(1)
author = client.get_user(post.user_id)
comments = client.list_post_comments(post.id)
todo = client.get_todo(1)

created = client.create_post(
    user_id=1,
    title="Demo title",
    body="Demo body",
)

client.close()
```

That one example covers:

- cacheable `GET` requests
- a non-cacheable `POST`
- typed response models
- optional request logging

### Single-origin API client with authentication

This mirrors `examples/news_api`:

```python
class NewsApiClient(ApiWrapper):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        super().__init__(
            origins={"default": "https://newsapi.org/v2"},
            default_origin="default",
            cache_path="newsapi_cache.json",
            default_expiry=900,
        )

    def get_session(self):
        session = super().get_session()
        session.headers.update({"X-Api-Key": self.api_key})
        return session

    def top_headlines(self) -> ArticleSearchResult:
        return self.request(
            "GET",
            "/top-headlines",
            params={"country": "us", "category": "technology", "pageSize": 5},
            expected="json",
            cast=ArticleSearchResult,
        )
```

That pattern covers:

- API-key authentication in one shared session
- cacheable authenticated `GET` requests
- typed response models with aliases and timestamps
- wrapper-level validation for endpoint-specific parameter rules

### Multi-origin API client

This mirrors `examples/weather_api`:

```python
class WeatherClient(ApiWrapper):
    def __init__(self) -> None:
        super().__init__(
            origins={
                "forecast": "https://api.open-meteo.com/v1",
                "geocode": "https://geocoding-api.open-meteo.com/v1",
            },
            default_origin="forecast",
            cache_path="weather_cache.db",
        )

    def search(self, query: str) -> GeocodingResults:
        return self.request(
            "GET",
            "/search",
            params={"name": query, "count": 5, "format": "json"},
            expected="json",
            cast=GeocodingResults,
            origin="geocode",
        )

    def forecast(self, latitude: float, longitude: float) -> Forecast:
        return self.request(
            "GET",
            "/forecast",
            params={"latitude": latitude, "longitude": longitude},
            expected="json",
            cast=Forecast,
        )
```

The important point is `origin="geocode"` on the non-default host.

### Consumer-side convenience methods

PyperCache does not dictate your wrapper's public surface. The Open-Meteo example shows how to add a friendlier layer on top:

```python
client = OpenMeteoClient(
    cache_path="openmeteo_cache.db",
    request_log_path="openmeteo_requests.log",
)

report = client.at("Phoenix", country_code="US").forecast(days=3)

print(report.location.label)
print(report.now.temperature_c, report.now.summary)
print(report.today.high_c, report.today.low_c)

for hour in report.next_hours(5):
    print(hour.time, hour.temperature_c, hour.summary)

location = client.resolve("Phoenix", country_code="US")
forecast = client.forecast(location, days=3)
report = client.weather("Phoenix", country_code="US", days=3)

client.close()
```

Methods like `search()`, `resolve()`, `at()`, `forecast()`, and `weather()` are wrapper-specific conveniences. `ApiWrapper` exists to support that style, not to limit it.

## What `request()` does for you

- joins relative paths against the selected origin
- removes `None` values from `params` and form `data`
- decodes JSON, text, bytes, or empty responses
- caches eligible `GET` responses
- hydrates return values with `cast=...`
- records request metadata when `request_log_path` is configured
- raises `ApiHTTPError` on HTTP 4xx and 5xx responses

That is the manual fetch-or-cache flow from the lower-level docs, packaged into one method.

## Caching rules

`ApiWrapper` caching is intentionally simple:

- only `GET` requests are cacheable
- only `expected="auto"` and `expected="json"` are cached
- stale entries are refetched, not served
- `use_cache=False` bypasses both lookup and writeback
- if `cache_path` is omitted, the wrapper has no cache

For mutating requests like `POST`, `PUT`, and `DELETE`, explicitly pass `use_cache=False`.

The cached payload shape is `{"value": decoded_response}`. You usually do not need to care about that unless you are inspecting the underlying cache file directly.

Short cache-hit example:

```python
first = client.get_post(1)
again = client.get_post(1)
print(again.title == first.title)
```

That is the same pattern used in the JSONPlaceholder demo app.

## Typed responses

Use `cast=...` when you want typed output:

```python
item = client.request("GET", "/widgets/7", expected="json", cast=Widget)
items = client.request("GET", "/widgets", expected="json", cast=list[Widget])
```

`cast` works well with:

- `@apimodel` classes
- builtin containers like `list[MyModel]`
- plain dataclasses and other supported types

For model design details, see [Typed models with `@apimodel`](./typed-models.md).

## Short endpoint method recipes

### Query parameters

```python
def list_widgets(self, page: int = 1) -> list[Widget]:
    return self.request(
        "GET",
        "/widgets",
        params={"page": page, "limit": 50},
        expected="json",
        cast=list[Widget],
    )
```

### JSON request body

```python
def create_widget(self, name: str) -> Widget:
    return self.request(
        "POST",
        "/widgets",
        expected="json",
        json_body={"name": name},
        use_cache=False,
        cast=Widget,
    )
```

### Per-request origin selection

```python
def search_places(self, query: str) -> GeocodingResults:
    return self.request(
        "GET",
        "/search",
        params={"name": query, "count": 5, "format": "json"},
        expected="json",
        cast=GeocodingResults,
        origin="geocode",
    )
```

## Other useful methods

### `download_to(...)`

Use this when the response should be written straight to disk:

```python
report_path = client.download_to("/reports/today.pdf", "downloads/today.pdf")
```

### `stream_sse(...)`

Use this for low-level Server-Sent Events parsing:

```python
for event in client.stream_sse("/events"):
    print(event.event, event.id, event.data)
```

This parser does not reconnect automatically and does not try to emulate browser `EventSource`.

## Error handling

HTTP errors raise `ApiHTTPError`:

```python
from pypercache.api_wrapper import ApiHTTPError

try:
    client.get_widget(404)
except ApiHTTPError as exc:
    print(exc.status_code)
    print(exc.url)
    print(exc.body)
```

## Lifecycle

If you let `ApiWrapper` create the session, call `close()` when you are done:

```python
client = WidgetClient()
try:
    widgets = client.list_widgets()
finally:
    client.close()
```

If you pass your own `requests.Session`, `ApiWrapper` uses it but does not own its shutdown.

## Good examples in this repo

- [JSONPlaceholder example](../../examples/jsonplaceholder_api/README.md)
- [NewsAPI example](../../examples/news_api/README.md)
- [Open-Meteo example](../../examples/weather_api/README.md)
