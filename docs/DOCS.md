# PyperCache — Documentation

## What PyperCache is (and isn't)

PyperCache is **key → JSON-like value** storage. Each key holds a dict, list, or nested tree that can round-trip through JSON (or pickle where needed). It is a durable cache — not a relational database, not a schema-enforced document store, not a multi-table data model.

**Use it for** persistent caching of HTTP API responses or other service calls; lightweight request logging; reusing stored response-shaped blobs; optional domain-typed values via `@Cache.cached`.

**Don't use it for** relational queries, enforced cross-key schemas, or as your authoritative structured datastore.

---

## How the pieces fit together

```
Cache(filepath="…")
│
│  extension → storage backend (.pkl / .json / .manifest / .db)
│
├── store(key, data, expiry, cast)   writes a CacheRecord to the backend
├── get(key)          → CacheRecord
│       ├── .data     → raw dict payload
│       └── .query    → JsonInjester (in-memory, read-only navigation)
├── get_object(key)   → typed instance via registered cast class
├── is_data_fresh(key)
├── has(key)
├── update(key, data)
└── completely_erase_cache()

RequestLogger(filepath="…")          independent of Cache
├── log(uri, status)                 append-only JSONL write
└── get_logs_from_last_seconds(n)    time-window read
```

1. The **file extension** passed to `Cache` selects the backend automatically. TTL, staleness, and typed round-trip semantics are identical across all four backends.
2. `get()` returns a `CacheRecord`. Its `.data` holds the raw blob; its `.query` wraps it in a `JsonInjester` for read-only navigation — entirely in memory, never touching the backend.
3. `RequestLogger` is entirely separate. Use it alongside `Cache` when you need an audit trail of request metadata (URIs, status codes) independent of cached bodies.

---

## Package layout

| Module | Responsibility | Go here when… |
|--------|---------------|---------------|
| `pypercache.core` | `Cache`, `CacheRecord`, `RequestLogger`, `LogRecord` | You use the main API or request logs. |
| `pypercache.query` | `JsonInjester` | You need query parsing or use `JsonInjester` directly. |
| `pypercache.storage` | Backends and `get_storage_mechanism` | You inspect or extend how paths map to storage. |
| `pypercache.utils` | Serialization, patterns, filesystem helpers | You reuse serializers, the class registry, or FS helpers. |

Primary exports:

```python
from pypercache import Cache, CacheRecord, LogRecord, RequestLogger
from pypercache.query import JsonInjester
from pypercache.storage import get_storage_mechanism
from pypercache.utils import DataSerializer, PickleStore
```

---

## Documentation index

### [CACHE.md](CACHE.md) — Cache, CacheRecord, TTL, typed objects

The core API. Read this first.

- Instantiation and backend selection
- `store`, `get`, `get_object`, `has`, `is_data_fresh`, `update`, `completely_erase_cache`
- TTL and staleness semantics
- Typed round-trips with `@Cache.cached` and `@apimodel`
- `CacheRecord` properties and the `.query` accessor
- Full lifecycle example

### [QUERY.md](QUERY.md) — JsonInjester / record.query

The selector language for navigating a loaded payload in memory.

- Obtaining a `JsonInjester` (via `record.query` or directly)
- Dot-separated path navigation
- `?key=value` match filter — returns elements where a key equals a value
- `?key*` pluck — extracts a field from every element in a list
- `?key` exists filter — gates on key presence without extracting values
- `select_first`, `default_value`, `cast` parameters
- `has()` existence check
- `root` and `default_tail` constructor parameters
- Known limitations

### [STORAGE.md](STORAGE.md) — Storage backends & RequestLogger

Backend internals, trade-offs, and extension.

- Choosing a backend by file extension
- Pickle, JSON, chunked manifest, and SQLite backend details
- SQLite write-behind buffer, WAL pragmas, data serialization ladder, and durability trade-offs
- `StorageMechanism` abstract base — hooks for implementing a custom backend
- Step-by-step guide to adding a new backend (with a full YAML example)
- `RequestLogger` — `log()`, `get_logs_from_last_seconds()`, `LogRecord`, file format

---

## Quick reference

### Fetch-or-cache

```python
from pypercache import Cache

cache = Cache(filepath="api-cache.pkl")   # .pkl / .json / .manifest / .db

KEY = "resource:v1"
if not cache.is_data_fresh(KEY):
    cache.store(KEY, fetch_from_api(), expiry=300)

data = cache.get(KEY).data
```

### Typed objects

```python
from pypercache import Cache

@Cache.cached
class UserList:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

cache.store("users:v1", {"users": [{"name": "Ada"}]}, expiry=3600, cast=UserList)
users = cache.get_object("users:v1")   # UserList instance
```

### Query navigation

```python
q = cache.get("users:v1").query

q.get("users?name*")                          # pluck all names
q.get("users?role=admin")                     # filter by value
q.get("users?role=admin", select_first=True)  # first match only
q.get("meta.total", default_value=0)          # safe path with default
q.has("meta.cursor")                          # existence check
```

### Request logging

```python
from pypercache import RequestLogger

log = RequestLogger("api_requests.log")
log.log(uri="/v1/resource", status=200)

for entry in log.get_logs_from_last_seconds(120):
    print(entry.data["uri"], entry.data["status"])
```

---

## Development

Tests live under `tests/` and run with `pytest` from the repository root. `pytest.ini` sets `pythonpath = .` so no install is required during development.

```bash
pip install -r requirements-dev.txt
pytest
```
