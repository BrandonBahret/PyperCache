---

tag: Reference

comment: "REF: STORAGE"

title: Storage & logging

title_em: "API"

lead: |

  Exact signatures for storage backends, `StorageMechanism{ref=ref-storage#storage-mechanism}`, and `RequestLogger{ref=ref-storage#request-logger}`.

breadcrumb: "pypercache / storage & logging"

---



```python
from pypercache import RequestLogger
from pypercache.storage import (
    ChunkedDictionary, ChunkedStorage, JSONStorage,
    PickleStorage, SQLiteStorage, StorageMechanism,
    get_storage_mechanism,
)
```

## Backend selection {id=backend-selection}

:::method
get_storage_mechanism("cache.db")
:::

Returns the backend class for the given file extension.

:::table
| Extension | Class |
| --- | --- |
| .pkl | PickleStorage |
| .json | JSONStorage |
| .manifest | ChunkedStorage |
| .db | SQLiteStorage |
:::

## StorageMechanism {id=storage-mechanism}

Abstract base class for custom backends. Implement these private methods:

* `_impl__touch_store(filepath)`
* `_impl__load(filepath)`
* `_impl__save(cache_records_dict, filepath)`
* `_impl__update_record(key, data)`
* `_impl__erase_everything()`

## SQLiteStorage {id=sqlite-storage}

:::method
SQLiteStorage(filepath, flush_interval=5.0, dirty_threshold=50,)
:::

Loads all rows into memory on open. Uses WAL mode. Flushes `store(){ref=ref-cache#store}` and `update(){ref=ref-cache#update}` writes immediately by default. Supports `flush()`, `close()`, `enable_manual_flush_mode()`, `disable_manual_flush_mode()`, and context manager usage. Manual flush mode is opt-in; when enabled, writes stay buffered until `flush()` or `close()`.

---

## RequestLogger {id=request-logger}

:::method
RequestLogger(filepath: str | None = None)
:::

Default path: `api_logfile.log{ref=ref-storage#request-logger}`. Writes JSONL records.

### log {id=log}

:::method
logger.log(uri, status)
:::

Appends one JSON object line to the log file.

### get_logs_from_last_seconds {id=get-logs-from-last-seconds}

:::method
logger.get_logs_from_last_seconds(seconds=60) → list[LogRecord]
:::

Returns matching records sorted oldest-first.

### as_list {id=as-list}

:::method
logger.as_list() → list[dict]
:::

Returns raw record dicts.

## LogRecord {id=log-record}

:::table
| Attribute | Description |
| --- | --- |
| timestamp | Unix timestamp of the log entry. |
| data | Dict with shape `{"uri": "...", "status": 200}{ref=ref-storage#log-record}`. |
:::
