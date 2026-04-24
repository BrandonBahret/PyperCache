---

tag: Cache users

title: Store & retrieve

title_em: "data"

lead: |

  The core persistence workflow: write a payload by key, check whether it's fresh, and read it back — with optional typed hydration via `@apimodel{ref=ref-apimodel#decorator}`.

breadcrumb: "pypercache / store & retrieve data"

---



## Create a cache

Pass a file path. The extension determines which storage backend is used.

```python
from pypercache import Cache

cache = Cache(filepath="app_cache.pkl")
```

Omit `filepath` and it defaults to `api-cache.pkl` in the working directory.

## Store and read

```python
cache.store("user:1", {"name": "Alice", "role": "admin"})
cache.store("user:2", {"name": "Bob", "role": "user"}, expiry=3600)

record = cache.get("user:1")
print(record.data)          # the raw payload
print(record.is_data_stale) # False — no expiry set
print(record.expiry)        # inf
```

`get(){ref=ref-cache#get}` always returns a `CacheRecord{ref=ref-cache#cache-record}`. Access `.data{ref=ref-cache#attributes}` for the raw payload. It raises `KeyError` if the key doesn't exist.

## TTL and freshness

The typical pattern is fetch-or-cache: check freshness, run the expensive work if stale, then read from cache.

```python
key = "expensive-result"

if not cache.is_data_fresh(key):
    payload = run_expensive_work()
    cache.store(key, payload, expiry=300)

result = cache.get(key).data
```

`is_data_fresh(){ref=ref-cache#is-data-fresh}` returns `False` when the key doesn't exist or the record's TTL has elapsed. It never throws.

## Updating a record

`update(){ref=ref-cache#update}` replaces the payload and refreshes the timestamp while keeping the original expiry and any `cast{ref=ref-cache#store}` metadata intact.

```python
cache.update("settings", {"theme": "light", "page_size": 50})
```

:::callout warn
**Note:** `update(){ref=ref-cache#update}` raises `KeyError` if the key doesn't exist. Use `store(){ref=ref-cache#store}` when you don't know whether the key is there yet.
:::

## Typed round-trips

Store a record with `cast=MyModel` and retrieve it as a fully hydrated object using `get_object(){ref=ref-cache#get-object}`.

```python
from pypercache.models.apimodel import apimodel

@apimodel(validate=True)
class User:
    id: int
    name: str

cache.store("user:1", {"id": 1, "name": "Ada"}, cast=User)

user = cache.get_object("user:1")
print(user.name)  # "Ada"

cache.close()
```

:::callout info
**Tip:** Always call `cache.close(){ref=ref-cache#close}` when using SQLite (`.db{ref=ref-storage#backend-selection}`). In the default mode writes are already flushed on `store(){ref=ref-cache#store}` and `update(){ref=ref-cache#update}`; in manual flush mode `close(){ref=ref-cache#close}` flushes pending writes. It's a no-op for other backends, so it's safe to call regardless.
:::

## Querying the payload inline

Every `CacheRecord{ref=ref-cache#cache-record}` exposes a `JsonInjester{ref=json-injester#standalone-usage}` via `.query{ref=ref-cache#attributes}`, so you can navigate the stored data without a separate extraction step.

```python
cache.store("order:1", {
    "customer": {"name": "Sarah Johnson"},
    "items": [
        {"name": "Laptop", "price": 999.99, "category": "electronics"},
        {"name": "Mouse", "price": 59.99, "category": "electronics"},
    ],
})

q = cache.get("order:1").query
print(q.get("customer.name"))
print(q.get("items?name*"))
print(q.get("items?category=electronics"))
```

## Clearing the cache

```python
cache.completely_erase_cache()
print(cache.has("user:1"))  # False
```
