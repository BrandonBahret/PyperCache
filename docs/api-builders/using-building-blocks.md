# Build From The Lower-Level Pieces

Use this path when you want PyperCache's storage, typing, or query layer without adopting `ApiWrapper`.

The main building blocks are:

- `Cache`
- `RequestLogger`
- `@apimodel`
- `JsonInjester`

Choose this path when you already have your own HTTP client abstraction, need custom cache keys or refresh rules, want to cache non-request work, or only need part of PyperCache instead of the full wrapper.

## Common pattern

This is the manual fetch-or-cache flow:

```python
import requests

from pypercache import Cache, RequestLogger
from pypercache.models.apimodel import apimodel


@apimodel(validate=True)
class User:
    id: int
    name: str
    email: str


cache = Cache(filepath="users_cache.db")
log = RequestLogger(filepath="users_requests.log")

key = "user:1"
if not cache.is_data_fresh(key):
    response = requests.get("https://api.example.com/users/1", timeout=10)
    response.raise_for_status()
    payload = response.json()
    log.log(uri=response.url, status=response.status_code)
    cache.store(key, payload, expiry=300, cast=User)

user = cache.get_object(key)
print(user.name)

cache.close()
```

This gives you the same durable caching model as `ApiWrapper`, but you stay in control of transport, headers, retries, cache keys, and refresh policy.

## When this path works well

- you already have an HTTP client abstraction
- you need custom cache keys
- you want to cache non-request work
- you want to inspect cached payloads with `JsonInjester`
- you only want some PyperCache features, not the whole wrapper layer

## Manual query navigation

Once a record is loaded, `record.query` lets you inspect it without mutating the payload:

```python
record = cache.get("user:1")

print(record.data)
print(record.query.has("name"))
print(record.query.get("address.city", default_value="unknown"))
```

You can also instantiate `JsonInjester` directly when the data never touches `Cache`:

```python
from pypercache.query import JsonInjester

q = JsonInjester(payload)
emails = q.get("users?email*")
```

## Choosing between `@apimodel` and `@Cache.cached`

Use `@apimodel` when:

- your source data is a raw dict from an API
- you want aliases, timestamps, lazy fields, or column transforms
- you want `from_dict()` and `as_dict()`

Use `@Cache.cached` when:

- you only need a lightweight class registration hook
- your class already knows how to accept the cached payload in its constructor

Example:

```python
from pypercache import Cache


@Cache.cached
class SearchResult:
    def __init__(self, hits=None, total=0, **kwargs):
        self.hits = hits or []
        self.total = total


cache = Cache(filepath="search.pkl")
cache.store("search:python", {"hits": [], "total": 0}, cast=SearchResult)
result = cache.get_object("search:python")
```

## Logging without caching

`RequestLogger` is independent. You can use it even if you are not storing bodies:

```python
from pypercache import RequestLogger

log = RequestLogger("requests.log")
log.log(uri="/health", status=200)

for entry in log.get_logs_from_last_seconds(60):
    print(entry.data["uri"], entry.data["status"])
```

## Mental model

`ApiWrapper` is a convenience layer over this exact pattern. If you can explain your flow as "fetch if stale, log if needed, store, then hydrate or query later", the lower-level pieces are often enough.

## Next reads

- [Typed models with `@apimodel`](./typed-models.md)
- [Serialize and retrieve data](../cache-users/serialize-your-data.md)
- [JsonInjester selector guide](../json-injester-users/selector-guide.md)
