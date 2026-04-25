# Choose a Storage Backend

The cache backend is determined entirely by the file extension passed to `Cache(filepath=...)`. The cache API is identical across all backends.

```python
Cache(filepath="cache.pkl")      # Pickle
Cache(filepath="cache.json")     # JSON
Cache(filepath="cache.manifest") # Chunked storage
Cache(filepath="cache.db")       # SQLite
```

## Quick comparison

| Extension | Backend | Best for |
|---|---|---|
| `.pkl` | Pickle | Simplest default. General-purpose. |
| `.json` | JSON | Human-readable files; small caches. |
| `.manifest` | Chunked storage | Many keys or large payloads; avoids full-file rewrites. |
| `.db` | SQLite | Regular writes, growing caches, concurrent access. |

## Pickle (`.pkl`)

Simple and Python-native. Rewrites the full store on every save. Not human-readable and not suitable as a portable long-term archive. Start here unless you have a specific reason not to.

## JSON (`.json`)

Human-readable and easy to inspect during debugging. Like Pickle, it rewrites the full store on every save. Complex objects may fall back to `jsonpickle`, which is not always human-friendly. Not ideal for large caches.

## Chunked storage (`.manifest`)

Stores records across multiple pickle chunk files with a manifest file alongside them. Only the affected chunk is rewritten on each write, making it more efficient than Pickle or JSON for large caches. Backed by a directory rather than a single file.

## SQLite (`.db`)

The most operationally robust backend. Records are loaded into memory on open and writes use WAL mode.

By default, `store()` and `update()` flush to disk immediately. Manual flush mode is available when you want to batch writes:

```python
cache = Cache(filepath="app_cache.db")
cache.enable_manual_flush_mode()

cache.store("user:1", {"name": "Ada"})
cache.update("user:1", {"name": "Ada Lovelace"})

cache.flush()   # writes reach disk
cache.close()
```

Always call `cache.close()` before the process exits when using SQLite.

## Request logging is separate

`RequestLogger` writes to its own file and does not depend on the cache backend:

```python
from pypercache import RequestLogger

log = RequestLogger("requests.log")
log.log(uri="/v1/items", status=200)
```

See [Storage and logging reference](../reference/storage-and-logging.md) for the full API.
