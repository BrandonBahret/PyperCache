# Cache & CacheRecord

`Cache` is the primary API for storing and retrieving data. `CacheRecord` is the object returned by `Cache.get()`. For query navigation over a loaded record see [QUERY.md](QUERY.md). For backend selection and internals see [STORAGE.md](STORAGE.md).

---

## Cache

### Instantiation

```python
from pypercache import Cache

cache = Cache(filepath="api-cache.pkl")   # .pkl | .json | .manifest | .db
```

The file extension determines the storage backend. If `filepath` is omitted the default is `api-cache.pkl` in the current working directory. The file (and any parent directories) is created automatically if it does not exist.

---

### Methods

#### `store(key, data, expiry=math.inf, cast=None)`

Creates or overwrites a cache entry.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `key` | `str` | required | Unique identifier for the entry. |
| `data` | `dict` | required | JSON-like payload to cache. |
| `expiry` | `int \| float` | `math.inf` | Seconds until the record is considered stale. Omit for no expiry. |
| `cast` | `type` | `None` | Registered class used when retrieving via `get_object()`. |

To update the payload of an existing record without replacing it, use `update()` — it preserves the original expiry and cast type.

---

#### `get(key) → CacheRecord`

Returns the `CacheRecord` for `key`. Raises `KeyError` if the key is absent.

```python
record = cache.get("search:v1:python")
print(record.data)                         # raw dict
print(record.query.get("meta.total"))      # navigate without mutating
```

---

#### `get_object(key, default_value=UNSET) → object`

Returns a typed instance of the class registered via `cast` on `store()`. Raises `KeyError` if the key is absent (suppressed when `default_value` is provided). Raises `AttributeError` if no cast type is registered for this record.

```python
result = cache.get_object("users:v1")           # raises KeyError if missing
result = cache.get_object("users:v1", default_value=None)  # returns None
```

---

#### `has(key) → bool`

Returns `True` if a record exists for `key`, regardless of staleness.

---

#### `is_data_fresh(key) → bool`

Returns `True` if a record exists and has not exceeded its expiry. The standard guard before an expensive fetch:

```python
if not cache.is_data_fresh(key):
    response = fetch_from_api(...)
    cache.store(key, response, expiry=300)
```

---

#### `update(key, data)`

Replaces the data payload of an existing record and refreshes its timestamp. Preserves the original expiry and cast type. Raises `KeyError` if the key does not exist.

---

#### `completely_erase_cache()`

Permanently deletes all records from the backing store. There is no undo.

---

### Typed round-trips

#### `@Cache.cached`

A class decorator that registers a class in the shared `ClassRepository`. Once registered, its name is stored alongside a cache entry and resolved back to the class at retrieval time.

```python
from pypercache import Cache

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

result = cache.get_object("search:v1:python")   # SearchResult instance
```

`store()` records the class's `__name__` string. `get_object()` resolves it via `ClassRepository`. If the class is not registered at retrieval time (e.g. in a fresh process that has not imported it), resolution raises `NameError`.

> **Note:** `ClassRepository` is a singleton. A class registered in one process is not visible to another.

---

#### `@apimodel`

A lightweight alternative to `@Cache.cached` for annotation-driven models. It registers the class, injects a constructor that accepts a raw `dict`, and provides `from_dict()` / `as_dict()` helpers.
Annotated fields missing from the raw payload are set to the shared `UNSET` sentinel; explicit `None` values remain `None`.
Use `Alias(...)` inside `typing.Annotated` when the API payload uses a key that is not the Python attribute name. If an alias is present, that raw key is authoritative; a same-named field key is ignored.
Use `Timestamp(...)` inside `typing.Annotated` when a raw API timestamp should hydrate as a `datetime` field. It supports ISO 8601 strings, Unix timestamps, millisecond timestamps, and explicit `datetime.strptime` formats.

