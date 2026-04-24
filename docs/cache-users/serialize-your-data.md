# Serialize And Retrieve Data

`Cache` is the core persistence API in PyperCache.

The core persistence workflow is: write a payload by key, check whether it is fresh, and read it back. If you want typed round-trips, store with `cast=MyModel` and retrieve later with `get_object()`.

## Create a cache

```python
from pypercache import Cache

cache = Cache(filepath="app_cache.pkl")
```

If you omit `filepath`, PyperCache uses `api-cache.pkl` in the current working directory.

## Notebook-style quick walkthrough

This is the smallest realistic cache flow from the notebook:

```python
from pypercache import Cache

cache = Cache(filepath="demo.pkl")

cache.store("user:1", {"name": "Alice", "role": "admin"})
cache.store("user:2", {"name": "Bob", "role": "user"})
cache.store("user:3", {"name": "Charlie", "role": "user"})

record = cache.get("user:1")
print(record.data)
print(record.is_data_stale)
print(record.expiry)
```

## Store data

```python
cache.store(
    "settings",
    {"theme": "dark", "page_size": 100},
    expiry=3600,
)
```

- `key` is any string identifier
- `data` is the payload to persist
- `expiry` is in seconds
- `cast` is optional and only matters if you plan to call `get_object()`

## Retrieve data

`get()` always returns a `CacheRecord`:

```python
record = cache.get("settings")

print(record.data)
print(record.timestamp)
print(record.expiry)
print(record.is_data_stale)
```

If the key is missing, `get()` raises `KeyError`.

Access `.data` for the raw payload. Use `.query` when you want to inspect the loaded payload with `JsonInjester`.

## Freshness checks

The usual pattern is fetch-or-cache:

```python
key = "expensive-result"

if not cache.is_data_fresh(key):
    payload = run_expensive_work()
    cache.store(key, payload, expiry=300)

result = cache.get(key).data
```

`is_data_fresh(key)` returns `False` when:

- the key does not exist
- the record exists but its TTL has expired

Short TTL example:

```python
import time

cache.store("session:abc", {"token": "xyz"}, expiry=1)
print(cache.is_data_fresh("session:abc"))
time.sleep(1)
print(cache.is_data_fresh("session:abc"))
```

## Update an existing record

`update()` replaces the payload and refreshes the timestamp while preserving the original expiry and cast metadata.

```python
cache.update("settings", {"theme": "light", "page_size": 50})
```

If the key does not exist, `update()` raises `KeyError`.

Use `store()` instead when you do not know whether the record exists yet.

Notebook-style update and erase:

```python
cache.store("profile:1", {"name": "Alice", "role": "admin"})
cache.update("profile:1", {"name": "Alice (updated)", "role": "superadmin"})
print(cache.get("profile:1").data)

cache.completely_erase_cache()
print(cache.has("profile:1"))
```

## Check for existence

```python
if cache.has("settings"):
    print("settings already cached")
```

`has()` only checks existence. It does not care whether the record is stale.

## Typed round-trips

If you store a record with `cast=...`, you can retrieve it as an object later:

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

### Lightweight class registration with `@Cache.cached`

This is the same pattern shown in the notebook:

```python
from pypercache import Cache


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

### Nested typed hydration with `@apimodel`

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
print(u.company.address.city)
print(u.previous[0].city)
```

## Querying a loaded record

Every `CacheRecord` exposes a `JsonInjester` through `.query`:

```python
record = cache.get("settings")
print(record.query.get("theme"))
```

This works entirely in memory over the loaded payload. It does not query the backend itself.

Short example from the notebook's order walkthrough:

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

query = cache.get("order:sample").query
print(query.get("customer.name"))
print(query.get("items?name*"))
print(query.get("items?category=electronics"))
```

For full selector syntax, see [JsonInjester selector guide](../json-injester-users/selector-guide.md).

## Request logging alongside a cache

This is the lower-level version of what `ApiWrapper` does for you automatically:

```python
from pypercache import Cache, RequestLogger

cache = Cache(filepath="api_cache.db")
log = RequestLogger(filepath="api_requests.log")

key = "users:1"
if not cache.is_data_fresh(key):
    payload = {"id": 1, "name": "Ada"}
    status_code = 200
    log.log(uri="/users/1", status=status_code)
    cache.store(key, payload, expiry=300)
```

## Close behavior

Call `cache.close()` when you are done. It is safe to call on every backend. For SQLite-backed caches (`.db`), this always closes the connection cleanly and also flushes any pending writes if you enabled manual flush mode.

## SQLite flush behavior

For SQLite-backed caches:

- `cache.store()` flushes immediately by default
- `cache.update()` flushes immediately by default
- manual flush mode is opt-in

If you want to batch SQLite writes manually, enable manual flush mode:

```python
cache = Cache(filepath="app_cache.db")
cache.enable_manual_flush_mode()

cache.store("user:1", {"name": "Ada"})
cache.update("user:1", {"name": "Ada Lovelace"})

# Required in manual flush mode for writes to reach disk.
cache.flush()
cache.close()
```

Use `cache.disable_manual_flush_mode()` to return to immediate-flush writes. While manual flush mode is enabled, SQLite writes stay in memory until `flush()` or `close()` runs.

## Clear the cache

```python
cache.completely_erase_cache()
```

This removes every record from the underlying store.

## Closing the cache

For `.pkl`, `.json`, and `.manifest` backends, there is usually nothing special to do. For `.db`, call `cache.close()` before the process exits. In the default mode writes are already flushed on each `store()` and `update()`, but in manual flush mode `close()` is one of the operations that makes pending SQLite writes reach disk.

```python
cache.close()
```
