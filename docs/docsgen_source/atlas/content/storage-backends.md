---

tag: Cache users

comment: STORAGE BACKENDS

title: Storage

title_em: "backends"

lead: |

  The backend is selected purely from the file extension. The cache API is identical across all of them.

breadcrumb: "pypercache / storage backends"

---



```python
Cache(filepath="cache.pkl")      # Pickle — default
Cache(filepath="cache.json")     # JSON — human-readable
Cache(filepath="cache.manifest") # Chunked — large stores
Cache(filepath="cache.db")       # SQLite — best write behavior
```

## Quick comparison

:::table
| Extension | Backend | Best for |
| --- | --- | --- |
| .pkl | **Pickle** | Default choice. Simple, fast, Python-native serialization. Rewrites the whole file on save. |
| .json | **JSON** | Human-readable files you want to inspect or diff. Not great for large caches — full rewrite on every save. |
| .manifest | **Chunked** | Many keys or large payloads. Per-chunk rewrites instead of full-file rewrites. Backed by a directory, not a single file. |
| .db | **SQLite** | Frequent writes, growing caches, concurrent access. WAL mode with batched flushes — the most operationally robust option. |
:::

## SQLite specifics

SQLite loads all rows into memory on open and uses WAL mode. For `Cache{ref=ref-cache#cache}`, `store(){ref=ref-cache#store}` and `update(){ref=ref-cache#update}` flush immediately by default. Manual flush mode is opt-in; when enabled, writes stay in memory until `flush(){ref=ref-storage#sqlite-storage}` or `close(){ref=ref-storage#sqlite-storage}` runs. Prefer using it as a context manager:

```python
from pypercache.storage import SQLiteStorage

with SQLiteStorage("cache.db") as store:
    ...
```

Or just call `cache.close(){ref=ref-cache#close}` before your process exits — that's what `ApiWrapper.close(){ref=ref-apiwrapper#close}` does under the hood.

## Request logging is separate

`RequestLogger{ref=ref-storage#request-logger}` writes JSONL audit records to its own file. It doesn't know about the cache backend and you don't need a cache to use it.

```python
from pypercache import RequestLogger

log = RequestLogger("requests.log")
log.log(uri="/v1/items", status=200)

for entry in log.get_logs_from_last_seconds(60):
    print(entry.data["uri"], entry.data["status"])
```
