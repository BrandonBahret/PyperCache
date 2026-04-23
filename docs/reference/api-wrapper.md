# ApiWrapper Reference

## Imports

```python
from pypercache.api_wrapper import ApiHTTPError, ApiWrapper, ApiWrapperError, SSEEvent
```

These are also re-exported from `pypercache`.

## Constructor

```python
ApiWrapper(
    *,
    origins: Mapping[str, str],
    default_origin: str,
    cache_path: str | None = None,
    default_expiry: int | float = math.inf,
    enable_cache: bool = True,
    request_log_path: str | None = None,
    timeout: int | float | None = 10,
    session: requests.Session | None = None,
)
```

Notes:

- `origins` must be non-empty
- `default_origin` must exist in `origins`
- `cache_path=None` disables caching entirely
- `request_log_path=None` disables request logging

## Main methods

### `get_session`

```python
client.get_session() -> requests.Session
```

Override this to centralize headers, auth, retries, or adapters.

### `request`

```python
client.request(
    method,
    path,
    *,
    params=None,
    json_body=None,
    data=None,
    files=None,
    expected="auto",
    use_cache=None,
    timeout=None,
    headers=None,
    expiry=None,
    cast=None,
    origin=None,
)
```

Behavior:

- joins relative paths against the selected origin
- supports `expected="auto"`, `"json"`, `"text"`, and `"bytes"`
- caches only `GET` requests with `expected="auto"` or `expected="json"`
- only caches values that can be represented as JSON-like data
- hydrates the decoded result when `cast` is provided
- raises `ApiHTTPError` for HTTP error responses

### `download_to`

```python
client.download_to(
    path,
    destination,
    *,
    params=None,
    use_cache=False,
    timeout=None,
    headers=None,
    origin=None,
)
```

Downloads a bytes response and writes it to `destination`.

### `stream_sse`

```python
client.stream_sse(
    path,
    *,
    params=None,
    data=None,
    timeout=None,
    headers=None,
    method="GET",
    origin=None,
) -> Iterator[SSEEvent]
```

Parses a Server-Sent Events stream into `SSEEvent` objects.

### `close`

```python
client.close()
```

- closes the cache if present
- closes the session only when the wrapper created it

## Exceptions and support types

### `ApiWrapperError`

Base exception for wrapper-related failures.

### `ApiHTTPError`

Raised on HTTP 4xx and 5xx responses.

Attributes:

- `status_code`
- `url`
- `body`

### `SSEEvent`

Frozen dataclass with:

- `event`
- `data`
- `id`
- `retry`
