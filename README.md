# PyperCache

A Python library providing durable file-backed caching for JSON-like data with pluggable storage backends (pickle, JSON, chunked manifest, SQLite), optional TTL and staleness semantics, read-only query navigation, and append-only request logging.

## Installation

```bash
pip install pypercache
```

Or install from source:

```bash
git clone https://github.com/BrandonBahret/PyperCache.git
cd PyperCache
pip install .
```

## Quick Start

See the full documentation, examples, and API reference on GitHub:

https://github.com/BrandonBahret/PyperCache/tree/master/docs

## Features

- **Pluggable Backends**: Choose storage by file extension (.pkl, .json, .manifest, .db)
- **TTL & Staleness**: Optional expiry and acceptable staleness windows
- **Typed Objects**: Decorate classes for automatic serialization/deserialization
- **Query Navigation**: Safe, read-only JSON path queries with filters
- **Request Logging**: Thread-safe JSONL audit trails

## Testing

```bash
pytest
```

## Example
 
The snippet below demonstrates every major feature in one pass: choosing a backend, TTL, typed objects, query navigation, and request logging.
 
```python
import math
from pypercache import Cache, RequestLogger
from pypercache.models.apimodel import apimodel
 
# ── 1. Backend is chosen by file extension ──────────────────────────────────
cache = Cache(filepath="api-cache.db")   # .pkl / .json / .manifest / .db
log   = RequestLogger("api_requests.log")
 
# ── 2. Define a typed model ──────────────────────────────────────────────────
@apimodel
class SearchResult:
    total: int
    hits:  list
 
# ── 3. Fetch-or-cache pattern ────────────────────────────────────────────────
KEY = "search:v1:python"
 
if not cache.is_data_fresh(KEY):
    payload = {
        "total": 3,
        "hits": [
            {"name": "Alice", "role": "staff",  "score": 92},
            {"name": "Bob",   "role": "guest",  "score": 74},
            {"name": "Carol", "role": "staff",  "score": 88},
        ],
    }
    cache.store(KEY, payload, expiry=3600, cast=SearchResult)
    log.log(uri="/api/search?q=python", status=200)
 
# ── 4. Retrieve a typed object ───────────────────────────────────────────────
result: SearchResult = cache.get_object(KEY)  # SearchResult instance
print(result.total)                           # 3
 
# ── 5. Query without mutating the payload ───────────────────────────────────
q = cache.get(KEY).query
 
print(q.get("total"))                           # 3
print(q.get("hits?role=staff.name"))            # [Alice, Carol]
print(q.get("hits?name*"))                      # ['Alice', 'Bob', 'Carol']
print(q.get("hits?role=staff", select_first=True)["name"])  # 'Alice'
 
# ── 6. Inspect the request log ───────────────────────────────────────────────
for entry in log.get_logs_from_last_seconds(60):
    print(entry.data["uri"], entry.data["status"])
```
 
## Features
 
- **Four backends** — `.pkl`, `.json`, `.manifest`, `.db` (SQLite with write-behind batching)
- **TTL & staleness** — per-record expiry; `is_data_fresh` tells you whether to re-fetch
- **Typed round-trips** — `@Cache.cached` / `@apimodel` + `cast=` on store; `get_object()` on retrieval
- **Query navigation** — dotted paths, `?key=value` filters, `?key*` plucks, `?key` existence, `select_first`, defaults; all in memory over the loaded record
- **Request logging** — thread-safe JSONL audit trail with time-window reads
 
---

## Query navigation
 
`record.query` returns a `JsonInjester` — a lightweight, read-only selector language that runs in memory over the loaded payload. It never touches the storage backend.
 
```python
q = cache.get("search:v1:python").query
```
 
You can also instantiate it directly over any dict:
 
```python
from pypercache.query import JsonInjester
q = JsonInjester({"meta": {"total": 5}, "hits": [...]})
```
 
### Path navigation
 
Dot-separated keys walk the dict. Returns `UNSET` if any key along the path is absent.
 
