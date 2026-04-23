# PyperCache Docs

PyperCache is a durable, file-backed cache for JSON-like Python data.


## Features

- **API wrapper base class**: build synchronous `requests` clients with URL joining, optional caching, response decoding, file downloads, SSE parsing, and typed response casting
- **File-backed storage backends**: choose Pickle, JSON, chunked manifest, or SQLite storage by file extension (`.pkl`, `.json`, `.manifest`, `.db`)
- **Expiry-aware cache records**: store records with optional TTLs, check freshness, and refetch stale `ApiWrapper` GET/JSON responses instead of serving expired data
- **Typed API models**: decorate classes with `@apimodel` for dict constructors, nested hydration, raw field aliases, timestamp parsing, lazy fields, and optional validation
- **JSON navigation**: query loaded dict/list payloads with `JsonInjester` selectors for dotted paths, existence checks, filters, plucks, defaults, and casting
- **Request logging**: append thread-safe JSONL request records and inspect recent entries by time window

## Installation


Install from [PyPI](https://pypi.org/project/pypercache/):

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

See the full documentation, examples, and API reference:

Read the [docs webpage](https://brandonbahret.github.io/PyperCache/docs-index.html)

Find api wrapper [examples](https://github.com/BrandonBahret/PyperCache/tree/master/examples)

## At a glance

At the center is `Cache`, which stores keyed records to disk and returns `CacheRecord` objects. Each record exposes `.query`, which gives you a `JsonInjester` over the loaded payload so you can navigate nested data without writing long chains of `dict.get(...)` calls.

`@apimodel` sits on top of that. Decorate a class and it gains a dict-accepting constructor, nested hydration, aliases, timestamp parsing, and lazy fields. Store with `cast=MyModel`, then retrieve a typed object later with `cache.get_object()`.

`ApiWrapper` composes `requests`, `Cache`, and optionally `RequestLogger` into a higher-level base class for HTTP clients. Subclass it, add thin endpoint methods, and let the wrapper handle URL joining, cache lookup, response decoding, and model hydration.

## API Wrapper

`pypercache.api_wrapper.ApiWrapper` provides a base class for building small synchronous API clients on top of `requests`, `Cache`, and `RequestLogger`.

```python
from pypercache.api_wrapper import ApiWrapper
from pypercache.models.apimodel import apimodel


@apimodel
class Widget:
    id: int
    name: str


class WidgetClient(ApiWrapper):
    ...

    def list_widgets(self) -> list[Widget]:
        return self.request("GET", "/widgets", expected="json", cast=list[Widget])
```

## Example
 
The snippet below demonstrates every major feature in one pass: choosing a backend, TTL, typed objects, query navigation, and request logging.
 
```python
import math
from datetime import datetime
from typing import Annotated

from pypercache import Cache, RequestLogger
from pypercache.models.apimodel import Alias, Timestamp, apimodel
 
# ── 1. Backend is chosen by file extension ──────────────────────────────────
cache = Cache(filepath="api-cache.db")   # .pkl / .json / .manifest / .db
log   = RequestLogger("api_requests.log")
 
# ── 2. Define a typed model ──────────────────────────────────────────────────
@apimodel
class SearchResult:
    total: int
    next_page: Annotated[str | None, Alias("nextPage")]
    fetched_at: Annotated[datetime, Alias("fetchedAt"), Timestamp()]
    hits:  list
 
# ── 3. Fetch-or-cache pattern ────────────────────────────────────────────────
KEY = "search:v1:python"
 
if not cache.is_data_fresh(KEY):
    payload = {
        "total": 3,
        "nextPage": None,
        "fetchedAt": "2026-04-19T12:34:56Z",
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
print(result.next_page)                       # None
print(result.fetched_at.isoformat())          # 2026-04-19T12:34:56+00:00
 
# ── 5. Query without mutating the payload ───────────────────────────────────
q = cache.get(KEY).query
 
print(q.get("total"))                           # 3
print(q.get("hits?role=staff.name"))            # [Alice, Carol]
print(q.get("hits?name*"))                      # ['Alice', 'Bob', 'Carol']
print(q.get("hits?role=staff", select_first=True)["name"])  # 'Alice'

member: StaffMember = q.get("hits?role=staff", select_first=True, cast=StaffMember)
 
# ── 6. Inspect the request log ───────────────────────────────────────────────
for entry in log.get_logs_from_last_seconds(60):
    print(entry.data["uri"], entry.data["status"])
```

## License
 
MIT
