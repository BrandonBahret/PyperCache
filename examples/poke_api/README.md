# PokeAPI Wrapper — Instructional Example

A self-contained Python project demonstrating four patterns every developer
should master when consuming REST APIs:

| Pattern | Where it lives |
|---|---|
| **Caching with TTL** | `pokeapi_wrapper.py` — `Cache`, `store(expiry=N)`, `is_data_fresh()` |
| **Hydrated data models** | `pokeapi_wrapper.py` — `@Cache.cached` + `from_dict()` + `cast=` |
| **Soft rate-limiting** | `pokeapi_wrapper.py` — `SoftRateLimiter` (token-bucket, sleep-based) |
| **Automated background refresh** | `pokeapi_wrapper.py` — `_refresh_loop()` daemon thread |

The API being consumed is **[PokeAPI v2](https://pokeapi.co)** — the gold
standard teaching API: free, no authentication, rich relational data,
well-documented, and forgiving of beginners.

---

## Quick start

```bash
pip install -r requirements.txt
python app.py
```

Delete `pokeapi_demo_cache.pkl` and re-run to see network fetches; keep it to
see cache hits.

---

## Project layout

```
pokedex_example/
├── pokeapi_wrapper.py   ← The library (wrapper + models + rate-limiter)
├── app.py               ← Demo application
├── requirements.txt
└── README.md
```

---

## Pattern 1 — Caching with PyperCache

### Why cache API responses?

Every HTTP round-trip adds latency and burns rate-limit quota.  If the data
doesn't change between calls (Pokémon stats are effectively static), returning
a locally stored copy is both faster and kinder to the upstream server.

### How PyperCache works

```
Cache(filepath="x.pkl")
  │
  ├─ .store(key, data, expiry=N, cast=MyClass)
  │     Writes data to the file.  expiry is TTL in *seconds*.
  │     cast= tells PyperCache which class to use when reconstructing
  │     the value later — think of it as a type annotation for stored data.
  │
  ├─ .is_data_fresh(key) → bool
  │     True  →  key exists AND its age < expiry.  Use this to gate network calls.
  │     False →  missing, or expired.
  │
  ├─ .get_object(key) → instance of cast class
  │     Reconstructs the stored dict into the registered type.
  │     Only works if cast= was provided at store time.
  │
  ├─ .get(key) → CacheRecord
  │     Raw record with .data, .is_data_stale, .query accessor.
  │
  └─ .has(key) → bool
        True if the key exists at all (even if stale).
```

### Cache-first fetch pattern

```python
def get_pokemon(self, identifier):
    key = self._make_key("pokemon", identifier)

    if self._cache.is_data_fresh(key):      # ← check freshness
        return self._cache.get_object(key)  # ← serve from cache

    data = self._fetch(f"{BASE_URL}/pokemon/{identifier}")  # ← network
    return self._store_and_return(key, data, Pokemon, TTL_POKEMON)  # Pokemon class and TTL_POKEMON constant are defined in pokeapi_wrapper.py
```

This pattern appears identically for `get_move()` and `get_ability()`.
Copy it any time you add a new endpoint.

### Choosing TTL values

| Resource type | Suggested TTL | Reasoning |
|---|---|---|
| Pokémon stats | inf | Static; game data doesn't change |
| Move metadata | inf | Same — only new game releases change it |
| Paginated lists | inf | Names/URLs are stable |
| User-specific data | 30–60 seconds | Changes more often |
| Live scores / prices | 5–30 seconds | Near real-time |

---

## Pattern 2 — Hydrated data models

### Why not just return dicts?

Raw JSON dicts are error-prone: typos in string keys silently return `None`,
there's no autocomplete, and the shape is invisible to type checkers.  A
dataclass gives you attribute access, `__str__`, and makes the contract
explicit.

### The `@Cache.cached` decorator

```python
@Cache.cached   # registers Pokemon in PyperCache's ClassRepository
@dataclass
class Pokemon:
    id: int
    name: str
    ...
    @classmethod
    def from_dict(cls, data: dict) -> "Pokemon":
        return cls(id=data["id"], name=data["name"], ...)
```

`@Cache.cached` tells PyperCache "this class can be the target of cast=".
Without it, `get_object()` wouldn't know how to reconstruct the instance.

### Storing with a type

```python
self._cache.store(key, data, expiry=ttl, cast=Pokemon)
```

The `cast=Pokemon` parameter is stored alongside the data.  On retrieval:

```python
instance = self._cache.get_object(key)
# → calls Pokemon.from_dict(stored_data) internally
type(instance)   # <class 'Pokemon'>
instance.name    # "pikachu"  — attribute access, no ["name"] key lookup
```

### The `CacheRecord.query` accessor

For ad-hoc reads without going through the model:

```python
record = cache.get("pokemon:pikachu")
record.query.get("base_experience")          # nested key
record.query.get("stats?stat.name=hp")       # filter a list
record.query.has("sprites")                  # existence check
record.query.get("missing", default_value=0) # safe default
```

---

## Pattern 3 — Soft rate-limiting

### Hard vs. soft

| Approach | Behaviour when over limit |
|---|---|
| **Hard** | Raises `RateLimitError`; caller must retry |
| **Soft** | Sleeps until a token is available; caller never notices |

Soft limiting is appropriate when you control the call rate and want the
application to *just work* without retry logic.

### Token-bucket implementation

```python
class SoftRateLimiter:
    def __init__(self, max_rps=5):
        self._min_gap   = 1.0 / max_rps   # 0.2 s between requests at 5 rps
        self._last_call = 0.0
        self._lock      = threading.Lock()

    def acquire(self):
        with self._lock:
            wait = self._min_gap - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
```

Every public method calls `self._limiter.acquire()` before firing HTTP:

```python
def _fetch(self, url):
    self._limiter.acquire()   # ← single choke-point
    response = self._session.get(url, timeout=10)
    response.raise_for_status()
    return response.json()
```

Centralising rate-limiting in `_fetch()` means you can never accidentally
bypass it by calling `requests.get()` directly elsewhere in the class.

---

## Pattern 4 — Automated background refresh

### The problem

A cache entry fetched at startup will eventually go stale.  Two strategies:

1. **Lazy refresh** — refresh on next *read* (the cache-first pattern above).
   Simple, but the first caller after expiry gets a slow response.

2. **Eager / background refresh** — a daemon thread proactively re-fetches
   stale entries before anyone asks for them.  Callers always get fast cache hits.

This project implements **both**: lazy refresh is the default path;
`start_auto_refresh()` adds eager refresh on top.

### How the refresh loop works

```python
def _refresh_loop(self):
    # threading.Event.wait(timeout) replaces time.sleep():
    # it returns immediately if stop_event is set, enabling clean shutdown.
    while not self._stop_event.wait(timeout=REFRESH_INTERVAL):
        self._refresh_stale()

def _refresh_stale(self):
    for key, (fetch_fn, args, _ttl) in list(self._key_registry.items()):
        if not self._cache.is_data_fresh(key):
            fetch_fn(*args)   # re-uses the same public getter → rate-limit respected
```

The **key registry** (`self._key_registry`) maps every cache key to the
function call needed to refresh it.  It's populated lazily: the first time
`get_pokemon("pikachu")` is called, `"pokemon:pikachu"` is registered.

### Thread safety notes

* `threading.Lock` in `SoftRateLimiter` protects `_last_call` from races
  when multiple threads call `acquire()` concurrently.
* `list(self._key_registry.items())` snapshots the dict before iterating,
  avoiding "dictionary changed size during iteration" errors if the main
  thread registers a new key mid-refresh.
* PyperCache's file-backed storage is safe for single-process use.  For
  multi-process scenarios, switch to a Redis or SQLite backend.

---

## Extending the wrapper

### Adding a new endpoint

```python
# 1. Define a data model
@Cache.cached
@dataclass
class Berry:
    id: int
    name: str
    growth_time: int

    @classmethod
    def from_dict(cls, data):
        return cls(id=data["id"], name=data["name"],
                   growth_time=data["growth_time"])

# 2. Add a getter following the cache-first pattern
def get_berry(self, identifier):
    key = self._make_key("berry", identifier)
    if self._cache.is_data_fresh(key):
        return self._cache.get_object(key)
    data = self._fetch(f"{BASE_URL}/berry/{identifier}")
    self._key_registry[key] = (self.get_berry, (identifier,), 3600)
    return self._store_and_return(key, data, Berry, 3600)
```

That's it.  Caching, hydration, rate-limiting, and auto-refresh all come
for free.

---

## PokeAPI quick reference

| Endpoint | Example |
|---|---|
| Single Pokémon | `GET /api/v2/pokemon/pikachu` |
| By national dex id | `GET /api/v2/pokemon/25` |
| Move | `GET /api/v2/move/thunderbolt` |
| Ability | `GET /api/v2/ability/static` |
| Type | `GET /api/v2/type/electric` |
| Paginated list | `GET /api/v2/pokemon?limit=20&offset=0` |
| Evolution chain | `GET /api/v2/evolution-chain/10` |

Base URL: `https://pokeapi.co/api/v2`  
Authentication: none required  
Rate limit: no hard limit; fair-use policy applies
