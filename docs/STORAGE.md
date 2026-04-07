# Storage Backends & RequestLogger

This document covers backend selection, backend-specific behavior and trade-offs, how to implement a custom backend, and how to use `RequestLogger` for operational audit trails.

---

## Choosing a backend

The backend is selected automatically from the file extension passed to `Cache`. No additional configuration is required — switching backends means changing the filename extension.

```python
cache = Cache(filepath="api-cache.pkl")             # Pickle
cache = Cache(filepath="debug-cache.json")          # JSON
cache = Cache(filepath="my_store/chunks.manifest")  # Chunked manifest
cache = Cache(filepath="responses.db")              # SQLite
```

All four backends expose identical cache semantics: TTL, staleness, typed round-trips, and `CacheRecord.query`.

| Extension | Backend | Best for |
|-----------|---------|----------|
| `.pkl` | Pickle | Default choice. Single file, Python-native types, no external dependencies. Well-suited for prototyping and scripts. |
| `.json` | JSON | Human-readable and diff-friendly. Rewrites the whole file on every save — keep caches small. |
| `.manifest` | Chunked | Large or growing caches. Only the changed chunk is rewritten, not the whole dataset. |
| `.db` | SQLite | High-write workloads or concurrent access. Write-behind batching and WAL mode. |

---

## Backend reference

### Pickle (`.pkl`)

Single-file, Python-native serialization. The entire mapping is loaded into memory on open and written back as a whole on every `store()`. No external dependencies.

Appropriate for notebooks, scripts, and caches with a manageable number of keys. Not human-readable. Pickle data is sensitive to Python version and class definition changes — do not rely on `.pkl` files as long-term portable archives.

---

### JSON (`.json`)

Single-file, human-readable. The entire mapping is serialized as one JSON document on every save, making it easy to open in an editor or diff in version control.

For complex Python objects that are not natively JSON-serializable (e.g. `set`), the backend falls back to `jsonpickle`, which may produce non-human-readable output. Use the `cast` parameter on `store()` to ensure correct deserialization of such values.

Avoid this backend for caches that will grow large — every `store()` rewrites the entire file.

---

### Chunked manifest (`.manifest`)

Splits records across multiple chunk files on disk. A manifest file (the path passed to `Cache`) tracks which chunk holds each key. Only the chunk containing the modified key is rewritten on `store()`.

```python
cache = Cache(filepath="my_store/chunks.manifest")
```

The manifest file and its chunk files reside in the same directory. The backing class is `ChunkedDictionary` in `PyperCache.storage`.

Use this backend when the cache has many keys or large payloads and a full-file rewrite on every write is unacceptable.

---

### SQLite (`.db`)

A single SQLite database file designed for high-write workloads.

```python
cache = Cache(filepath="responses.db")
```

#### Schema

Each cache entry occupies one row in the `cache_records` table:

| Column | Type | Description |
|--------|------|-------------|
| `key` | `TEXT PRIMARY KEY` | Cache key. |
| `cast` | `TEXT` | Type / cast metadata. |
| `expiry` | `REAL` | Expiry in seconds. |
| `timestamp` | `REAL` | Unix epoch of last write. |
| `data` | `BLOB` | Serialized payload. |

#### Write-behind buffer

All records are loaded into memory on open. `get_record()` is a pure O(1) dict lookup with zero disk IO. Writes go into an in-memory dirty buffer and are flushed in a single transaction (one `fsync`) when any of the following occurs:

- `DIRTY_FLUSH_THRESHOLD` dirty keys accumulate (default: 50)
- `FLUSH_INTERVAL_SECONDS` elapses (default: 5 s) — handled by a background daemon thread
- `store.flush()` is called explicitly
- `store.close()` or context-manager `__exit__` is called

```python
from PyperCache.storage.sqlite_storage import SQLiteStorage

with SQLiteStorage("responses.db") as store:
    # close() flushes and checkpoints WAL on exit
    pass
```

