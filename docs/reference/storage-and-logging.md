# Storage and Logging Reference

## Imports

```python
from pypercache import RequestLogger
from pypercache.storage import (
    ChunkedDictionary,
    ChunkedStorage,
    JSONStorage,
    PickleStorage,
    SQLiteStorage,
    StorageMechanism,
    get_storage_mechanism,
)
```

## Backend selection

```python
get_storage_mechanism("cache.db")
```

Returns the backend class selected by file extension.

| Extension | Backend class |
|---|---|
| `.pkl` | `PickleStorage` |
| `.json` | `JSONStorage` |
| `.manifest` | `ChunkedStorage` |
| `.db` | `SQLiteStorage` |

## `StorageMechanism`

Abstract base class for custom backends.

### Public methods

- `load()`
- `save(data)`
- `get_record(key)`
- `update_record(key, data)`
- `store_record(key, cache_record_dict)`
- `erase_everything()`
- `touch_store()`

### Methods to implement in custom backends

- `_impl__touch_store(filepath)`
- `_impl__load(filepath)`
- `_impl__save(cache_records_dict, filepath)`
- `_impl__update_record(key, data)`
- `_impl__erase_everything()`

## `SQLiteStorage`

The most specialized backend. Prefer using it through `Cache` rather than directly.

### Constructor

```python
SQLiteStorage(
    filepath,
    flush_interval=5.0,
    dirty_threshold=50,
)
```

### Behavior

- Loads all rows into memory on open
- Tracks dirty keys in memory
- Uses WAL mode
- `store()` and `update()` flush immediately by default
- Manual flush mode is opt-in

### Manual flush mode

When enabled, writes stay buffered in memory until `flush()` or `close()` is called.

```python
cache.enable_manual_flush_mode()
# ... writes ...
cache.flush()
cache.close()
```

Call `disable_manual_flush_mode()` to return to immediate-flush writes. Disabling also flushes any pending writes.

### Context manager

```python
with SQLiteStorage("cache.db") as store:
    ...
```

---

## `RequestLogger`

### Constructor

```python
RequestLogger(filepath: str | None = None)
```

Default path: `api_logfile.log`. Independent of the cache backend.

### Methods

#### `log`

```python
logger.log(uri, status)
```

Appends one JSON object line to the log file.

#### `get_logs_from_last_seconds`

```python
logger.get_logs_from_last_seconds(seconds=60) -> list[LogRecord]
```

Returns matching records sorted oldest-first.

#### `as_list`

```python
logger.as_list() -> list[dict]
```

Returns raw record dicts.

## `LogRecord`

| Attribute | Description |
|---|---|
| `timestamp` | Unix timestamp of the log entry |
| `data` | Dict with shape `{"uri": "...", "status": 200}` |
