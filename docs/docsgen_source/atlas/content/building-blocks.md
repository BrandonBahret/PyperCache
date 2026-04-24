---

tag: API clients

comment: BUILDING BLOCKS

title: Lower-level

title_em: "pieces"

lead: |

  Bring your own HTTP transport and compose only the PyperCache parts you need: `Cache{ref=ref-cache#cache}`, `RequestLogger{ref=ref-storage#request-logger}`, `@apimodel{ref=ref-apimodel#decorator}`, and `JsonInjester{ref=json-injester#standalone-usage}`.

breadcrumb: "pypercache / lower-level pieces"

---



:::callout info
**When to use this path:** You already have an HTTP client abstraction, need custom cache keys or refresh rules, want to cache non-request work, or only need parts of PyperCache — not the full wrapper.
:::

## Manual fetch-or-cache

This is the core pattern — everything `ApiWrapper.request(){ref=ref-apiwrapper#request}` automates, written explicitly.

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

## Navigating a loaded record

```python
record = cache.get("user:1")
print(record.query.has("name"))
print(record.query.get("address.city", default_value="unknown"))
```

## @apimodel vs @Cache.cached

Use `@apimodel{ref=ref-apimodel#decorator}` when you want aliases, timestamps, lazy fields, or column transforms. Use `@Cache.cached{ref=ref-cache#cache-cached}` when you only need lightweight class registration — your class already knows how to accept the cached payload.

```python
@Cache.cached
class SearchResult:
    def __init__(self, hits=None, total=0, **kwargs):
        self.hits = hits or []
        self.total = total

cache.store("search:python", {"hits": [], "total": 0}, cast=SearchResult)
result = cache.get_object("search:python")
```

## Using RequestLogger standalone

```python
from pypercache import RequestLogger

log = RequestLogger("requests.log")
log.log(uri="/health", status=200)

for entry in log.get_logs_from_last_seconds(60):
    print(entry.data["uri"], entry.data["status"])
```
