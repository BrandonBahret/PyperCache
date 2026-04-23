# Pypercache Wrapper Patterns

Use these repo-local examples as the primary implementation reference.

## Best Example To Copy First

- `examples/weather_api/openmeteo_wrapper.py`

This is the richest example in the repo. It demonstrates:

- `ApiWrapper` subclassing
- multi-origin APIs
- request logging and cache defaults
- `@apimodel(validate=True)`
- `Alias`
- `Timestamp`
- `Lazy`
- `Columns`
- wrapper-specific convenience methods
- returning composed helper objects instead of only raw endpoint responses

## Supporting Examples

- `examples/news_api/newsapi_wrapper.py`
  - API-key authentication in `get_session()`
  - simple typed nested models
  - endpoint-level validation logic
  - shared helper functions for query normalization

- `examples/jsonplaceholder_api/jsonplaceholder_wrapper.py`
  - lowest-complexity reference
  - small, thin endpoint methods
  - clear `POST` pattern with `use_cache=False`
  - straightforward nested models and aliases

## Constructor Pattern

Prefer this constructor shape:

```python
class ExampleClient(ApiWrapper):
    def __init__(
        self,
        *,
        cache_path: str | None = DEFAULT_CACHE_PATH,
        default_expiry: int | float = DEFAULT_EXPIRY_SECONDS,
        request_log_path: str | None = None,
        timeout: int | float | None = DEFAULT_TIMEOUT,
        session=None,
    ) -> None:
        super().__init__(
            origins={"default": BASE_URL},
            default_origin="default",
            cache_path=cache_path,
            default_expiry=default_expiry,
            request_log_path=request_log_path,
            timeout=timeout,
            session=session,
        )
```

For multi-host APIs, use named origins and pass `origin="..."` per request.

## Endpoint Method Pattern

Keep each endpoint method thin:

1. validate or normalize inputs
2. build `params`, `json_body`, or `data`
3. call `self.request(...)`
4. cast into typed output

Example pattern:

```python
def get_widget(self, widget_id: int) -> Widget:
    return self.request("GET", f"/widgets/{widget_id}", expected="json", cast=Widget)
```

## Session Customization

Override `get_session()` when the API needs:

- auth headers
- shared `Accept` headers
- a user agent
- retry adapters or other session-wide behavior

This is the default place to apply wrapper-wide authentication and header setup. The pattern should usually be:

```python
def get_session(self):
    session = super().get_session()
    session.headers.update({"Authorization": f"Bearer {self.api_key}"})
    return session
```

Prefer this approach over repeating auth data in individual endpoint methods. If the API uses a different auth flow, document that exception clearly in the wrapper code and generated markdown.

## Caching And Logging

Default to enabling both a cache path and optional request logging unless the API is highly volatile or the endpoint is clearly unsafe to cache.

- Cacheable reads: `GET` with `expected="json"` or `expected="auto"`
- Non-cacheable writes: `POST`, `PUT`, `PATCH`, `DELETE` should typically pass `use_cache=False`
- Per-endpoint TTLs should reflect the API's update frequency

## Model Scope

Define response models at module scope, not inside methods. This keeps casts stable and makes the wrapper easier to read and document.
