# PyperCache

**Durable, file-backed caching** for JSON-like blobs — with TTL, staleness checks, optional typed round-trips, read-only path/filter queries over loaded payloads, and an append-only request log.

---

## What this is (and isn't)

`PyperCache` is **key → JSON-like value** storage. Each key holds a dict/list/tree you could round-trip through JSON (or pickle where needed). It is a **durable cache** — not a relational database, not a schema-enforced document store, not a multi-table data model.

**Use it for:** persistent caching of HTTP API responses or other service calls; lightweight request logging; reusing stored response-shaped blobs; optional domain-typed values via `@Cache.cached`.

**Don't use it for:** relational queries, enforced cross-key schemas, or as your authoritative structured datastore.

---

## Headline features

**Four pluggable backends** — pick the store by file extension. `.pkl` for zero-friction prototyping, `.json` for human-readable/diffable files, `.manifest` for large or growing caches (per-key writes, no full-file rewrites), `.db` for a SQLite file with write-behind batching and WAL concurrency.

**TTL and staleness** — every record carries a timestamp and an optional `expiry`. `is_data_fresh` tells you whether to re-fetch. Expiry defaults to `math.inf` (never stale).

**Typed domain objects** — decorate your class with `@Cache.cached`, pass `cast=MyClass` to `store()`, and `get_object()` hands you back a hydrated instance rather than a raw dict.

**Safe JSON navigation** — `record.query` exposes a `JsonInjester` over the loaded payload: dotted paths, `?key=value` match filters, `?key*` plucks, `?key` existence filters, `select_first`, defaults. All in memory — never touches the storage backend.

**Request logging** — `RequestLogger` appends one JSON object per line (JSONL), thread-safe, with time-window reads. Keeps an operational audit trail of URIs and status codes independent of cached bodies.

---

## Requirements

- Python 3.10 or newer
- Runtime dependencies are installed automatically when you install the package from PyPI.

Install from PyPI:

```bash
pip install pypercache
```

Read the full documentation on GitHub:

https://github.com/BrandonBahret/PyperCache/tree/master/docs

For development, install dev dependencies:

```bash
pip install -r requirements-dev.txt
```

Run the test suite (from the repository root; `pytest.ini` sets `pythonpath = .`):

```bash
pytest
```

---

## Quick start

```python
from PyperCache import Cache

cache = Cache(filepath="api-cache.pkl")   # .pkl / .json / .manifest / .db
cache.store("key", {"answer": 42}, expiry=300)

if cache.is_data_fresh("key"):
    print(cache.get("key").data)          # {'answer': 42}
```

Omit `filepath` and the default `api-cache.pkl` is used in the current working directory.

### Cache + request log together

```python
from PyperCache import Cache, RequestLogger

cache = Cache(filepath="api-bodies.json")
log   = RequestLogger("api_requests.log")

log.log("/v1/resource", 200)
recent = log.get_logs_from_last_seconds(120)
```

### Typed domain objects

```python
from PyperCache import Cache

@Cache.cached
class UserList:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

cache = Cache(filepath="responses.pkl")
key   = "users:v1"

if not cache.is_data_fresh(key):
    cache.store(key, {"users": [{"name": "Ada"}]}, expiry=3600, cast=UserList)

users = cache.get_object(key)   # UserList instance
```

---

## Package layout

| Module                 | Responsibility                                          | Go here when…                                          |
|------------------------|---------------------------------------------------------|--------------------------------------------------------|
| `PyperCache.core`      | `Cache`, `CacheRecord`, `RequestLogger`, `LogRecord`    | You use the main API or request logs.                  |
| `PyperCache.query`     | `JsonInjester`                                          | You need query parsing or use `JsonInjester` directly. |
| `PyperCache.storage`   | Backends and `get_storage_mechanism`                    | You inspect or extend how paths map to storage.        |
| `PyperCache.utils`     | Serialization, patterns, filesystem helpers             | You reuse serializers, class registry, or FS helpers.  |

Primary exports:

```python
from PyperCache import Cache, CacheRecord, LogRecord, RequestLogger
from PyperCache.query import JsonInjester
from PyperCache.storage import get_storage_mechanism
from PyperCache.utils import DataSerializer, PickleStore
```

---

## How the pieces fit together

1. Pass a `filepath` to `Cache`. The **file extension** selects the storage backend automatically.
2. `Cache` exposes `store`, `get`, `is_data_fresh`, `get_object`, `update`, and `completely_erase_cache`. TTL and cast semantics are identical across all backends.
3. `get` returns a `CacheRecord`. Its `.data` property holds the raw blob; its `.query` property wraps it in a `JsonInjester` for read-only navigation in memory over that single record.
4. `RequestLogger` is entirely separate. It appends JSONL lines and supports time-window reads. Use it alongside `Cache` when you want an audit trail of request metadata (URIs, status codes) independent of cached bodies.

---

## Detailed documentation

| Topic | Document |
|---|---|
| `Cache`, `CacheRecord`, TTL, typed objects | [CACHE.md](CACHE.md) |
| `JsonInjester` / `record.query` selector syntax | [QUERY.md](QUERY.md) |
| Storage backends, `RequestLogger`, SQLite internals | [STORAGE.md](STORAGE.md) |

---

## Development

Tests live under `tests/` and run with `pytest` from the repository root. Install dev dependencies with `pip install -r requirements-dev.txt`.