```python
from datetime import datetime
from pypercache import Cache
from typing import Annotated

from pypercache.models.apimodel import Alias, Timestamp, apimodel

@apimodel
class User:
    id:    int
    name:  Annotated[str, Alias("display_name")]
    plan:  Annotated[str, Alias("planCode")]
    joined_at: Annotated[datetime, Alias("joinedAt"), Timestamp()]
    email: str | None

cache = Cache(filepath="users.pkl")
cache.store(
    "user:1",
    {
        "id": 1,
        "display_name": "Alice",
        "planCode": "pro",
        "joinedAt": "2026-04-19T12:34:56Z",
        "email": "alice@example.com",
    },
    cast=User,
)

user = cache.get_object("user:1")
print(user.name)            # Alice
print(user.plan)            # pro
print(user.joined_at.isoformat())  # 2026-04-19T12:34:56+00:00

u2 = User.from_dict({
    "id": 2,
    "display_name": "Bob",
    "planCode": "free",
    "joinedAt": 1776602096,
    "email": None,
})
print(u2.as_dict())
```

Aliases also work with lazy fields:

```python
from typing import Annotated

from pypercache.models.apimodel import Alias, apimodel
from pypercache.models.lazy import Lazy

@apimodel
class Profile:
    timezone: str

@apimodel
class UserWithProfile:
    profile: Lazy[Annotated[Profile, Alias("profile_v2")]]

user = UserWithProfile({"profile_v2": {"timezone": "America/Phoenix"}})
print(user.profile.timezone)  # America/Phoenix
```

---

## CacheRecord

`CacheRecord` is returned by `cache.get()`. It is rarely constructed directly.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `.data` | `dict` | The cached payload. |
| `.timestamp` | `float` | Unix timestamp of the last `store()` or `update()`. |
| `.expiry` | `float` | Seconds until stale (`math.inf` if no expiry was set). |
| `.cast_str` | `str \| None` | Registered class name, or `None`. |
| `.cast` | `type \| None` | Lazily resolved class from `.cast_str`; cached after first access. |
| `.is_data_stale` | `bool` | `True` when `now > timestamp + expiry`. |
| `.should_convert_type` | `bool` | `True` when `.cast` resolves to a valid type. |

### `.query`

Returns a `JsonInjester` over `.data`. Built once on first access and reused. Operates entirely in memory — it never touches the storage backend. Invalidated and rebuilt after `record.update()`.

```python
record = cache.get("search:v1:python")
total  = record.query.get("meta.total")
staff  = record.query.get("hits?role=staff")
```

See [QUERY.md](QUERY.md) for the full selector syntax.

### `.update(data)`

Replaces `.data`, refreshes `.timestamp`, and invalidates the cached query injester. Equivalent to calling `cache.update(key, data)` from the `Cache` level.

### `.as_dict()`

Returns a plain dict safe for serialization. `math.inf` is encoded as the string `'math.inf'` for JSON compatibility.

---

## Lifecycle example

```python
from pypercache import Cache

@Cache.cached
class OrgProfile:
    def __init__(self, name=None, members=None, **kw):
        self.name    = name
        self.members = members or []

cache = Cache(filepath="org-cache.db")
key   = "org:acme"

# 1. Fetch only when stale
if not cache.is_data_fresh(key):
    payload = {"name": "Acme Corp", "members": [{"id": 1, "role": "admin"}]}
    cache.store(key, payload, expiry=1800, cast=OrgProfile)

# 2. Navigate the raw payload
record = cache.get(key)
admins = record.query.get("members?role=admin")

# 3. Retrieve a typed instance
org = cache.get_object(key)   # OrgProfile

# 4. Update in place (preserves expiry and cast)
cache.update(key, {"name": "Acme Corp", "members": [
    {"id": 1, "role": "admin"},
    {"id": 2, "role": "member"},
]})

# 5. Check staleness
if record.is_data_stale:
    print("Record expired — re-fetch recommended.")
```
