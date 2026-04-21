# API Wrapper

`pypercache.api_wrapper` provides a sync-first base for building small HTTP API clients on top of `requests`, `Cache`, `RequestLogger`, and pypercache's existing type hydration utilities.

This page covers the `ApiWrapper` base class: what it gives you, how requests and caching behave, and how to structure a wrapper subclass. For the annotation-driven model system used with `cast=...`, see [APIMODEL.md](APIMODEL.md).

---

## What `ApiWrapper` is for

Use `ApiWrapper` when you want:

- one place for HTTP request behavior
- persistent caching for JSON `GET` responses
- optional request logging
- typed response hydration through `cast=...`
- a small amount of streaming support for SSE endpoints

It is intentionally a **sync** abstraction. v1 does not expose `async` / `await` APIs.

---

## Imports

```python
from pypercache.api_wrapper import ApiHTTPError, ApiWrapper, SSEEvent
```

These names are also re-exported from the package root:

```python
from pypercache import ApiHTTPError, ApiWrapper, SSEEvent
```

---

## Constructor

```python
ApiWrapper(
    base_url: str,
    cache_path: str | None = None,
    default_expiry: int | float = math.inf,
    enable_cache: bool = True,
    request_log_path: str | None = None,
    timeout: int | float | None = 10,
    session: requests.Session | None = None,
)
```

### Parameters

| Parameter | Description |
|---|---|
| `base_url` | Base URL joined with relative request paths. |
| `cache_path` | Optional cache file path. If omitted, request caching is disabled. |
| `default_expiry` | Default TTL, in seconds, for cacheable `GET` responses. |
| `enable_cache` | Global cache toggle for this wrapper instance. |
| `request_log_path` | Optional JSONL request log path. |
| `timeout` | Default request timeout used when a call does not override it. |
| `session` | Optional pre-built `requests.Session`. Pass one when you want full control over lifecycle/configuration. |

---

## Subclassing pattern

Most wrappers should keep endpoint methods thin and let `request()` handle transport details.

```python
from pypercache.api_wrapper import ApiWrapper
from pypercache.models.apimodel import apimodel


@apimodel
class Widget:
    id: int
    name: str


class WidgetClient(ApiWrapper):
    def get_session(self):
        session = super().get_session()
        session.headers.update({"User-Agent": "widget-client/1.0"})
        return session

    def list_widgets(self) -> list[Widget]:
        return self.request("GET", "/widgets", expected="json", cast=list[Widget])

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

---

## `request(...)`

`request()` is the main entry point for normal HTTP calls.

```python
def request(
    self,
    method: str,
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    json_body: Any = None,
    data: Mapping[str, Any] | None = None,
    files: Mapping[str, Any] | None = None,
    expected: str = "auto",
    use_cache: bool | None = None,
    timeout: int | float | None = None,
    headers: Mapping[str, str] | None = None,
    expiry: int | float | None = None,
    cast: type[Any] | None = None,
) -> Any:
```

### Key behaviors

1. Relative `path` values are joined against `base_url`.
2. Cache keys are built from wrapper identity, URL, method, query params, and JSON body.
3. Only `GET` requests with `expected="auto"` or `expected="json"` are cacheable.
4. Cache entries use the payload shape `{"value": decoded_response}`.
5. Non-JSON response modes like text and bytes are returned directly and are not cached in v1.
6. `cast=...` passes the decoded value through pypercache's existing `instantiate_type(...)` logic.

### `expected`

Supported response modes:

- `"auto"`: JSON when content type is JSON, text for `text/*`, otherwise bytes
- `"json"`: force `response.json()`
- `"text"`: return `response.text`
- `"bytes"`: return `response.content`

Empty bodies return `None`.

### `cast`

Use `cast` for typed responses:

```python
widget = client.request("GET", "/widgets/7", expected="json", cast=Widget)
widgets = client.request("GET", "/widgets", expected="json", cast=list[Widget])
```

For model design, aliases, timestamps, lazy fields, and `from_dict()` behavior, see [APIMODEL.md](APIMODEL.md).

---

## Caching behavior

Caching is meant for response-shaped JSON data, not for full HTTP semantics.

- cache lookup happens before the network call
- freshness is TTL-based via `default_expiry` or per-call `expiry`
- stale values are refetched, not served
- `use_cache=False` bypasses cache lookup and storage for that call
- if `cache_path` was omitted, no cache object is created

Typical pattern:

```python
client = WidgetClient(
    base_url="https://api.example.com",
    cache_path="widget-cache.pkl",
    default_expiry=300,
)
```

---

## Error handling

HTTP error responses raise `ApiHTTPError`.

```python
try:
    client.request("GET", "/widgets/missing", expected="json")
except ApiHTTPError as exc:
    print(exc.status_code)
    print(exc.url)
    print(exc.body)
```

`exc.body` is populated from `response.json()` when possible, otherwise from `response.text`.

---

## Downloads

Use `download_to()` for binary responses you want written directly to disk.

```python
path = client.download_to("/files/report.pdf", "downloads/report.pdf")
```

This is a thin wrapper around:

```python
client.request("GET", "/files/report.pdf", expected="bytes")
```

---

## Request logging

If `request_log_path` is provided, each request is recorded through `RequestLogger`.

```python
client = WidgetClient(
    base_url="https://api.example.com",
    request_log_path="api_requests.log",
)
```

Each log entry stores:

- `uri`
- `status`
- `timestamp`

For log internals and file format details, see [STORAGE.md](STORAGE.md).

---

## SSE streaming

`stream_sse()` is a low-level helper for caller-driven Server-Sent Events.

```python
for event in client.stream_sse("/stream"):
    print(event.event, event.id, event.data)
```

`SSEEvent` contains:

- `event`
- `data`
- `id`
- `retry`

v1 behavior:

- sends `Accept: text/event-stream`
- parses one event per blank-line-delimited block
- joins repeated `data:` lines with newline characters
- ignores comment lines that begin with `:`
- yields the final event even if the stream ends without a trailing blank line
- does not reconnect automatically
- does not emulate browser `EventSource`

---

## Session lifecycle

If you do not pass a session, `ApiWrapper` creates one through `get_session()` and `close()` will close it.

If you pass your own `requests.Session`, `ApiWrapper` uses it but does not take ownership of closing it.

```python
client = WidgetClient(base_url="https://api.example.com")
try:
    items = client.list_widgets()
finally:
    client.close()
```

---

## Notes and limitations

- v1 is intentionally sync-only
- cache invalidation is TTL-driven only
- text and bytes responses are not cached by default
- SSE support is parser-focused, not a full realtime client
- `ApiWrapper` is a base abstraction, not a generated SDK layer
