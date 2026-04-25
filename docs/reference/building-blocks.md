# Build From the Lower-Level Pieces

Use this path when you want PyperCache's storage, typing, or query layer without adopting `ApiWrapper` — for example, when you already have your own HTTP client, need custom cache keys or refresh rules, or only want part of the library.

## The manual fetch-or-cache pattern

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

This is the same flow `ApiWrapper` performs internally. Use it directly when you need control over transport, headers, retries, cache keys, or refresh policy.

## Querying a loaded record

`record.query` gives you a `JsonInjester` over the loaded payload without mutating it:

```python
record = cache.get("user:1")

print(record.data)
print(record.query.has("name"))
print(record.query.get("address.city", default_value="unknown"))
```

You can also instantiate `JsonInjester` directly over any dict or list:

```python
from pypercache.query import JsonInjester

q = JsonInjester(payload)
emails = q.get("users?email*")
```

See [JsonInjester selector syntax](./json-injester.md) for the full reference.

## `@apimodel` vs `@Cache.cached`

Use `@apimodel` when:

- your source data is a raw dict from an API
- you want aliases, timestamp parsing, lazy fields, or column transforms
- you want `from_dict()` and `as_dict()`

Use `@Cache.cached` when:

- you only need a lightweight class registration hook
- your class already knows how to accept the cached payload in its constructor

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

See [Typed models with @apimodel](./typed-models.md) for full decorator options.

## Logging without caching

`RequestLogger` is independent of `Cache`. Use it on its own if you only need request metadata:

```python
from pypercache import RequestLogger

log = RequestLogger("requests.log")
log.log(uri="/health", status=200)

for entry in log.get_logs_from_last_seconds(60):
    print(entry.data["uri"], entry.data["status"])
```
