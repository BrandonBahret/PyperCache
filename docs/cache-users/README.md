# Cache Users

This section is for people who want durable file-backed caching without building an HTTP wrapper.

Use this path if your main goal is:

- persist Python data between runs
- avoid repeating expensive fetch or compute work
- add TTL-based freshness checks
- optionally hydrate cached payloads into Python objects later

The core workflow is simple: store a payload by key, check whether it is still fresh, and read it back. If you want typed round-trips, store with `cast=...` and retrieve later with `get_object()`.

## Start here

- [Serialize and retrieve data](./serialize-your-data.md)
- [Choose a storage backend](./storage-backends.md)

## What you need to know first

- `Cache` chooses its backend from the file extension.
- `cache.get(key)` returns a `CacheRecord`, not just the raw payload.
- `cache.get_object(key)` returns a typed object only if you stored the record with `cast=...`.
- `RequestLogger` is separate from `Cache`. Use it only if you want request audit logs.
- `cache.close()` is safe to call on every backend and matters most for SQLite, where it flushes pending writes.

## Smallest useful example

```python
from pypercache import Cache

cache = Cache(filepath="my_cache.json")

if not cache.is_data_fresh("settings"):
    cache.store("settings", {"theme": "light", "page_size": 50}, expiry=3600)

settings = cache.get("settings").data
print(settings["theme"])
```

## Choose this path when

- you want durable storage, not an HTTP client abstraction
- your cache keys come from your own application logic
- you need TTL checks around expensive local work or external fetches
- you may want `JsonInjester` on loaded payloads, but not a full wrapper
