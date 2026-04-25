# Build With ApiWrapper

`ApiWrapper` is the highest-level integration surface in PyperCache. Subclass it when you want a small HTTP client where endpoint methods stay thin and the base class handles HTTP, caching, and typed hydration.

## Constructor

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

`origins` is a named map of base URLs. `default_origin` selects which one `request()` uses unless overridden per-call. `cache_path=None` disables caching. `request_log_path=None` disables request logging.

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

Override `get_session()` to centralize headers, auth, retries, or adapters.

## What `request()` does

- joins relative paths against the selected origin
- removes `None` values from `params` and form `data`
- decodes JSON, text, bytes, or empty responses
- caches eligible `GET` responses
- hydrates return values with `cast=...`
- records request metadata when `request_log_path` is configured
- raises `ApiHTTPError` on HTTP 4xx and 5xx responses

## Caching rules

- only `GET` requests are cached
- only `expected="auto"` and `expected="json"` are cached
- stale entries are refetched, not served
- `use_cache=False` bypasses both lookup and writeback
- if `cache_path` is omitted, no caching occurs

Always pass `use_cache=False` for mutating requests (`POST`, `PUT`, `DELETE`).

## Endpoint recipes

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

### Multi-origin: per-request origin selection

```python
super().__init__(
    origins={
        "forecast": "https://api.open-meteo.com/v1",
        "geocode": "https://geocoding-api.open-meteo.com/v1",
    },
    default_origin="forecast",
    cache_path="weather_cache.db",
)

def search_places(self, query: str) -> GeocodingResults:
    return self.request(
        "GET",
        "/search",
        params={"name": query, "count": 5, "format": "json"},
        expected="json",
        cast=GeocodingResults,
        origin="geocode",   # override per call
    )
```

### API key authentication

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
```

## Other useful methods

### `download_to`

Write a bytes response directly to disk:

```python
report_path = client.download_to("/reports/today.pdf", "downloads/today.pdf")
```

### `stream_sse`

Parse a Server-Sent Events stream:

```python
for event in client.stream_sse("/events"):
    print(event.event, event.id, event.data)
```

This does not reconnect automatically and does not emulate browser `EventSource`.

## Error handling

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

```python
client = WidgetClient()
try:
    widgets = client.list_widgets()
finally:
    client.close()
```

`close()` closes the cache and the session when the wrapper created the session. If you pass your own `requests.Session`, the wrapper uses it but does not close it.
