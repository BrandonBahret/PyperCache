# Cache & CacheRecord

This document covers the two core classes: `Cache` (the main API) and `CacheRecord` (a single cached entry). For query navigation over a loaded record see [QUERY.md](QUERY.md). For backend choice and internals see [STORAGE.md](STORAGE.md).

---

## Cache

`Cache` is the entry point for all cache operations. Instantiate it with a filepath; the file extension determines which storage backend is used.

```python
from PyperCache import Cache

cache = Cache(filepath="api-cache.pkl")   # also: .json  .manifest  .db
```

If `filepath` is omitted, the default is `api-cache.pkl` in the current working directory.

### Storing a value

```python
cache.store(key, data, expiry=math.inf, cast=None)
```

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `key` | `str` | required | Unique identifier for this cache entry. |
| `data` | `dict` | required | The payload to cache. Must be a dict (JSON-like blob). |
| `expiry` | `int` or `float` | `math.inf` | Seconds until the record is considered stale. Omit for no expiry. |
| `cast` | `type` | `None` | A registered class to use when deserializing via `get_object`. |

`store` creates or overwrites. If you want to update only the data of an existing record without recreating it, use `update`.

### Checking freshness

```python
cache.has("key")            # True if a record exists (stale or fresh)
cache.is_data_fresh("key")  # True if a record exists AND has not expired
```

The common pattern before any network call:

```python
if not cache.is_data_fresh(key):
    response = fetch_from_api(...)
    cache.store(key, response, expiry=300)
```

### Retrieving values

`get` returns the raw `CacheRecord`:

```python
record = cache.get("key")
print(record.data)           # the raw dict
print(record.query.get("meta.total_hits"))  # navigate without mutating
```

Raises `KeyError` if the key is not present.

`get_object` returns a typed instance (requires `cast` to have been set on `store`):

```python
user_list = cache.get_object("users:v1")   # UserList instance
```

Raises `KeyError` if missing; raises `AttributeError` if no cast type is registered. Pass a `default_value` to suppress the `KeyError`:

```python
result = cache.get_object("users:v1", default_value=None)
```

### Updating a record in place

```python
cache.update("key", new_data_dict)
```

Replaces the data payload and refreshes the timestamp. The expiry and cast type are preserved. Raises `KeyError` if the record does not exist.

### Erasing everything

```python
cache.completely_erase_cache()
```

Permanently deletes all records from the backing store. Use with care — there is no undo.

---

## Typed round-trips with `@Cache.cached`

`@Cache.cached` is a class decorator that registers a class in the shared `ClassRepository`. Once registered, its name can be stored alongside a cache record and resolved back to the class at retrieval time.

```python
from PyperCache import Cache

@Cache.cached
class SearchResult:
    def __init__(self, hits=None, meta=None, **kwargs):
        self.hits = hits or []
        self.meta = meta or {}

cache = Cache(filepath="search.pkl")
cache.store(
    "search:v1:python",
    {"hits": [...], "meta": {"total": 42}},
    expiry=3600,
    cast=SearchResult,
)

result = cache.get_object("search:v1:python")
# result is a SearchResult instance: SearchResult(hits=[...], meta={...})
```

`@Cache.cached` uses a shared `ClassRepository` singleton. Keep this in mind in multi-process or isolated test environments — a class registered in one process is not visible to another.

### How the cast type is stored and resolved

`store` records the class's `__name__` string (`"SearchResult"`) alongside the payload. On `get_object`, `CacheRecord.cast` resolves that string back to the class via `ClassRepository`. If the class is not registered at retrieval time (e.g. in a fresh process that hasn't imported and decorated it), resolution raises `NameError`.

## Simple API models with `@apimodel`

For small, annotation-driven models you can use the lightweight `@apimodel` decorator which:
- registers the class with the shared `ClassRepository`,
- injects a constructor that accepts a raw `dict`, and
- provides `from_dict` and `as_dict` helpers.

Example:

```python
from PyperCache import Cache
from PyperCache.models.apimodel import apimodel

@apimodel
class User:
    id: int
    name: str
    email: str | None

cache = Cache(filepath="users.pkl")
raw = {"id": 1, "name": "Alice", "email": "alice@example.com"}

# store with the model as the cast type
cache.store("user:1", raw, expiry=3600, cast=User)

# retrieve a typed instance (constructor was injected by @apimodel)
user = cache.get_object("user:1")
print(user.name)          # Alice

# or construct directly from a dict
u2 = User.from_dict({"id": 2, "name": "Bob", "email": None})
print(u2.as_dict())       # original dict preserved
```

`@apimodel` is a convenient alternative to `@Cache.cached` when you prefer
annotation-driven hydration and the `from_dict`/`as_dict` helpers.
---

## CacheRecord

`CacheRecord` is what `cache.get()` returns. You rarely construct one directly.

### Core properties

| Property | Type | Description |
|----------|------|-------------|
| `.data` | `dict` | The cached payload. |
| `.timestamp` | `float` | Unix timestamp of when the record was stored or last updated. |
| `.expiry` | `float` | Seconds the record stays fresh (`math.inf` if none was set). |
| `.cast_str` | `str or None` | The registered class name, or `None`. |
| `.cast` | `type or None` | Lazily resolved class from `.cast_str`. Cached after first access. |
| `.is_data_stale` | `bool` | `True` if `now > timestamp + expiry`. |
| `.should_convert_type` | `bool` | `True` if `.cast` is a valid type. |

### The `query` property

```python
record = cache.get("search:v1:python")
q = record.query     # JsonInjester — see QUERY.md
total = q.get("meta.total")
staff = q.get("hits?role=staff")
```

`record.query` builds a `JsonInjester` over `.data` on first access and reuses it. It operates entirely in memory on the already-loaded dict — it never touches the storage backend. After calling `record.update(new_data)`, the injester is invalidated and rebuilt on next access.

### Updating a record directly

```python
record.update({"hits": [...], "meta": {"total": 7}})
```

Replaces `.data`, refreshes `.timestamp`, and invalidates the cached `query`. This is equivalent to `cache.update(key, data)` from the `Cache` level.

### Serialization

```python
d = record.as_dict()
```

Returns a plain dict safe for serialization. `math.inf` is encoded as the string `'math.inf'` so the record can survive JSON round-trips.

---

## Full lifecycle example

```python
from PyperCache import Cache

@Cache.cached
class OrgProfile:
    def __init__(self, name=None, members=None, **kw):
        self.name = name
        self.members = members or []

cache = Cache(filepath="org-cache.db")
key   = "org:acme"

# 1. Check freshness, fetch if stale
if not cache.is_data_fresh(key):
    payload = {"name": "Acme Corp", "members": [{"id": 1, "role": "admin"}]}
    cache.store(key, payload, expiry=1800, cast=OrgProfile)

# 2. Navigate the raw payload without mutating it
record = cache.get(key)
admin_members = record.query.get("members?role=admin")

# 3. Get a typed object
org = cache.get_object(key)   # OrgProfile instance

# 4. Update in place when new data arrives (preserves expiry and cast)
cache.update(key, {"name": "Acme Corp", "members": [{"id": 1, "role": "admin"}, {"id": 2, "role": "member"}]})

# 5. Check staleness directly on the record
if record.is_data_stale:
    print("Record has expired — re-fetch recommended.")
```