```python
q.get("meta.total")          # 5
q.get("meta.page")           # 1
q.get("meta.missing")        # UNSET
q.has("meta.total")          # True  (shorthand for `get(...) is not UNSET`)
```
 
Keys containing hyphens or other non-identifier characters must be wrapped in double quotes inside the selector string:
 
```python
q.get('"content-type".value')
```
 
### `?key=value` — match filter
 
Returns every element in a list where the key equals the value. A tail path after the operator plucks a field from each matched element.
 
```python
q.get("hits?role=staff")
# [{"name": "Alice", ...}, {"name": "Carol", ...}]
 
q.get("hits?role=staff.name")
# ["Alice", "Carol"]
 
q.get("hits?team.name=Engineering")
# all dicts where hits[i].team.name == "Engineering"
```
 
Prefix the value with `#` to match numbers instead of strings:
 
```python
q.get("hits?score=#92")    # integer match
q.get("hits?ratio=#0.75")  # float match
```
 
No matches returns an empty list, not `UNSET`.
 
### `?key*` — pluck
 
Extracts a field from every element in the list. Non-missing results are collected; missing ones are silently skipped. Plucks can be chained.
 
```python
q.get("hits?name*")
# ["Alice", "Bob", "Carol"]
 
q.get("hits?team.name*")
# ["Engineering", "Marketing", "Engineering"]
 
q.get("hits?role*?label*")
# chained: pluck role objects, then pluck label from each
```
 
On a dict cursor (rather than a list), pluck navigates to the key and returns its value or `UNSET`.
 
### `?key` — exists filter
 
Does not extract values. On a list cursor, returns only elements that contain the key. On a dict cursor, returns the cursor unchanged if the key is present, or `UNSET` if absent.
 
```python
# list cursor — filter to elements that have a "team" key
q.get("hits?team")
 
# dict cursor — gate on key presence
q.get("meta?total")          # returns the meta dict (key exists)
q.get("meta?ghost")          # UNSET
q.get("meta?ghost", default_value=0)  # 0
```
 
### `select_first` and `default_value`
 
`select_first=True` unwraps the first element of a list result. Returns `UNSET` if the list is empty.
 
```python
from pypercache.query.json_injester import UNSET
 
first = q.get("hits?role=staff", select_first=True)
print(first["name"])   # "Alice"
 
empty = q.get("hits?role=contractor", select_first=True)
print(empty is UNSET)  # True
```
 
`default_value` is returned when the path is missing or resolves to `None`. Falsy non-`None` values (`False`, `0`, `""`) pass through unchanged.
 
```python
q.get("meta.missing", default_value=0)   # 0
q.get("flags.debug", default_value=False) # False (returned as-is, not default)
```
 
### `cast`
 
When the result is a dict, `cast` passes it to the given type before returning.
 
```python
q.get("hits?role=staff", select_first=True, cast=StaffMember)
# StaffMember instance
```
 
### Known limitations
 
`JsonInjester` is intentionally scoped and simple. A few things it does not do:
 
- **Integer list indexing** — `"hits.0.name"` is not supported. Use a filter or pluck to reach list elements.
- **Cross-key queries** — `record.query` operates on a single loaded payload. It does not scan multiple records or touch the backend.
- **Non-ASCII keys** — unquoted non-ASCII key names raise a parse error. Wrap them in double quotes: `'"héros".name'`.
 
For the complete selector reference see [QUERY.md](QUERY.md).
 
---
 
## Documentation
 
| Topic | File |
|---|---|
| `Cache`, `CacheRecord`, TTL, typed objects | [CACHE.md](CACHE.md) |
| `JsonInjester` / `record.query` selector syntax | [QUERY.md](QUERY.md) |
| Storage backends, `RequestLogger`, SQLite internals | [STORAGE.md](STORAGE.md) |
 
Full docs and examples: https://github.com/BrandonBahret/PyperCache/tree/master/docs
 
## License
 
MIT