#### SQLite pragmas

| Pragma | Value | Reason |
|--------|-------|--------|
| `journal_mode` | `WAL` | Readers and writers do not block each other. |
| `page_size` | `8192` | Better suited for large binary blobs. |
| `synchronous` | `NORMAL` | OS handles durability; no per-commit `fsync`. |
| `cache_size` | `-65536` (64 MB) | Reduces repeated page reads. |

#### Data serialization

The `data` BLOB column uses a three-tier encoding (first successful tier wins):

| Condition | Encoding |
|-----------|----------|
| Plain JSON-serializable | UTF-8 JSON text |
| Dicts containing `bytes` etc. | `\x00` + msgpack bytes |
| Arbitrary Python objects | `\x01` + jsonpickle JSON |
| Raw `bytes` / `bytearray` | Stored as-is |

#### Durability trade-off

A process crash between flushes can lose at most `FLUSH_INTERVAL_SECONDS` (default 5 s) of writes. For a cache this is generally acceptable — a stale miss on restart is far cheaper than per-write `fsync` latency under load. Call `flush()` explicitly after writes that must not be lost, or reduce `flush_interval` when constructing `SQLiteStorage` directly.

#### Tunable constants

```python
from PyperCache.storage.sqlite_storage import SQLiteStorage

store = SQLiteStorage("responses.db", flush_interval=1.0, dirty_threshold=10)
```

| Parameter | Default | Effect |
|-----------|---------|--------|
| `dirty_threshold` | `50` | Trigger an immediate flush when this many keys are dirty. |
| `flush_interval` | `5.0` | Background flush cadence in seconds. |

---

## StorageMechanism — the abstract base

All four backends extend `StorageMechanism` (`PyperCache.storage.base`). Public methods (`load`, `save`, `get_record`, `store_record`, `update_record`, `erase_everything`) acquire a threading lock before delegating to the `_impl__*` abstract hooks.

| Abstract method | Responsibility |
|----------------|---------------|
| `_impl__touch_store(filepath)` | Create an empty store if one does not exist. Return `True` on success. |
| `_impl__load(filepath)` | Deserialize all records from disk. Return a `MutableMapping[str, dict]`. |
| `_impl__save(records, filepath)` | Serialize the full mapping to disk. |
| `_impl__update_record(key, data)` | Merge `data` into an existing record and persist. |
| `_impl__erase_everything()` | Delete all records from the store. |

---

## Implementing a custom backend

### 1. Subclass `StorageMechanism`

Create a new class in `PyperCache/storage/` that inherits from `StorageMechanism` and implements all abstract methods:

```python
from pathlib import Path
from typing import MutableMapping
from PyperCache.storage.base import StorageMechanism

class MyCustomStorage(StorageMechanism):

    def _impl__touch_store(self, filepath: Path) -> bool:
        # Create the backing store if it does not exist. Return True on success.
        ...

    def _impl__load(self, filepath: Path) -> MutableMapping[str, dict]:
        # Deserialize all records from disk and return them.
        ...

    def _impl__save(self, cache_records_dict: dict, filepath: Path):
        # Write the full records dict to persistent storage.
        ...

    def _impl__update_record(self, key: str, data: dict):
        # Merge data into the existing record for key and persist.
        ...

    def _impl__erase_everything(self):
        # Remove all records from the backing store.
        ...
```

The base class handles thread safety. Your implementations do not need to acquire locks.

### 2. Register the backend

Add the new extension and class to `_EXTENSION_TO_STORAGE` in `PyperCache/storage/factory.py`:

```python
_EXTENSION_TO_STORAGE: dict = {
    ".manifest": ChunkedStorage,
    ".json":     JSONStorage,
    ".pkl":      PickleStorage,
    ".db":       SQLiteStorage,
    ".myformat": MyCustomStorage,   # add your backend here
}
```

