# Serialize and Retrieve Data

`Cache` is the core persistence API in PyperCache. The basic workflow is: write a payload by key, check whether it is fresh, and read it back. For typed round-trips, store with `cast=MyModel` and retrieve with `get_object()`.

## Create a cache

```python
from pypercache import Cache

cache = Cache(filepath="app_cache.pkl")
```

The backend is chosen automatically from the file extension. Omitting `filepath` defaults to `api-cache.pkl`. See [Choose a storage backend](./storage-backends.md) for extension options.

## Store data

```python
cache.store(
    "settings",
    {"theme": "dark", "page_size": 100},
    expiry=3600,
)
```

- `key` — any string identifier
- `data` — the payload to persist
- `expiry` — TTL in seconds (default: no expiry)
- `cast` — optional type for later retrieval via `get_object()`

`store()` creates or overwrites a record. If you know the record already exists and want to preserve its expiry and cast metadata, use `update()` instead.

## Retrieve data

`get()` always returns a `CacheRecord`:

```python
record = cache.get("settings")

print(record.data)          # raw payload
print(record.timestamp)     # Unix timestamp of last write
print(record.expiry)        # TTL in seconds
print(record.is_data_stale) # True if TTL has expired
```

If the key is missing, `get()` raises `KeyError`. Use `cache.has(key)` to check existence without fetching.

## Freshness checks

The typical fetch-or-cache pattern:

```python
key = "expensive-result"

if not cache.is_data_fresh(key):
    payload = run_expensive_work()
    cache.store(key, payload, expiry=300)

result = cache.get(key).data
```

`is_data_fresh(key)` returns `False` when the key does not exist or its TTL has expired. `has(key)` only checks existence — it does not consider staleness.

## Update an existing record

```python
cache.update("settings", {"theme": "light", "page_size": 50})
```

`update()` replaces the payload and refreshes the timestamp while preserving the original expiry and cast metadata. It raises `KeyError` if the key does not exist.

## Typed round-trips

### With `@apimodel`

```python
from pypercache import Cache
from pypercache.models.apimodel import apimodel


@apimodel(validate=True)
class User:
    id: int
    name: str


cache = Cache(filepath="users.db")
cache.store("user:1", {"id": 1, "name": "Ada"}, cast=User)

user = cache.get_object("user:1")
print(user.name)
cache.close()
```

If no cast was stored for that record, `get_object()` raises `AttributeError`.

### With `@Cache.cached`

Use this when you only need simple class registration with no field metadata:

```python
@Cache.cached
class UserProfile:
    def __init__(self, data: dict):
        self.name = data["name"]
        self.role = data["role"]


cache = Cache(filepath="profiles.pkl")
cache.store("profile:1", {"name": "Alice", "role": "admin"}, cast=UserProfile)

obj = cache.get_object("profile:1")
print(obj.name, obj.role)
```

### Nested typed hydration

```python
from pypercache.models.apimodel import apimodel


@apimodel
class Address:
    city: str

@apimodel
class Company:
    name: str
    address: Address

@apimodel
class User:
    id: int
    company: Company
    previous: list[Address]


cache.store(
    "u",
    {
        "id": 1,
        "company": {"name": "Microsoft", "address": {"city": "Redmond"}},
        "previous": [{"city": "Phoenix"}, {"city": "Tempe"}],
    },
    cast=User,
)

u = cache.get_object("u")
print(u.company.address.city)   # "Redmond"
print(u.previous[0].city)       # "Phoenix"
```

See [Typed models with @apimodel](./typed-models.md) for full decorator options.

## Querying a loaded record

Every `CacheRecord` exposes a `JsonInjester` through `.query` for in-memory inspection:

```python
record = cache.get("settings")
print(record.query.get("theme"))
```

```python
cache.store(
    "order:sample",
    {
        "customer": {"name": "Sarah Johnson"},
        "items": [
            {"name": "Laptop", "price": 999.99, "category": "electronics"},
            {"name": "Mouse", "price": 59.99, "category": "electronics"},
        ],
        "total": 1059.98,
    },
)

q = cache.get("order:sample").query
print(q.get("customer.name"))
print(q.get("items?name*"))
print(q.get("items?category=electronics"))
```

See [JsonInjester selector syntax](./json-injester.md) for the full selector reference.

## SQLite flush behavior

For SQLite-backed caches (`.db`), `store()` and `update()` flush to disk immediately by default.

To batch writes manually:

```python
cache = Cache(filepath="app_cache.db")
cache.enable_manual_flush_mode()

cache.store("user:1", {"name": "Ada"})
cache.update("user:1", {"name": "Ada Lovelace"})

cache.flush()   # required to reach disk in manual flush mode
cache.close()
```

Call `cache.disable_manual_flush_mode()` to return to immediate-flush writes.

## Lifecycle

```python
cache.completely_erase_cache()  # removes every record
cache.close()                   # required for .db; safe to call on any backend
```

For `.pkl`, `.json`, and `.manifest` backends, `close()` is a no-op. For `.db`, always call `close()` before the process exits.
