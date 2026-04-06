# Storage Backends & RequestLogger

This document covers how to choose and configure a storage backend, how the SQLite backend works under the hood, and how to use `RequestLogger` for operational audit trails.

---

## Choosing a backend

The backend is selected **automatically** from the file extension you pass to `Cache`. There is no other configuration needed — change the extension, change the backend. All four expose identical cache semantics (TTL, staleness, typed round-trips, `CacheRecord.query`).

```python
cache = Cache(filepath="api-cache.pkl")        # Pickle
cache = Cache(filepath="debug-cache.json")     # JSON
cache = Cache(filepath="my_store/chunks.manifest")  # Chunked manifest
cache = Cache(filepath="responses.db")         # SQLite
```

| Extension | Backend | Best for |
|-----------|---------|----------|
| `.pkl` | Pickle | Default choice. Single file, preserves Python-native types. No external dependency. Good for prototyping and scripts. |
| `.json` | JSON | Human-readable, diff-friendly. Rewrite the whole file on every save — keep small. Note: `set` values are stored as tuples; see [JSON caveats](#json-caveats) below. |
| `.manifest` | Chunked | Large or growing caches. Per-key persistence — only the changed chunk is rewritten, not the whole dataset. A manifest file tracks which chunk holds each key. |
| `.db` | SQLite | High-write workloads or concurrent access. Write-behind batching means many stores → one fsync. WAL mode keeps readers unblocked. |

---

## Pickle backend (`.pkl`)

Single-file, Python-native serialization. Entire mapping is loaded into memory on open and written back as a whole on every `store`. No external dependencies beyond the standard library.

```python
cache = Cache(filepath="scratch.pkl")
```

Good default for notebooks, scripts, and anything where the total number of keys stays manageable. Not human-readable. Pickle data is Python-version and class-definition sensitive — don't rely on `.pkl` files as long-term portable archives.

---

## JSON backend (`.json`)

Single-file, human-readable. The entire mapping is serialized as one JSON document on every save. Open it in an editor, diff it in version control, inspect it easily.

```python
cache = Cache(filepath="debug-cache.json")
```

### JSON caveats

The JSON backend uses standard JSON for simple data, falling back to jsonpickle for complex Python objects (like sets). This ensures serialization safety but may produce non-human-readable JSON for complex types. Use the `cast` parameter on `store` to ensure proper deserialization.

Avoid the JSON backend for caches that will grow large — every `store` call rewrites the entire file.

---

## Chunked manifest backend (`.manifest`)

Splits records across multiple chunk files on disk. A manifest file (the path you pass to `Cache`) records which chunk file holds each key. Only the chunk containing the modified key is rewritten on a `store` — there is no full-file rewrite.

```python
cache = Cache(filepath="my_store/chunks.manifest")
```

The manifest file and chunk files live in the same directory. The backing class is `ChunkedDictionary` in `PyperCache.storage`.

Use this when your cache has many keys or large payloads and you cannot afford to rewrite the whole dataset on every write. It is also the right choice when you want file-per-chunk granularity for backup or inspection purposes.

---

## SQLite backend (`.db`)

A single SQLite database file. Designed for high-write workloads with the best durability/throughput trade-off of all four backends.

```python
cache = Cache(filepath="responses.db")
```

### Schema

Each cache record occupies one row in a single `cache_records` table:

```
key        TEXT PRIMARY KEY
cast       TEXT          — type/cast metadata
expiry     REAL          — expiry (seconds)
timestamp  REAL          — Unix epoch of last write
data       BLOB          — serialized payload
```

### Write-behind buffer

The dominant cost in a naive SQLite backend is per-write `fsync`. This backend eliminates it with a write-behind dirty buffer:

1. **Hot read cache** — all records are loaded into memory on open. `get_record` is a pure O(1) dict lookup with zero disk IO.
2. **Dirty buffer** — `store_record` and `update_record` write into the in-memory dict and mark the key dirty. No disk IO until a flush is triggered.
3. **Batch flush** — all dirty keys are persisted in a single transaction (one `fsync` regardless of how many records changed). A flush is triggered by any of:
   - `DIRTY_FLUSH_THRESHOLD` dirty keys accumulated (default: 50)
   - `FLUSH_INTERVAL_SECONDS` elapsed (default: 5 s) — handled by a background daemon thread
   - Explicit `store.flush()` call
   - `store.close()` or context-manager `__exit__`

```python
from PyperCache.storage.sqlite_storage import SQLiteStorage

with SQLiteStorage("responses.db") as store:
    # ... work with the store directly ...
    pass   # close() flushes and checkpoints WAL on exit
```

### SQLite pragmas

The backend sets these on every connection:

| Pragma | Value | Reason |
|--------|-------|--------|
| `journal_mode` | `WAL` | Readers never block writers; writers never block readers. |
| `page_size` | `8192` | Larger pages suit big binary blobs. |
| `synchronous` | `NORMAL` | OS handles durability — no per-commit fsync. |
| `cache_size` | `-65536` (64 MB) | Reduces repeated page reads. |

### Data serialization ladder

The `data` BLOB column uses a three-tier encoding (first success wins):

| Condition | Encoding |
|-----------|----------|
| Plain JSON-serializable | UTF-8 JSON text |
| Dicts containing `bytes` etc. | `\x00` + msgpack bytes |
| Arbitrary Python objects | `\x01` + jsonpickle JSON |
| Raw `bytes` / `bytearray` | Stored as-is |

### Durability trade-off

A process crash between flushes can lose at most `FLUSH_INTERVAL_SECONDS` (default 5 s) of writes. For a cache this is always acceptable — a stale miss on restart is far cheaper than per-write fsync latency under load. If you need stronger guarantees, call `flush()` explicitly after writes you cannot afford to lose, or reduce `flush_interval` when constructing `SQLiteStorage` directly.

### Tunable constants

Import from `PyperCache.storage.sqlite_storage` if you need to override defaults:

```python
from PyperCache.storage.sqlite_storage import SQLiteStorage

store = SQLiteStorage("responses.db", flush_interval=1.0, dirty_threshold=10)
```

| Constant | Default | Effect |
|----------|---------|--------|
| `DIRTY_FLUSH_THRESHOLD` | `50` | Flush immediately when this many keys are dirty. |
| `FLUSH_INTERVAL_SECONDS` | `5.0` | Background flush cadence in seconds. |

---

## StorageMechanism — the abstract base

All four backends extend `StorageMechanism` (`PyperCache.storage.base`). The abstract hooks you implement to add a new backend are:

| Method | Responsibility |
|--------|---------------|
| `_impl__touch_store(filepath)` | Create an empty store if one does not exist. Return `True` on success. |
| `_impl__load(filepath)` | Deserialize all records from disk. Return a `MutableMapping[str, dict]`. |
| `_impl__save(records, filepath)` | Serialize the full mapping to disk. |
| `_impl__update_record(key, data)` | Merge `data` into an existing record and persist. |
| `_impl__erase_everything()` | Delete all records from the store. |

Public methods (`load`, `save`, `get_record`, `store_record`, `update_record`, `erase_everything`) all acquire a threading lock before delegating to the `_impl__*` hooks.

---

## RequestLogger

`RequestLogger` maintains an append-only log of API request metadata (URI and HTTP status code), completely separate from the cache. Use it alongside `Cache` when you want an operational audit trail.

```python
from PyperCache import RequestLogger

log = RequestLogger(filepath="api_requests.log")
```

If `filepath` is omitted, the default is `api_logfile.log` in the current working directory.

### Logging a request

```python
log.log(uri="/api/users", status=200)
log.log(uri="/api/health", status=503)
```

Each call appends one JSON object as a line (JSONL format) — an O(1) operation regardless of how many records already exist. Writes are protected by a threading lock; `RequestLogger` is safe to share across threads.

### Reading recent logs

```python
recent = log.get_logs_from_last_seconds(60)   # last 60 seconds, sorted oldest-first
for entry in recent:
    print(entry.data["uri"], entry.data["status"])
```

### `LogRecord`

Each entry in `.records` and in the list returned by `get_logs_from_last_seconds` is a `LogRecord`:

| Attribute | Type | Content |
|-----------|------|---------|
| `.timestamp` | `float` | Unix timestamp of the log entry. |
| `.data` | `dict` | `{"uri": ..., "status": ...}` |

```python
record = log.records[0]
print(repr(record))
# 06-04-2026 02:15:30,123456 PM - {'uri': '/api/users', 'status': 200}
```

### File format and migration

The log file is JSONL (one JSON object per line). If `RequestLogger` encounters a legacy file written as a single JSON array, it detects and migrates it transparently on load — rewriting it as JSONL in place.

### Full HTTP client workflow

```python
from PyperCache import Cache, RequestLogger

cache = Cache(filepath="api-bodies.json")
log   = RequestLogger("api_requests.log")

def fetch(url: str) -> dict:
    key = f"response:{url}"
    if cache.is_data_fresh(key):
        return cache.get(key).data

    response = call_http_api(url)   # your HTTP layer
    log.log(uri=url, status=response.status_code)
    cache.store(key, response.json(), expiry=300)
    return response.json()
```

---

## Caveats summary

**JSON backend** — uses jsonpickle fallback for complex objects, which may make the file non-human-readable. Rewrites the whole file on every save — keep caches small.

**SQLite backend** — understand the flush timing if maximum durability on every `store` matters. Call `flush()` explicitly or use a context manager to ensure no writes are lost.

**`record.query`** — runs in memory over a single loaded record. It is not SQL; it does not scan the backend or cross keys.

**`RequestLogger`** — log records are not linked to cache records. The logger stores only URI and status; response bodies live in `Cache`.