### 3. Add tests and documentation

Follow the pattern of existing backend tests in `tests/test_storage.py`. Add your backend to the table in the "Choosing a backend" section of this document.

### Example: YAML backend

```python
import yaml
from pathlib import Path
from PyperCache.storage.base import StorageMechanism

class YAMLStorage(StorageMechanism):

    def _impl__touch_store(self, filepath: Path) -> bool:
        filepath.touch(exist_ok=True)
        return True

    def _impl__load(self, filepath: Path) -> dict:
        content = filepath.read_text().strip()
        return yaml.safe_load(content) if content else {}

    def _impl__save(self, cache_records_dict: dict, filepath: Path):
        filepath.write_text(yaml.dump(cache_records_dict, default_flow_style=False))

    def _impl__update_record(self, key: str, data: dict):
        self.records[key].update(data)
        self.save(self.records)

    def _impl__erase_everything(self):
        self.records = {}
        self.save(self.records)
```

Register it, then use it like any other backend:

```python
# factory.py
_EXTENSION_TO_STORAGE[".yaml"] = YAMLStorage

# application code
cache = Cache(filepath="my_cache.yaml")
```

---

## RequestLogger

`RequestLogger` maintains an append-only JSONL log of request metadata (URI and HTTP status code), independent of the cache. Use it alongside `Cache` when you need an operational audit trail.

```python
from PyperCache import RequestLogger

log = RequestLogger(filepath="api_requests.log")
```

If `filepath` is omitted, the default is `api_logfile.log` in the current working directory.

### `log(uri, status)`

Appends one JSON object as a line (JSONL). An O(1) operation regardless of how many records already exist. Writes are protected by a threading lock — `RequestLogger` is safe to share across threads.

```python
log.log(uri="/api/users",  status=200)
log.log(uri="/api/health", status=503)
```

### `get_logs_from_last_seconds(seconds) → list[LogRecord]`

Returns log entries from the last `seconds` seconds, sorted oldest-first.

```python
recent = log.get_logs_from_last_seconds(60)
for entry in recent:
    print(entry.data["uri"], entry.data["status"])
```

### LogRecord

| Attribute | Type | Description |
|-----------|------|-------------|
| `.timestamp` | `float` | Unix timestamp of the log entry. |
| `.data` | `dict` | `{"uri": ..., "status": ...}` |

```python
record = log.records[0]
print(repr(record))
# 06-04-2026 02:15:30,123456 PM - {'uri': '/api/users', 'status': 200}
```

### File format

The log file is JSONL (one JSON object per line). If `RequestLogger` encounters a legacy file written as a single JSON array, it detects and migrates it transparently on load, rewriting it as JSONL in place.

### Usage alongside Cache

```python
from PyperCache import Cache, RequestLogger

cache = Cache(filepath="api-bodies.json")
log   = RequestLogger("api_requests.log")

def fetch(url: str) -> dict:
    key = f"response:{url}"
    if cache.is_data_fresh(key):
        return cache.get(key).data

    response = call_http_api(url)
    log.log(uri=url, status=response.status_code)
    cache.store(key, response.json(), expiry=300)
    return response.json()
```

> **Note:** `RequestLogger` stores only URI and status code. Response bodies live in `Cache`. The two are not linked.

---

## Caveats summary

| Backend / feature | Caveat |
|---|---|
| JSON backend | Falls back to `jsonpickle` for non-JSON-serializable types, which may produce non-human-readable output. Rewrites the whole file on every `store()` — keep caches small. |
| SQLite backend | Writes may be lost if the process crashes between flushes (up to `flush_interval` seconds). Call `flush()` explicitly or use a context manager when durability is required. |
| `record.query` | Operates in memory over a single loaded record. Not SQL; does not scan the backend or cross keys. |
| `RequestLogger` | Log records are not linked to cache records. The logger stores only URI and status; response bodies live in `Cache`. |